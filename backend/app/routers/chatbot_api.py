# Chatbot integration API — secure endpoints for the seniors' Shopify AI chatbot.
# Auth: X-Shop-Domain + X-API-Key headers (same handshake as external_tickets.py).
# All routes live under /api/chatbot/...
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel

from app.database import get_db, get_db_b
from app.models.ticket import TicketInDB
from app.models.message import MessageInDB
from app.services.api_key_service import verify_api_key
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.shopify_client import shopify_get, shopify_post, ShopifyAPIError
from app.services.ticket_service import apply_sla_policy, classify_ticket_type, _get_admin_agent_id
from app.services.activity_service import log_activity
from app.services.whatsapp_service import send_text_message, get_whatsapp_config

router = APIRouter(prefix="/api/chatbot", tags=["Chatbot API"])


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION DEPENDENCY
# ─────────────────────────────────────────────────────────────────────────────

async def verify_chatbot(
    x_shop_domain: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> dict:
    """Verify chatbot caller via X-Shop-Domain + X-API-Key.

    Returns the merchant document on success.
    Raises 401/422/403 on any failure.
    """
    if not x_shop_domain:
        raise HTTPException(status_code=422, detail="X-Shop-Domain header is required")
    if not x_api_key:
        raise HTTPException(status_code=422, detail="X-API-Key header is required")
    if not x_shop_domain.endswith(".myshopify.com"):
        raise HTTPException(
            status_code=422,
            detail="X-Shop-Domain must end with .myshopify.com",
        )

    db = get_db()
    merchant = await db.merchants.find_one({"shopify_store_domain": x_shop_domain})
    if not merchant:
        raise HTTPException(status_code=401, detail="Store not registered.")
    if not merchant.get("is_active", True):
        raise HTTPException(status_code=403, detail="Store access disabled.")

    stored_hash = merchant.get("api_key_hash", "")
    if not stored_hash or not verify_api_key(x_api_key, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid API key.")

    await db.merchants.update_one(
        {"shopify_store_domain": x_shop_domain},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )
    return merchant


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────

class ChatbotTicketCreate(BaseModel):
    subject: str
    customer_email: str
    customer_name: Optional[str] = None
    channel: str = "whatsapp"          # whatsapp | chat | email | manual
    priority: str = "normal"           # low | normal | high | urgent
    tags: List[str] = []
    initial_message: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    shopify_order_id: Optional[str] = None
    shopify_order_number: Optional[str] = None
    ticket_type: Optional[str] = None  # refund | return | cancel_requested | general …


class ChatbotTicketUpdate(BaseModel):
    status: Optional[str] = None       # open | pending | resolved | closed
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    assignee_id: Optional[str] = None
    ticket_type: Optional[str] = None


class ChatbotMessageCreate(BaseModel):
    body: str
    sender_type: str = "bot"           # bot | customer | agent | system
    sender_name: Optional[str] = None


class WhatsAppSendRequest(BaseModel):
    to_phone: str                      # e.g. "919876543210" or "+919876543210"
    message: str
    ticket_id: Optional[str] = None    # optional — logs message to ticket if provided


class OrderCancelRequest(BaseModel):
    reason: str = "customer"           # customer | inventory | fraud | declined | other
    restock: bool = True
    notify_customer: bool = False


class OrderRefundRequest(BaseModel):
    custom_amount: str                 # e.g. "499.00"
    note: Optional[str] = None
    notify_customer: bool = True


class ConversationAnalyzeRequest(BaseModel):
    messages: List[dict]               # [{sender, message}] or [{sender_type, body}]
    subject: str = ""
    customer_email: str = ""
    shopify_order_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# TICKETS — list / get / create / update
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/tickets")
async def list_tickets(
    email: Optional[str] = Query(None, description="Filter by customer email"),
    phone: Optional[str] = Query(None, description="Filter by WhatsApp phone"),
    status: Optional[str] = Query(None, description="open | pending | resolved | closed"),
    channel: Optional[str] = Query(None, description="whatsapp | email | chat"),
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    merchant: dict = Depends(verify_chatbot),
):
    """List tickets. Filter by customer email, phone, status, or channel."""
    db = get_db()
    query: dict = {}

    if email:
        query["customer_email"] = email
    if phone:
        # phone stored as whatsapp_phone on ticket
        normalized = phone.lstrip("+")
        query["whatsapp_phone"] = {"$in": [phone, normalized, f"+{normalized}"]}
    if status:
        query["status"] = status
    if channel:
        query["channel"] = channel

    skip = (page - 1) * limit
    cursor = db.tickets.find(query).sort("created_at", -1).skip(skip).limit(limit)
    tickets = await cursor.to_list(limit)
    total = await db.tickets.count_documents(query)

    for t in tickets:
        t["_id"] = str(t["_id"])

    return {"tickets": tickets, "total": total, "page": page, "limit": limit}


@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    include_messages: bool = Query(True),
    merchant: dict = Depends(verify_chatbot),
):
    """Get a single ticket by ID, optionally including its message history."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket["_id"] = str(ticket["_id"])

    if include_messages:
        msgs = await db.messages.find({"ticket_id": ticket_id}).sort("created_at", 1).to_list(200)
        for m in msgs:
            m["_id"] = str(m["_id"])
        ticket["messages"] = msgs

    return ticket


@router.post("/tickets", status_code=201)
async def create_ticket(
    data: ChatbotTicketCreate,
    merchant: dict = Depends(verify_chatbot),
):
    """Create a new support ticket on behalf of the chatbot.

    Pass whatsapp_phone to link to the WhatsApp conversation.
    Pass shopify_order_id / shopify_order_number to pre-link an order.
    """
    db = get_db()

    # Sync customer from Shopify (skips placeholder emails automatically)
    customer = await fetch_and_sync_customer(data.customer_email)
    admin_id = await _get_admin_agent_id()

    ticket_type = data.ticket_type or classify_ticket_type(data.subject, data.initial_message or "")

    ticket = TicketInDB(
        subject=data.subject,
        customer_email=data.customer_email,
        customer_name=data.customer_name or f"{customer.get('first_name','')} {customer.get('last_name','')}".strip() or None,
        shopify_customer_id=customer.get("shopify_customer_id"),
        merchant_id=merchant.get("id"),
        source_store=merchant.get("shopify_store_domain"),
        channel=data.channel,
        priority=data.priority,
        tags=data.tags,
        ticket_type=ticket_type,
        assignee_id=admin_id,
        whatsapp_phone=data.whatsapp_phone,
        shopify_order_id=data.shopify_order_id,
        shopify_order_number=data.shopify_order_number,
    )

    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    if data.initial_message:
        msg = MessageInDB(
            ticket_id=ticket.id,
            body=data.initial_message,
            sender_type="customer",
        )
        await db.messages.insert_one(msg.model_dump())

    await log_activity(
        entity_type="ticket",
        entity_id=ticket.id,
        event="ticket.created",
        actor_type="chatbot",
        actor_id=merchant.get("shopify_store_domain"),
        actor_name="AI Chatbot",
        description=f"Ticket created via chatbot API: {data.subject}",
        customer_email=data.customer_email,
    )

    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("ticket.created", ticket_doc)
    except Exception:
        pass

    ticket_doc.pop("_id", None)
    return ticket_doc


@router.patch("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    data: ChatbotTicketUpdate,
    merchant: dict = Depends(verify_chatbot),
):
    """Update ticket status, priority, tags, or type."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    updates: dict = {"updated_at": datetime.now(timezone.utc)}
    if data.status is not None:
        updates["status"] = data.status
        if data.status == "resolved":
            updates["resolved_at"] = datetime.now(timezone.utc)
    if data.priority is not None:
        updates["priority"] = data.priority
    if data.tags is not None:
        updates["tags"] = data.tags
    if data.assignee_id is not None:
        updates["assignee_id"] = data.assignee_id
    if data.ticket_type is not None:
        updates["ticket_type"] = data.ticket_type

    await db.tickets.update_one({"id": ticket_id}, {"$set": updates})

    updated = await db.tickets.find_one({"id": ticket_id})
    updated["_id"] = str(updated["_id"])
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# TICKET MESSAGES — list / add
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/tickets/{ticket_id}/messages")
async def get_ticket_messages(
    ticket_id: str,
    limit: int = Query(100, ge=1, le=500),
    merchant: dict = Depends(verify_chatbot),
):
    """Return all messages for a ticket, oldest first."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msgs = await db.messages.find({"ticket_id": ticket_id}).sort("created_at", 1).to_list(limit)
    for m in msgs:
        m["_id"] = str(m["_id"])
    return {"messages": msgs, "total": len(msgs)}


@router.post("/tickets/{ticket_id}/messages", status_code=201)
async def add_ticket_message(
    ticket_id: str,
    data: ChatbotMessageCreate,
    merchant: dict = Depends(verify_chatbot),
):
    """Append a message to a ticket (chatbot reply, customer message, or system note)."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = MessageInDB(
        ticket_id=ticket_id,
        body=data.body,
        sender_type=data.sender_type,
    )
    msg_doc = msg.model_dump()
    await db.messages.insert_one(msg_doc)

    # Mark ticket as pending when chatbot/agent replies
    if data.sender_type in ("bot", "agent", "ai"):
        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": {"status": "pending", "updated_at": datetime.now(timezone.utc)}},
        )

    msg_doc.pop("_id", None)
    return msg_doc


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP — send message / message history
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/whatsapp/send")
async def send_whatsapp_message(
    data: WhatsAppSendRequest,
    merchant: dict = Depends(verify_chatbot),
):
    """Send a WhatsApp text message to a customer phone number.

    Optionally pass ticket_id to log the outbound message on the ticket.
    Uses merchant-specific WhatsApp config when available.
    """
    merchant_id = merchant.get("id")
    config = await get_whatsapp_config(merchant_id)

    result = await send_text_message(data.to_phone, data.message, config)

    if result.get("error"):
        raise HTTPException(status_code=502, detail=f"WhatsApp send failed: {result.get('detail', result.get('error'))}")

    # Log the message to the ticket if provided
    if data.ticket_id:
        db = get_db()
        ticket = await db.tickets.find_one({"id": data.ticket_id})
        if ticket:
            msg = MessageInDB(
                ticket_id=data.ticket_id,
                body=data.message,
                sender_type="agent",
                channel="whatsapp",
            )
            await db.messages.insert_one(msg.model_dump())
            await db.tickets.update_one(
                {"id": data.ticket_id},
                {"$set": {"status": "pending", "updated_at": datetime.now(timezone.utc)}},
            )

    return {"status": "sent", "to": data.to_phone, "whatsapp_response": result}


