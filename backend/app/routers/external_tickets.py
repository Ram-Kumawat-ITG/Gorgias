# External ticket creation router — allows registered external Shopify stores
# to create tickets via API key + shop domain verification (MongoDB handshake).
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from app.database import get_db
from app.models.ticket import TicketCreate, TicketInDB
from app.models.message import MessageInDB
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.ticket_service import apply_sla_policy, classify_ticket_type, _get_admin_agent_id
from app.services.activity_service import log_activity
from app.services.api_key_service import verify_api_key
from app.services.merchant_shopify import get_shopify_creds

router = APIRouter(prefix="/api/external", tags=["External"])


# ---------------------------------------------------------------------------
# Merchant verification dependency — API key + shop domain handshake
# ---------------------------------------------------------------------------

async def verify_merchant(
    x_shop_domain: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> str:
    """Verify the calling store using both shop domain and API key.

    Checks:
    1. Both headers are present (422 if missing)
    2. Shop domain exists in merchants collection
    3. API key hash matches the stored hash
    4. Merchant is active (403 if inactive)
    Updates last_used_at on success. Returns verified shop_domain.
    """
    if not x_shop_domain:
        raise HTTPException(status_code=422, detail="X-Shop-Domain header is required")

    if not x_api_key:
        raise HTTPException(status_code=422, detail="X-API-Key header is required")

    if not x_shop_domain.endswith(".myshopify.com"):
        raise HTTPException(
            status_code=422,
            detail="X-Shop-Domain must end with .myshopify.com (e.g. my-store.myshopify.com)",
        )

    db = get_db()
    merchant = await db.merchants.find_one({"shopify_store_domain": x_shop_domain})

    if not merchant:
        raise HTTPException(status_code=401, detail="Store not registered. Please install the app first.")

    if not merchant.get("is_active", True):
        raise HTTPException(status_code=403, detail="Store access disabled. Contact the administrator.")

    stored_hash = merchant.get("api_key_hash", "")
    if not stored_hash or not verify_api_key(x_api_key, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Update last_used_at timestamp
    await db.merchants.update_one(
        {"shopify_store_domain": x_shop_domain},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )

    return x_shop_domain


# ---------------------------------------------------------------------------
# External ticket creation — same schema as internal, but verified via handshake
# ---------------------------------------------------------------------------

@router.post("/tickets")
async def create_external_ticket(
    data: TicketCreate,
    shop_domain: str = Depends(verify_merchant),
):
    """Create a ticket on behalf of a registered external Shopify store.

    The calling store passes X-Shop-Domain in the header. No access token is
    needed — trust is established by checking the merchants collection.

    Accepts both `initial_message` and `message` (preferred alias). The
    `images` field accepts a list of publicly-accessible image URLs that are
    stored as message attachments and displayed inline in the chat UI.
    """
    db = get_db()

    # Look up the merchant record to get their merchant_id + Shopify credentials
    merchant = await db.merchants.find_one({"shopify_store_domain": shop_domain})
    merchant_id = merchant["id"] if merchant else None

    # Use per-merchant Shopify credentials for customer sync
    store_domain, access_token = await get_shopify_creds(merchant_id=merchant_id, store_domain=shop_domain)
    customer = await fetch_and_sync_customer(
        data.customer_email,
        store_domain=store_domain,
        access_token=access_token,
    )

    admin_id = await _get_admin_agent_id()

    images = [url for url in (data.images or []) if url and url.startswith("http")]

    # Merge into existing open ticket for same customer + store instead of creating a duplicate
    body = data.message or data.initial_message
    existing = await db.tickets.find_one({
        "customer_email": data.customer_email,
        "store_domain": shop_domain,
        "status": "open",
    })
    if existing is None:
        existing = await db.tickets.find_one({
            "customer_email": data.customer_email,
            "source_store": shop_domain,
            "status": "open",
        })

    if existing:
        existing_id = str(existing["id"]) if existing.get("id") else str(existing["_id"])
        if body or images:
            msg = MessageInDB(
                ticket_id=existing_id,
                body=body or "",
                sender_type="customer",
                attachments=images,
                channel="whatsapp" if data.channel == "whatsapp" else None,
            )
            await db.messages.insert_one(msg.model_dump())
        update_fields = {"updated_at": datetime.now(timezone.utc), "status": "open"}
        if images:
            # Merge new image URLs into the ticket's images list (deduplicated)
            existing_images = existing.get("images") or []
            merged_images = list(dict.fromkeys(existing_images + images))
            update_fields["images"] = merged_images
        await db.tickets.update_one(
            {"_id": existing["_id"]},
            {"$set": update_fields},
        )
        await log_activity(
            entity_type="ticket",
            entity_id=existing_id,
            event="message.added",
            actor_type="external_store",
            actor_id=shop_domain,
            actor_name=shop_domain,
            description=f"Follow-up message merged into existing ticket from {shop_domain}",
            customer_email=data.customer_email,
        )
        # Refresh the ticket document to return the updated state
        updated = await db.tickets.find_one({"_id": existing["_id"]})
        if updated:
            updated.pop("_id", None)
            return {"merged": True, "ticket": updated}
        existing.pop("_id", None)
        return {"merged": True, "ticket": existing}

    ticket = TicketInDB(
        subject=data.subject,
        customer_email=data.customer_email,
        customer_name=data.customer_name or f"{customer.get('first_name') or ''} {customer.get('last_name') or ''}".strip() or None,
        shopify_customer_id=data.shopify_customer_id or customer.get("shopify_customer_id"),
        merchant_id=merchant_id,
        store_domain=store_domain or shop_domain,
        source_store=shop_domain,
        channel=data.channel.value if hasattr(data.channel, "value") else data.channel,
        priority=data.priority.value if hasattr(data.priority, "value") else data.priority,
        tags=data.tags,
        images=images,
        ticket_type=classify_ticket_type(data.subject, data.initial_message or data.message or ""),
        assignee_id=admin_id,
    )

    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    if body or images:
        msg_body = body or ""
        msg = MessageInDB(
            ticket_id=ticket.id,
            body=msg_body,
            sender_type="customer",
            attachments=images,
            channel="whatsapp" if data.channel == "whatsapp" else None,
        )
        await db.messages.insert_one(msg.model_dump())

    # Log activity
    await log_activity(
        entity_type="ticket",
        entity_id=ticket.id,
        event="ticket.created",
        actor_type="external_store",
        actor_id=shop_domain,
        actor_name=shop_domain,
        description=f"External ticket created from {shop_domain}: {data.subject}",
        customer_email=data.customer_email,
    )

    # Trigger automations
    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("ticket.created", ticket_doc)
    except Exception:
        pass

    ticket_doc.pop("_id", None)
    return {"merged": False, "ticket": ticket_doc}


# ---------------------------------------------------------------------------
# Follow-up message endpoint — App A adds messages to an existing ticket
# ---------------------------------------------------------------------------

class ExternalMessageCreate(BaseModel):
    message: str
    images: List[str] = []


@router.post("/tickets/{ticket_id}/messages")
async def add_external_message(
    ticket_id: str,
    data: ExternalMessageCreate,
    shop_domain: str = Depends(verify_merchant),
):
    """Add a follow-up customer message (with optional image URLs) to an existing ticket.

    The ticket must belong to the authenticated store (matched via source_store or
    store_domain). Returns the created message document.

    Validation:
    - `message` is required and must be a non-empty string
    - `images` is optional; each entry must be an http/https URL (invalid entries silently dropped)
    - Ticket must exist and belong to this store
    """
    if not data.message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty")

    db = get_db()

    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Confirm ticket belongs to this store
    ticket_store = ticket.get("source_store") or ticket.get("store_domain") or ""
    if ticket_store and ticket_store != shop_domain:
        raise HTTPException(status_code=403, detail="Ticket does not belong to this store")

    images = [url for url in (data.images or []) if url and url.startswith("http")]

    msg = MessageInDB(
        ticket_id=ticket_id,
        body=data.message.strip(),
        sender_type="customer",
        attachments=images,
        channel=ticket.get("channel") if ticket.get("channel") in ("whatsapp", "email") else None,
    )
    msg_doc = msg.model_dump()
    await db.messages.insert_one(msg_doc)

    # Reopen ticket if it was resolved/closed so agent sees the new message
    if ticket.get("status") in ("resolved", "closed"):
        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": {"status": "open", "updated_at": datetime.now(timezone.utc)}},
        )

    await log_activity(
        entity_type="ticket",
        entity_id=ticket_id,
        event="message.added",
        actor_type="external_store",
        actor_id=shop_domain,
        actor_name=shop_domain,
        description=f"Follow-up message added from {shop_domain}",
        customer_email=ticket.get("customer_email"),
    )

    msg_doc.pop("_id", None)
    return msg_doc
