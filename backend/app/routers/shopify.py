# Shopify sync router — pull recent orders from Shopify and create tickets
from fastapi import APIRouter, Depends, Query
from datetime import datetime
from app.routers.auth import get_current_agent
from app.database import get_db
from app.models.ticket import TicketInDB
from app.models.message import MessageInDB
from app.services.shopify_client import shopify_get
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.activity_service import log_activity
from app.services.merchant_shopify import get_shopify_creds
from typing import Optional

router = APIRouter(prefix="/shopify", tags=["Shopify"])


@router.post("/sync-orders")
async def sync_orders(
    limit: int = Query(50, ge=1, le=250),
    agent=Depends(get_current_agent),
):
    """Fetch recent orders from Shopify and create tickets for any that don't already exist."""
    db = get_db()
    created = 0
    skipped = 0
    errors = []

    try:
        data = await shopify_get("/orders.json", {"status": "any", "limit": limit})
    except Exception as e:
        return {"status": "error", "detail": str(e), "created": 0, "skipped": 0}

    orders = data.get("orders", [])

    for order in orders:
        shopify_order_id = str(order["id"])
        email = order.get("email") or order.get("contact_email")
        if not email:
            skipped += 1
            continue

        # Skip if a ticket for this Shopify order already exists
        existing = await db.tickets.find_one({"shopify_order_id": shopify_order_id})
        if existing:
            skipped += 1
            continue

        try:
            customer = await fetch_and_sync_customer(email)

            order_number = order.get("order_number", order.get("name", shopify_order_id))
            financial_status = order.get("financial_status", "unknown")
            fulfillment_status = order.get("fulfillment_status") or "unfulfilled"
            total_price = order.get("total_price", "0.00")
            currency = order.get("currency", "USD")
            line_items = order.get("line_items", [])
            items_summary = ", ".join(
                f"{li.get('title', 'Item')} x{li.get('quantity', 1)}"
                for li in line_items[:5]
            )

            subject = f"Shopify Order #{order_number}"
            message_body = (
                f"Order #{order_number}\n"
                f"Customer: {email}\n"
                f"Status: {financial_status} / {fulfillment_status}\n"
                f"Total: {total_price} {currency}\n"
                f"Items: {items_summary}\n"
            )

            # Store fulfillment tracking if available
            fulfillments = order.get("fulfillments", [])
            if fulfillments:
                tracking_url = fulfillments[0].get("tracking_url", "")
                tracking_number = fulfillments[0].get("tracking_number", "")
                if tracking_url:
                    message_body += f"Tracking: {tracking_url}\n"

            # Determine priority based on financial status
            priority = "normal"
            if financial_status in ("refunded", "voided"):
                priority = "high"
            elif fulfillment_status == "unfulfilled" and financial_status == "paid":
                priority = "normal"

            # Build tags from order data
            tags = ["shopify", financial_status]
            if fulfillment_status:
                tags.append(fulfillment_status)

            customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or None

            ticket = TicketInDB(
                subject=subject,
                customer_email=email,
                customer_name=customer_name,
                shopify_customer_id=customer.get("shopify_customer_id"),
                channel="shopify",
                priority=priority,
                tags=tags,
            )
            ticket_doc = ticket.model_dump()
            ticket_doc["shopify_order_id"] = shopify_order_id
            ticket_doc["shopify_order_number"] = str(order_number)
            ticket_doc["shopify_financial_status"] = financial_status
            ticket_doc["shopify_fulfillment_status"] = fulfillment_status
            ticket_doc["shopify_total_price"] = total_price
            ticket_doc["shopify_currency"] = currency
            ticket_doc["shopify_line_items"] = [
                {"title": li.get("title"), "quantity": li.get("quantity"), "price": li.get("price")}
                for li in line_items
            ]
            ticket_doc["shopify_created_at"] = order.get("created_at")

            await db.tickets.insert_one(ticket_doc)

            # Create initial message with order details
            msg = MessageInDB(
                ticket_id=ticket.id,
                body=message_body,
                sender_type="system",
            )
            await db.messages.insert_one(msg.model_dump())

            # Cache order snapshot
            snapshot = {
                "shopify_order_id": shopify_order_id,
                "shopify_customer_id": customer.get("shopify_customer_id", ""),
                "order_number": order.get("order_number"),
                "email": email,
                "financial_status": financial_status,
                "fulfillment_status": fulfillment_status,
                "total_price": total_price,
                "currency": currency,
                "tracking_url": fulfillments[0].get("tracking_url") if fulfillments else None,
                "tracking_number": fulfillments[0].get("tracking_number") if fulfillments else None,
                "line_items": ticket_doc["shopify_line_items"],
                "created_at": order.get("created_at"),
            }
            await db.order_snapshots.update_one(
                {"shopify_order_id": shopify_order_id},
                {"$set": snapshot},
                upsert=True,
            )

            await log_activity(
                entity_type="ticket",
                entity_id=ticket.id,
                event="ticket.created",
                actor_type="system",
                description=f"Ticket synced from Shopify Order #{order_number}",
                customer_email=email,
                metadata={"shopify_order_id": shopify_order_id},
            )

            created += 1
        except Exception as e:
            errors.append(f"Order {shopify_order_id}: {str(e)}")

    return {
        "status": "ok",
        "created": created,
        "skipped": skipped,
        "total_fetched": len(orders),
        "errors": errors[:10],
    }


