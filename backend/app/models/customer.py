# Customer model — synced from Shopify and cached in MongoDB
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class CustomerInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    shopify_customer_id: Optional[str] = None
    total_spent: str = "0.00"
    orders_count: int = 0
    tags: List[str] = []
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
