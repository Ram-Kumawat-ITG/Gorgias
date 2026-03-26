# Macro model — canned response templates with Jinja2 variables
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class MacroCreate(BaseModel):
    name: str
    body: str
    tags: List[str] = []
    actions: List[Dict[str, Any]] = []


class MacroInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    body: str  # Jinja2 template string
    tags: List[str] = []
    actions: List[Dict[str, Any]] = []
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
