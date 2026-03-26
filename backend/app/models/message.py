# Message model — individual messages within a ticket thread
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class MessageCreate(BaseModel):
    body: str
    sender_type: str = "agent"
    is_internal_note: bool = False
    ai_generated: bool = False


class MessageInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ticket_id: str
    body: str
    sender_type: str  # customer, agent, ai, system
    sender_id: Optional[str] = None
    is_internal_note: bool = False
    ai_generated: bool = False
    attachments: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
