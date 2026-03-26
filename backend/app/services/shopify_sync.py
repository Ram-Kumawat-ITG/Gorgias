# Shopify data sync — fetches and caches customer + order data from Shopify
from datetime import datetime
from app.database import get_db
from app.services.shopify_client import shopify_get
from app.models.customer import CustomerInDB


async def fetch_and_sync_customer(email: str) -> dict:
    db = get_db()
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
            await db.customers.insert_one(doc)
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
        )
        doc = customer.model_dump()
        set_doc = {k: v for k, v in doc.items() if k != "created_at"}
        await db.customers.update_one(
            {"email": email},
            {"$set": set_doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )
        doc.pop("_id", None)
        return doc
    except Exception:
        customer = CustomerInDB(email=email)
        doc = customer.model_dump()
        set_doc = {k: v for k, v in doc.items() if k != "created_at"}
        await db.customers.update_one(
            {"email": email},
            {"$set": set_doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )
        doc.pop("_id", None)
        return doc


async def fetch_customer_orders(shopify_customer_id: str) -> list:
    db = get_db()
    cached = await db.order_snapshots.find(
        {"shopify_customer_id": shopify_customer_id}
    ).to_list(10)
    if cached:
        for o in cached:
            o["_id"] = str(o["_id"])
        return cached

    if not shopify_customer_id:
        return []

    try:
        data = await shopify_get(
            f"/customers/{shopify_customer_id}/orders.json",
            {"status": "any", "limit": 10},
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
                    {"title": li["title"], "quantity": li["quantity"], "price": li["price"]}
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
