# Activity log model — tracks every meaningful event across the system
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
import uuid


class ActivityLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_type: str  # ticket, order, customer, message
    entity_id: str
    customer_email: Optional[str] = None
    event: str  # e.g. ticket.created, order.fulfilled, sla.breached
    actor_type: str  # agent, customer, system, shopify
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    description: str
    metadata: Optional[Any] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
