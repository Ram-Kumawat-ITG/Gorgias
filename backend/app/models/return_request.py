# Return request model — custom return management (not native Shopify)
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

RETURN_STATUSES = ["requested", "approved", "shipped", "received", "resolved", "rejected", "cancelled"]
RETURN_REASONS = [
    "defective", "wrong_item", "not_as_described", "changed_mind",
    "size_issue", "damaged_in_shipping", "late_delivery", "other",
]
RESOLUTION_TYPES = ["refund", "replacement"]

# Tag applied to Shopify order at each status
STATUS_TAGS = {
    "requested": "return-requested",
    "approved": "return-approved",
    "shipped": "return-shipped",
    "received": "return-received",
    "resolved_refund": "return-refunded",
    "resolved_replacement": "return-replaced",
    "rejected": "",
    "cancelled": "",
}
ALL_RETURN_TAGS = [v for v in STATUS_TAGS.values() if v]


class ReturnItem(BaseModel):
    line_item_id: str
    title: str
    variant_title: Optional[str] = None
    quantity: int
    price: str
    sku: Optional[str] = None


class StatusEntry(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor_type: str = "system"
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    note: Optional[str] = None


class ReturnCreate(BaseModel):
    order_id: str
    items: List[ReturnItem]
    reason: str
    reason_notes: Optional[str] = None
    resolution: str
    images: Optional[List[str]] = []  # customer-submitted image URLs (WhatsApp/chatbot)


class ReturnStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None


class ReturnTrackingUpdate(BaseModel):
    tracking_number: str
    courier: str  # e.g. "FedEx", "UPS", "DHL", "USPS", "BlueDart", "DTDC"
    warehouse_address: Optional[str] = None


class ReturnInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    order_number: Optional[int] = None
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    customer_id: Optional[str] = None
    items: List[Dict[str, Any]] = []
    reason: str
    reason_notes: Optional[str] = None
    resolution: str
    status: str = "requested"
    status_history: List[Dict[str, Any]] = []
    initiated_by: str = "admin"
    initiated_by_id: Optional[str] = None
    # Tracking
    tracking_number: Optional[str] = None
    courier: Optional[str] = None
    tracking_status: Optional[str] = None  # in_transit, delivered, failed, etc.
    tracking_last_checked: Optional[datetime] = None
    # Resolution
    resolved_at: Optional[datetime] = None
    refund_id: Optional[str] = None
    replacement_order_id: Optional[str] = None
    images: List[str] = []  # customer-submitted image URLs (WhatsApp/chatbot)
    return_tag: Optional[str] = None  # current tag on the Shopify order
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
