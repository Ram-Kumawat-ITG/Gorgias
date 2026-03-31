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
    # Channel tracking for multi-channel replies
    channel: Optional[str] = None  # email, whatsapp, manual
    # WhatsApp-specific metadata
    whatsapp_message_id: Optional[str] = None
    whatsapp_status: Optional[str] = None  # sent, delivered, read, failed
    whatsapp_media_url: Optional[str] = None
    whatsapp_media_type: Optional[str] = None  # image, video, document, audio
    # Instagram-specific metadata
    instagram_message_id: Optional[str] = None
    instagram_status: Optional[str] = None  # sent, read
    instagram_media_url: Optional[str] = None
    instagram_media_type: Optional[str] = None  # image, video, audio, file
    instagram_sender_igsid: Optional[str] = None  # used for read-receipt tracking
    # Twitter-specific metadata
    twitter_message_id: Optional[str] = None   # DM event ID or tweet ID
    twitter_tweet_id: Optional[str] = None     # tweet ID (for mention replies)
    twitter_status: Optional[str] = None       # sent, failed
    twitter_media_url: Optional[str] = None
    twitter_media_type: Optional[str] = None   # photo, video, animated_gif
    twitter_type: Optional[str] = None         # dm or mention
    created_at: datetime = Field(default_factory=datetime.utcnow)