@router.get("/whatsapp/history/{phone}")
async def get_whatsapp_history(
    phone: str,
    limit: int = Query(50, ge=1, le=200),
    merchant: dict = Depends(verify_chatbot),
):
    """Return the full WhatsApp message history for a given phone number.

    Looks up all tickets linked to the phone and returns their messages in
    chronological order — giving the chatbot full conversation context.
    """
    db = get_db()
    normalized = phone.lstrip("+")
    # Find all tickets linked to this phone
    tickets = await db.tickets.find(
        {"whatsapp_phone": {"$in": [phone, normalized, f"+{normalized}"]}}
    ).sort("created_at", -1).to_list(20)

    if not tickets:
        return {"messages": [], "tickets": [], "phone": phone}

    ticket_ids = [t["id"] for t in tickets]
    msgs = (
        await db.messages.find({"ticket_id": {"$in": ticket_ids}})
        .sort("created_at", 1)
        .to_list(limit)
    )
    for m in msgs:
        m["_id"] = str(m["_id"])
    for t in tickets:
        t["_id"] = str(t["_id"])

    return {
        "phone": phone,
        "tickets": tickets,
        "messages": msgs,
        "total_messages": len(msgs),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SHOPIFY ORDERS — lookup / cancel / refund
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/shopify/orders/by-email/{email}")
async def get_orders_by_email(
    email: str,
    limit: int = Query(10, ge=1, le=50),
    merchant: dict = Depends(verify_chatbot),
):
    """Look up Shopify orders for a customer email address.

    Returns a list of orders sorted by most recent first.
    """
    try:
        data = await shopify_get(
            "/orders.json",
            {"email": email, "status": "any", "limit": limit},
        )
        orders = data.get("orders", [])
        return {
            "email": email,
            "orders": [_slim_order(o) for o in orders],
            "total": len(orders),
        }
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/shopify/orders/{order_id}")
async def get_order(
    order_id: str,
    merchant: dict = Depends(verify_chatbot),
):
    """Get full details of a single Shopify order by its ID."""
    try:
        data = await shopify_get(f"/orders/{order_id}.json")
        return _slim_order(data.get("order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/shopify/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    data: OrderCancelRequest,
    merchant: dict = Depends(verify_chatbot),
):
    """Cancel a Shopify order. Optionally restock items and notify the customer."""
    try:
        result = await shopify_post(
            f"/orders/{order_id}/cancel.json",
            {"reason": data.reason, "restock": data.restock, "email": data.notify_customer},
        )
        order = result.get("order", {})
        return {
            "status": "cancelled",
            "order_id": order_id,
            "cancelled_at": order.get("cancelled_at"),
            "cancel_reason": order.get("cancel_reason"),
        }
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/shopify/orders/{order_id}/refund")
async def refund_order(
    order_id: str,
    data: OrderRefundRequest,
    merchant: dict = Depends(verify_chatbot),
):
    """Issue a custom-amount refund on a Shopify order.

    Automatically finds the original payment transaction to refund against.
    """
    try:
        # Look up paid transactions to get a parent_id
        txns = await shopify_get(f"/orders/{order_id}/transactions.json")
        parent_id = None
        for t in txns.get("transactions", []):
            if t.get("kind") in ("sale", "capture") and t.get("status") == "success":
                parent_id = t["id"]
                break

        if not parent_id:
            raise HTTPException(status_code=400, detail="No paid transaction found to refund against")

        refund_payload = {
            "refund": {
                "notify": data.notify_customer,
                "transactions": [
                    {
                        "parent_id": parent_id,
                        "amount": data.custom_amount,
                        "kind": "refund",
                        "gateway": "manual",
                    }
                ],
            }
        }
        if data.note:
            refund_payload["refund"]["note"] = data.note

        result = await shopify_post(f"/orders/{order_id}/refunds.json", refund_payload)
        refund = result.get("refund", {})
        return {
            "status": "refunded",
            "order_id": order_id,
            "refund_id": str(refund.get("id", "")),
            "amount": data.custom_amount,
            "created_at": refund.get("created_at"),
        }
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─────────────────────────────────────────────────────────────────────────────
# SHOPIFY CUSTOMERS — lookup by email or ID
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/shopify/customers/by-email/{email}")
async def get_customer_by_email(
    email: str,
    merchant: dict = Depends(verify_chatbot),
):
    """Look up a Shopify customer by email address."""
    try:
        data = await shopify_get("/customers/search.json", {"query": f"email:{email}", "limit": 1})
        customers = data.get("customers", [])
        if not customers:
            raise HTTPException(status_code=404, detail="Customer not found")
        return _slim_customer(customers[0])
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/shopify/customers/{customer_id}")
async def get_customer_by_id(
    customer_id: str,
    merchant: dict = Depends(verify_chatbot),
):
    """Get a Shopify customer by their Shopify customer ID."""
    try:
        data = await shopify_get(f"/customers/{customer_id}.json")
        return _slim_customer(data.get("customer", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─────────────────────────────────────────────────────────────────────────────
# AI — analyze a conversation
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/ai/analyze")
async def analyze_conversation(
    data: ConversationAnalyzeRequest,
    merchant: dict = Depends(verify_chatbot),
):
    """Run AI analysis on a conversation transcript.

    Returns intent, sentiment, suggested actions, and a suggested reply.
    The chatbot can call this to understand what the customer wants and
    decide which Shopify action to take next.
    """
    from app.services.ai_agent_service import analyze_conversation as _analyze
    result = await _analyze(
        messages=data.messages,
        subject=data.subject,
        customer_email=data.customer_email,
        shopify_order_id=data.shopify_order_id,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _slim_order(o: dict) -> dict:
    """Return a compact, chatbot-friendly order summary."""
    customer = o.get("customer") or {}
    shipping = o.get("shipping_address") or {}
    fulfillments = o.get("fulfillments") or []
    return {
        "id": str(o.get("id", "")),
        "order_number": o.get("order_number"),
        "name": o.get("name", ""),
        "email": o.get("email") or customer.get("email"),
        "customer_id": str(customer.get("id", "")),
        "customer_name": f"{customer.get('first_name','')} {customer.get('last_name','')}".strip(),
        "financial_status": o.get("financial_status"),
        "fulfillment_status": o.get("fulfillment_status"),
        "total_price": o.get("total_price"),
        "currency": o.get("currency"),
        "cancelled_at": o.get("cancelled_at"),
        "cancel_reason": o.get("cancel_reason"),
        "created_at": o.get("created_at"),
        "shipping_address": {
            "address1": shipping.get("address1"),
            "city": shipping.get("city"),
            "zip": shipping.get("zip"),
            "country": shipping.get("country"),
        } if shipping else None,
        "tracking_number": fulfillments[0].get("tracking_number") if fulfillments else None,
        "tracking_url": fulfillments[0].get("tracking_url") if fulfillments else None,
        "line_items": [
            {
                "id": str(li.get("id", "")),
                "title": li.get("title"),
                "quantity": li.get("quantity"),
                "price": li.get("price"),
                "sku": li.get("sku"),
                "variant_id": str(li.get("variant_id") or ""),
            }
            for li in o.get("line_items", [])
        ],
    }


def _slim_customer(c: dict) -> dict:
    """Return a compact, chatbot-friendly customer summary."""
    addresses = c.get("addresses") or []
    addr = addresses[0] if addresses else {}
    return {
        "id": str(c.get("id", "")),
        "email": c.get("email"),
        "first_name": c.get("first_name"),
        "last_name": c.get("last_name"),
        "phone": c.get("phone"),
        "orders_count": c.get("orders_count", 0),
        "total_spent": c.get("total_spent"),
        "tags": c.get("tags"),
        "address": {
            "address1": addr.get("address1"),
            "city": addr.get("city"),
            "zip": addr.get("zip"),
            "country": addr.get("country"),
        } if addr else None,
        "created_at": c.get("created_at"),
    }
