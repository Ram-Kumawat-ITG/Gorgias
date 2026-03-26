# SLA policy model — defines response and resolution time targets by priority
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class SLAPolicyCreate(BaseModel):
    name: str
    priority: str
    first_response_hours: float
    resolution_hours: float
    applies_to_channels: List[str] = ["email", "manual"]
    is_active: bool = True


class SLAPolicyInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    priority: str
    first_response_hours: float
    resolution_hours: float
    applies_to_channels: List[str] = ["email", "manual"]
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
