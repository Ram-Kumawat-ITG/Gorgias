# External ticket creation router — allows registered external Shopify stores
# to create tickets via MongoDB handshake (no access token required).
from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Optional
from datetime import datetime, timezone
from app.database import get_db
from app.models.ticket import TicketCreate, TicketInDB
from app.models.message import MessageInDB
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.ticket_service import apply_sla_policy, classify_ticket_type, _get_admin_agent_id
from app.services.activity_service import log_activity

router = APIRouter(prefix="/api/external", tags=["External"])


# ---------------------------------------------------------------------------
# Merchant verification dependency — MongoDB handshake
# ---------------------------------------------------------------------------

async def verify_merchant(x_shop_domain: Optional[str] = Header(None)) -> str:
    """Verify the calling store is registered in the merchants collection.

    Returns the verified shop_domain string on success.
    """
    if not x_shop_domain:
        raise HTTPException(
            status_code=422,
            detail="X-Shop-Domain header is required",
        )

    if not x_shop_domain.endswith(".myshopify.com"):
        raise HTTPException(
            status_code=422,
            detail="X-Shop-Domain must end with .myshopify.com (e.g. my-store.myshopify.com)",
        )

    db = get_db()
    merchant = await db.merchants.find_one({
        "shopify_store_domain": x_shop_domain,
        "is_active": True,
    })

    if not merchant:
        raise HTTPException(
            status_code=401,
            detail="Store not registered. Please install the app first.",
        )

    return x_shop_domain


# ---------------------------------------------------------------------------
# Register a merchant store (lightweight — for manual onboarding)
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class MerchantRegister(BaseModel):
    shop_domain: str
    app_name: Optional[str] = None


@router.post("/register-store")
async def register_store(data: MerchantRegister):
    """Register a Shopify store so it can create external tickets."""
    if not data.shop_domain.endswith(".myshopify.com"):
        raise HTTPException(
            status_code=422,
            detail="shop_domain must end with .myshopify.com",
        )

    db = get_db()
    existing = await db.merchants.find_one({"shopify_store_domain": data.shop_domain})
    if existing:
        raise HTTPException(status_code=400, detail="Store already registered")

    import uuid
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.shop_domain.replace(".myshopify.com", ""),
        "support_email": "",
        "mailgun_api_key": "",
        "mailgun_domain": "",
        "shopify_store_domain": data.shop_domain,
        "shopify_access_token": "",
        "app_name": data.app_name or "",
        "is_active": True,
        "installed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    await db.merchants.insert_one(doc)
    doc.pop("_id", None)
    return {"status": "registered", "shop_domain": data.shop_domain, "merchant_id": doc["id"]}


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
    """
    db = get_db()

    # Look up the merchant record to get their merchant_id
    merchant = await db.merchants.find_one({"shopify_store_domain": shop_domain})
    merchant_id = merchant["id"] if merchant else None

    # Sync customer — uses default (.env) Shopify credentials for lookup
    customer = await fetch_and_sync_customer(data.customer_email)

    admin_id = await _get_admin_agent_id()

    ticket = TicketInDB(
        subject=data.subject,
        customer_email=data.customer_email,
        customer_name=data.customer_name or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or None,
        shopify_customer_id=data.shopify_customer_id or customer.get("shopify_customer_id"),
        merchant_id=merchant_id,
        source_store=shop_domain,
        channel=data.channel.value if hasattr(data.channel, "value") else data.channel,
        priority=data.priority.value if hasattr(data.priority, "value") else data.priority,
        tags=data.tags,
        ticket_type=classify_ticket_type(data.subject, data.initial_message or ""),
        assignee_id=admin_id,
    )

    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    # Create initial message if provided
    if data.initial_message:
        msg = MessageInDB(
            ticket_id=ticket.id,
            body=data.initial_message,
            sender_type="customer",
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
    return ticket_doc
