# Shopify data sync — fetches customer + order data from Shopify and caches in MongoDB
from datetime import datetime, timezone
from app.database import get_db
from app.services.shopify_client import shopify_get
from app.models.customer import CustomerInDB


async def fetch_and_sync_customer(email: str, force_refresh: bool = False) -> dict:
    """Fetch customer from Shopify by email, cache in MongoDB."""
    db = get_db()

    if not force_refresh:
        cached = await db.customers.find_one({"email": email})
        if cached:
            cached["_id"] = str(cached["_id"])
            return cached

    try:
        data = await shopify_get("/customers/search.json", {"query": f"email:{email}"})
        customers = data.get("customers", [])
        if not customers:
            customer = CustomerInDB(email=email)
            doc = customer.model_dump()
            set_doc = {k: v for k, v in doc.items() if k != "created_at"}
            await db.customers.update_one(
                {"email": email},
                {"$set": set_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
                upsert=True,
            )
            doc.pop("_id", None)
            return doc

        sc = customers[0]
        customer = CustomerInDB(
            email=email,
            first_name=sc.get("first_name"),
            last_name=sc.get("last_name"),
            shopify_customer_id=str(sc["id"]),
            total_spent=sc.get("total_spent", "0.00"),
            orders_count=sc.get("orders_count", 0),
            tags=sc.get("tags", "").split(", ") if sc.get("tags") else [],
            notes=sc.get("note"),
        )
        doc = customer.model_dump()
        set_doc = {k: v for k, v in doc.items() if k != "created_at"}
        await db.customers.update_one(
            {"email": email},
            {"$set": set_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        doc.pop("_id", None)
        return doc
    except Exception:
        # Shopify unreachable — return cached or create placeholder
        cached = await db.customers.find_one({"email": email})
        if cached:
            cached["_id"] = str(cached["_id"])
            return cached
        customer = CustomerInDB(email=email)
        doc = customer.model_dump()
        set_doc = {k: v for k, v in doc.items() if k != "created_at"}
        await db.customers.update_one(
            {"email": email},
            {"$set": set_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        doc.pop("_id", None)
        return doc


async def fetch_customer_orders(shopify_customer_id: str, force_refresh: bool = False) -> list:
    """Fetch all orders for a Shopify customer, cache snapshots in MongoDB."""
    db = get_db()

    if not force_refresh:
        cached = await db.order_snapshots.find(
            {"shopify_customer_id": shopify_customer_id}
        ).sort("created_at", -1).to_list(50)
        if cached:
            for o in cached:
                o["_id"] = str(o["_id"])
            return cached

    if not shopify_customer_id:
        return []

    try:
        data = await shopify_get(
            f"/customers/{shopify_customer_id}/orders.json",
            {"status": "any", "limit": 50},
        )
        orders = data.get("orders", [])
        results = []
        for order in orders:
            fulfillments = order.get("fulfillments", [])
            tracking_url = fulfillments[0].get("tracking_url") if fulfillments else None
            tracking_number = fulfillments[0].get("tracking_number") if fulfillments else None
            snapshot = {
                "shopify_order_id": str(order["id"]),
                "shopify_customer_id": shopify_customer_id,
                "order_number": order.get("order_number"),
                "email": order.get("email"),
                "financial_status": order.get("financial_status"),
                "fulfillment_status": order.get("fulfillment_status"),
                "total_price": order.get("total_price"),
                "currency": order.get("currency"),
                "tracking_url": tracking_url,
                "tracking_number": tracking_number,
                "line_items": [
                    {"title": li.get("title"), "quantity": li.get("quantity"), "price": li.get("price")}
                    for li in order.get("line_items", [])
                ],
                "created_at": order.get("created_at"),
            }
            await db.order_snapshots.update_one(
                {"shopify_order_id": str(order["id"])},
                {"$set": snapshot},
                upsert=True,
            )
            results.append(snapshot)
        return results
    except Exception:
        # Shopify unreachable — return cached
        cached = await db.order_snapshots.find(
            {"shopify_customer_id": shopify_customer_id}
        ).sort("created_at", -1).to_list(50)
        for o in cached:
            o["_id"] = str(o["_id"])
        return cached


async def fetch_all_shopify_customers(limit: int = 50, since_id: str = None) -> list:
    """Fetch a batch of customers from Shopify and sync to MongoDB."""
    params = {"limit": limit}
    if since_id:
        params["since_id"] = since_id
    try:
        data = await shopify_get("/customers.json", params)
        customers = data.get("customers", [])
        db = get_db()
        results = []
        for sc in customers:
            email = sc.get("email")
            if not email:
                continue
            doc = {
                "email": email,
                "first_name": sc.get("first_name"),
                "last_name": sc.get("last_name"),
                "shopify_customer_id": str(sc["id"]),
                "total_spent": sc.get("total_spent", "0.00"),
                "orders_count": sc.get("orders_count", 0),
                "tags": sc.get("tags", "").split(", ") if sc.get("tags") else [],
                "notes": sc.get("note"),
                "updated_at": datetime.now(timezone.utc),
            }
            await db.customers.update_one(
                {"email": email},
                {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
                upsert=True,
            )
            doc["shopify_created_at"] = sc.get("created_at")
            results.append(doc)
        return results
    except Exception:
        return []


async def fetch_all_shopify_orders(limit: int = 50, status: str = "any") -> list:
    """Fetch recent orders from Shopify and sync to MongoDB."""
    try:
        data = await shopify_get("/orders.json", {"limit": limit, "status": status})
        orders = data.get("orders", [])
        db = get_db()
        results = []
        for order in orders:
            fulfillments = order.get("fulfillments", [])
            tracking_url = fulfillments[0].get("tracking_url") if fulfillments else None
            tracking_number = fulfillments[0].get("tracking_number") if fulfillments else None
            customer = order.get("customer", {})
            snapshot = {
                "shopify_order_id": str(order["id"]),
                "shopify_customer_id": str(customer.get("id", "")),
                "order_number": order.get("order_number"),
                "email": order.get("email") or customer.get("email"),
                "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                "financial_status": order.get("financial_status"),
                "fulfillment_status": order.get("fulfillment_status"),
                "total_price": order.get("total_price"),
                "currency": order.get("currency"),
                "tracking_url": tracking_url,
                "tracking_number": tracking_number,
                "line_items": [
                    {"title": li.get("title"), "quantity": li.get("quantity"), "price": li.get("price")}
                    for li in order.get("line_items", [])
                ],
                "created_at": order.get("created_at"),
            }
            await db.order_snapshots.update_one(
                {"shopify_order_id": str(order["id"])},
                {"$set": snapshot},
                upsert=True,
            )
            results.append(snapshot)
        return results
    except Exception:
        return []
