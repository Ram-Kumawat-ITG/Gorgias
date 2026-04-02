# Gift card admin endpoints — fetch from Shopify, assign to customers, notify, history
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.database import get_db
from app.models.gift_card import GiftCardAssignRequest
from app.services.gift_card_service import (
    fetch_shopify_gift_cards,
    get_shopify_gift_card,
    assign_gift_card,
    notify_customer,
    get_assigned_gift_cards,
    expire_gift_card,
)

router = APIRouter(prefix="/gift-cards", tags=["Gift Cards"])


@router.get("/store-domain")
async def get_store_domain():
    """Return the Shopify store domain from ENV for the frontend 'Visit online store' button."""
    domain = settings.shopify_store_domain
    if domain:
        # Ensure it has a protocol
        url = f"https://{domain}" if not domain.startswith("http") else domain
        return {"store_url": url}
    return {"store_url": ""}


@router.get("/shopify")
async def list_shopify_gift_cards(status: str = "enabled", limit: int = 50):
    """Fetch gift cards directly from Shopify Admin API.
    Status: enabled (active), disabled, or empty for all."""
    cards = await fetch_shopify_gift_cards(status=status, limit=limit)
    return {"gift_cards": cards, "total": len(cards)}


@router.get("/shopify/{gift_card_id}")
async def get_single_shopify_gift_card(gift_card_id: str):
    """Fetch a single gift card from Shopify by ID (includes full code)."""
    card = await get_shopify_gift_card(gift_card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Gift card not found on Shopify")
    return card


@router.get("/assignments")
async def list_assignments(status: str = None, page: int = 1, limit: int = 20):
    """List all gift card assignments (history of cards assigned to customers).
    Filter by status: notified, pending, or omit for all."""
    result = await get_assigned_gift_cards(status_filter=status, page=page, limit=limit)
    return result


@router.post("/assign")
async def assign_and_notify(data: GiftCardAssignRequest):
    """Assign a Shopify gift card to a customer.
    Creates ONE gift card and stores it with all selected channels (comma-separated).
    The full gift card code is fetched from Shopify during assignment."""
    channels = data.channels or ["email"]
    channel_str = ",".join(channels)
    result = await assign_gift_card(
        shopify_gift_card_id=data.shopify_gift_card_id,
        code=data.code,
        balance=data.balance,
        currency=data.currency,
        customer_email=data.customer_email,
        channel=channel_str,
        ticket_id=data.ticket_id,
        gift_type=data.type,
        expires_at=data.expires_at,
    )
    return result


@router.post("/assignments/{assignment_id}/notify")
async def notify(assignment_id: str):
    """Send the gift card code to the customer via their assigned channel."""
    result = await notify_customer(assignment_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/assignments/{assignment_id}/expire")
async def expire(assignment_id: str):
    """Expire/disable a gift card on Shopify and update local DB."""
    result = await expire_gift_card(assignment_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(assignment_id: str):
    """Delete an assignment record."""
    db = get_db()
    gc = await db.gift_cards.find_one({"id": assignment_id})
    if not gc:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.gift_cards.delete_one({"id": assignment_id})
    return {"status": "deleted"}
