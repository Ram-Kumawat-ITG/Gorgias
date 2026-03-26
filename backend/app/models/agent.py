# Agent model — support agents who log in and handle tickets
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class AgentCreate(BaseModel):
    email: str
    full_name: str
    role: str = "agent"
    password: str


class AgentInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    full_name: str
    role: str = "agent"
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