@router.get("/inventory")
async def get_inventory_levels(
    variant_ids: str = Query(..., description="Comma-separated Shopify variant IDs"),
    merchant_id: Optional[str] = Query(None),
    agent=Depends(get_current_agent),
):
    """Fetch inventory quantities using inventory_levels API (inventory_quantity is deprecated in 2024-01)."""
    ids = [v.strip() for v in variant_ids.split(",") if v.strip()]
    if not ids:
        return {"inventory": []}
    store_domain, access_token = await get_shopify_creds(merchant_id)
    try:
        # Step 1: fetch variants to get inventory_item_id (needed for inventory_levels lookup)
        variant_data = await shopify_get(
            "/variants.json",
            {"ids": ",".join(ids), "fields": "id,title,sku,inventory_item_id,inventory_management,inventory_policy"},
            store_domain=store_domain, access_token=access_token,
        )
        variants = variant_data.get("variants", [])
        if not variants:
            return {"inventory": []}

        # Build map: inventory_item_id -> variant
        item_id_to_variant = {}
        for v in variants:
            inv_item_id = v.get("inventory_item_id")
            if inv_item_id:
                item_id_to_variant[str(inv_item_id)] = v

        inventory_item_ids = list(item_id_to_variant.keys())

        # Step 2: fetch actual available stock from inventory_levels (requires read_inventory scope)
        qty_by_item: dict = {}
        if inventory_item_ids:
            levels_data = await shopify_get(
                "/inventory_levels.json",
                {"inventory_item_ids": ",".join(inventory_item_ids), "limit": 250},
                store_domain=store_domain, access_token=access_token,
            )
            for level in levels_data.get("inventory_levels", []):
                item_id = str(level.get("inventory_item_id", ""))
                available = level.get("available")
                if available is not None:
                    qty_by_item[item_id] = qty_by_item.get(item_id, 0) + int(available)

        # Build response: one entry per variant with real inventory quantities
        result = []
        for v in variants:
            inv_item_id = str(v.get("inventory_item_id") or "")
            inv_mgmt = v.get("inventory_management") or ""
            # qty is None when item has no inventory levels (not tracked or no read_inventory scope)
            qty = qty_by_item.get(inv_item_id) if inv_item_id in qty_by_item else None
            result.append({
                "variant_id": str(v["id"]),
                "title": v.get("title") or "",
                "sku": v.get("sku") or "",
                "inventory_quantity": qty,
                "inventory_management": inv_mgmt,
                "inventory_policy": v.get("inventory_policy") or "deny",
                "tracked": inv_mgmt == "shopify",
            })

        return {"inventory": result}
    except Exception as e:
        return {"inventory": [], "error": str(e)}


@router.get("/products/{product_id}/variants")
async def get_product_variants(
    product_id: str,
    merchant_id: Optional[str] = Query(None),
    agent=Depends(get_current_agent),
):
    """Fetch all variants for a Shopify product with inventory levels."""
    store_domain, access_token = await get_shopify_creds(merchant_id)
    try:
        data = await shopify_get(f"/products/{product_id}.json", {"fields": "id,title,variants"},
                                 store_domain=store_domain, access_token=access_token)
        product = data.get("product", {})
        variants = product.get("variants", [])
        return {
            "product_title": product.get("title", ""),
            "variants": [
                {
                    "id": str(v["id"]),
                    "title": v.get("title", ""),
                    "sku": v.get("sku", ""),
                    "price": v.get("price", "0.00"),
                    "inventory_quantity": v.get("inventory_quantity", 0),
                    "inventory_management": v.get("inventory_management") or "",
                    "available": (v.get("inventory_quantity", 0) or 0) > 0,
                }
                for v in variants
            ],
        }
    except Exception as e:
        return {"product_title": "", "variants": [], "error": str(e)}


@router.get("/orders")
async def list_shopify_orders(
    limit: int = Query(50, ge=1, le=100),
    agent=Depends(get_current_agent),
):
    """List cached order snapshots from MongoDB."""
    db = get_db()
    orders = await db.order_snapshots.find().sort("created_at", -1).limit(limit).to_list(limit)
    for o in orders:
        o["_id"] = str(o["_id"])
    return {"orders": orders, "total": len(orders)}
