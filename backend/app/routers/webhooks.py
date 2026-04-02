# Shopify webhook handlers — order and customer events with HMAC verification
import json
from fastapi import APIRouter, Request, Depends
from app.middleware.shopify_hmac import verify_shopify_hmac
from app.database import get_db
from app.services.activity_service import log_activity

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/orders/create")
async def order_created(request: Request, body: bytes = Depends(verify_shopify_hmac)):
    order_data = json.loads(body)
    db = get_db()
    await db.order_snapshots.update_one(
        {"shopify_order_id": str(order_data["id"])},
        {"$set": {
            "shopify_order_id": str(order_data["id"]),
            "shopify_customer_id": str(order_data.get("customer", {}).get("id", "")),
            "order_number": order_data.get("order_number"),
            "email": order_data.get("email"),
            "financial_status": order_data.get("financial_status"),
            "fulfillment_status": order_data.get("fulfillment_status"),
            "total_price": order_data.get("total_price"),
            "currency": order_data.get("currency"),
            "line_items": [
                {"title": li["title"], "quantity": li["quantity"], "price": li["price"]}
                for li in order_data.get("line_items", [])
            ],
            "raw": order_data,
        }},
        upsert=True,
    )
    await log_activity(
        entity_type="order",
        entity_id=str(order_data["id"]),
        event="order.created",
        actor_type="shopify",
        description=f"Order #{order_data.get('order_number')} created",
        customer_email=order_data.get("email"),
        metadata={"total_price": order_data.get("total_price")},
    )
    return {"status": "received"}


@router.post("/orders/fulfilled")
async def order_fulfilled(request: Request, body: bytes = Depends(verify_shopify_hmac)):
    order_data = json.loads(body)
    db = get_db()
    fulfillments = order_data.get("fulfillments", [])
    tracking_url = fulfillments[0].get("tracking_url") if fulfillments else None
    tracking_number = fulfillments[0].get("tracking_number") if fulfillments else None
    await db.order_snapshots.update_one(
        {"shopify_order_id": str(order_data["id"])},
        {"$set": {
            "fulfillment_status": "fulfilled",
            "tracking_url": tracking_url,
            "tracking_number": tracking_number,
        }},
    )
    await log_activity(
        entity_type="order",
        entity_id=str(order_data["id"]),
        event="order.fulfilled",
        actor_type="shopify",
        description=f"Order #{order_data.get('order_number')} fulfilled",
        customer_email=order_data.get("email"),
        metadata={"tracking_url": tracking_url},
    )
    return {"status": "received"}


@router.post("/orders/cancelled")
async def order_cancelled(request: Request, body: bytes = Depends(verify_shopify_hmac)):
    order_data = json.loads(body)
    db = get_db()
    order_id_str = str(order_data["id"])
    await db.order_snapshots.update_one(
        {"shopify_order_id": order_id_str},
        {"$set": {
            "financial_status": order_data.get("financial_status", "voided"),
            "cancelled_at": order_data.get("cancelled_at"),
            "cancel_reason": order_data.get("cancel_reason"),
        }},
    )
    # Update any linked ticket
    ticket = await db.tickets.find_one({"shopify_order_id": order_id_str, "status": {"$in": ["open", "pending", "in_progress"]}})
    if ticket:
        from app.models.message import MessageInDB
        note = MessageInDB(
            ticket_id=ticket["id"],
            body=f"Order #{order_data.get('order_number')} has been cancelled via Shopify.",
            sender_type="system",
        )
        await db.messages.insert_one(note.model_dump())
    await log_activity(
        entity_type="order",
        entity_id=order_id_str,
        event="order.cancelled",
        actor_type="shopify",
        description=f"Order #{order_data.get('order_number')} cancelled",
        customer_email=order_data.get("email"),
        metadata={"cancel_reason": order_data.get("cancel_reason")},
    )
    return {"status": "received"}


@router.post("/orders/updated")
async def order_updated(request: Request, body: bytes = Depends(verify_shopify_hmac)):
    order_data = json.loads(body)
    db = get_db()
    await db.order_snapshots.update_one(
        {"shopify_order_id": str(order_data["id"])},
        {"$set": {
            "shopify_order_id": str(order_data["id"]),
            "shopify_customer_id": str(order_data.get("customer", {}).get("id", "")),
            "order_number": order_data.get("order_number"),
            "email": order_data.get("email"),
            "financial_status": order_data.get("financial_status"),
            "fulfillment_status": order_data.get("fulfillment_status"),
            "total_price": order_data.get("total_price"),
            "currency": order_data.get("currency"),
            "cancelled_at": order_data.get("cancelled_at"),
            "line_items": [
                {"title": li["title"], "quantity": li["quantity"], "price": li["price"]}
                for li in order_data.get("line_items", [])
            ],
        }},
        upsert=True,
    )
    return {"status": "received"}


@router.post("/customers/update")
async def customer_updated(request: Request, body: bytes = Depends(verify_shopify_hmac)):
    c = json.loads(body)
    db = get_db()
    await db.customers.update_one(
        {"shopify_customer_id": str(c["id"])},
        {"$set": {
            "shopify_customer_id": str(c["id"]),
            "email": c.get("email"),
            "first_name": c.get("first_name"),
            "last_name": c.get("last_name"),
            "total_spent": c.get("total_spent", "0.00"),
            "orders_count": c.get("orders_count", 0),
        }},
        upsert=True,
    )
    return {"status": "received"}
