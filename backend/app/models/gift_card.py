# Gift card data model — tracks Shopify gift card assignments to customers
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class GiftCardAssignment(BaseModel):
    """Tracks when a Shopify gift card is assigned to a customer."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    shopify_gift_card_id: str         # Shopify gift card ID
    code: str                          # last 4 chars masked in UI, full code for notification
    balance: str                       # current balance from Shopify
    currency: str = "INR"
    customer_email: str
    customer_id: Optional[str] = None
    channel: str = "email"             # whatsapp, instagram, email
    assigned_by: str = "admin"         # admin agent id or "bot"
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    notified: bool = False
    notified_at: Optional[datetime] = None
    ticket_id: Optional[str] = None
    merchant_id: Optional[str] = None
    # Retention context
    type: str = "manual"               # manual or retention
    expires_at: Optional[str] = None   # from Shopify


class GiftCardAssignRequest(BaseModel):
    """Request body for assigning a Shopify gift card to a customer."""
    shopify_gift_card_id: str
    code: str
    balance: str
    currency: str = "INR"
    customer_email: str
    channels: list[str] = ["email"]   # one or more of: email, whatsapp, instagram
    ticket_id: Optional[str] = None
    type: str = "manual"
    expires_at: Optional[str] = None
