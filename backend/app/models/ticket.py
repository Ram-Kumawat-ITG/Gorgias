# Ticket data models — core entity for the helpdesk
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class TicketStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketType(str, Enum):
    REFUND = "refund"
    RETURN = "return"
    SHIPPING = "shipping"
    ORDER_STATUS = "order_status"
    BILLING = "billing"
    PRODUCT_INQUIRY = "product_inquiry"
    TECHNICAL = "technical"
    GENERAL = "general"


class TicketChannel(str, Enum):
    EMAIL = "email"
    MANUAL = "manual"
    SHOPIFY = "shopify"
    WHATSAPP = "whatsapp"
    CHAT = "chat"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"


class TicketCreate(BaseModel):
    subject: str
    customer_email: str
    customer_name: Optional[str] = None
    shopify_customer_id: Optional[str] = None
    channel: TicketChannel = TicketChannel.MANUAL
    priority: TicketPriority = TicketPriority.NORMAL
    tags: List[str] = []
    initial_message: Optional[str] = None


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[str] = None
    tags: Optional[List[str]] = None
    subject: Optional[str] = None
    ticket_type: Optional[str] = None


class TicketInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject: str
    customer_email: str
    customer_name: Optional[str] = None
    shopify_customer_id: Optional[str] = None
    merchant_id: Optional[str] = None
    channel: str = "email"
    status: str = "open"
    priority: str = "normal"
    ticket_type: str = "general"
    assignee_id: Optional[str] = None
    tags: List[str] = []
    sla_policy_id: Optional[str] = None
    sla_due_at: Optional[datetime] = None
    sla_status: str = "ok"
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    # WhatsApp-specific fields
    whatsapp_phone: Optional[str] = None
    whatsapp_conversation_id: Optional[str] = None
    whatsapp_last_customer_msg_at: Optional[datetime] = None  # tracks 24-hour window
    # Instagram-specific fields
    instagram_user_id: Optional[str] = None  # sender's IGSID
    instagram_username: Optional[str] = None  # display name
    instagram_last_customer_msg_at: Optional[datetime] = None  # tracks 24-hour window
    # Twitter-specific fields
    twitter_sender_id: Optional[str] = None  # Twitter user ID of the customer
    twitter_username: Optional[str] = None   # @handle of the customer
    twitter_type: Optional[str] = None       # "dm" or "mention"
    twitter_last_tweet_id: Optional[str] = None  # last tweet/DM id for threading
    # Shopify order link (latest order at ticket creation time)
    shopify_order_id: Optional[str] = None
    shopify_order_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
