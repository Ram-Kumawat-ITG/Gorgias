# Ticket data models — core entity for the helpdesk
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class TicketStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketChannel(str, Enum):
    EMAIL = "email"
    MANUAL = "manual"


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


class TicketInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject: str
    customer_email: str
    customer_name: Optional[str] = None
    shopify_customer_id: Optional[str] = None
    channel: str = "email"
    status: str = "open"
    priority: str = "normal"
    assignee_id: Optional[str] = None
    tags: List[str] = []
    sla_policy_id: Optional[str] = None
    sla_due_at: Optional[datetime] = None
    sla_status: str = "ok"
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
