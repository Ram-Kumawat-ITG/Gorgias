# Automation rule model — if-then rules that auto-tag, assign, or reply to tickets
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class AutomationRuleCreate(BaseModel):
    name: str
    trigger_event: str  # ticket.created, message.received, sla.breached
    conditions: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    stop_processing: bool = False
    priority: int = 0
    is_active: bool = True


class AutomationRuleInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    trigger_event: str
    conditions: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    stop_processing: bool = False
    priority: int = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
