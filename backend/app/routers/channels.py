# Channels router — manage and list available sales/support channels
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.routers.auth import get_current_agent
from app.database import get_db

router = APIRouter(prefix="/channels", tags=["Channels"])

# Default channels seeded on first request if the collection is empty
_DEFAULT_CHANNELS = [
    {"id": "all",      "name": "All Channels", "value": "",         "icon": "all",       "order": 0, "enabled": True},
    {"id": "shopify",  "name": "Shopify",       "value": "shopify",  "icon": "shopify",   "order": 1, "enabled": True},
    {"id": "email",    "name": "Email",          "value": "email",    "icon": "email",     "order": 2, "enabled": True},
    {"id": "manual",   "name": "Manual",         "value": "manual",   "icon": "manual",    "order": 3, "enabled": True},
    {"id": "whatsapp", "name": "WhatsApp",       "value": "whatsapp", "icon": "whatsapp",  "order": 4, "enabled": True},
    {"id": "chat",     "name": "Live Chat",      "value": "chat",     "icon": "chat",      "order": 5, "enabled": True},
]


async def _ensure_seeded(db):
    """Seed default channels if the collection is empty."""
    count = await db.channels.count_documents({})
    if count == 0:
        await db.channels.insert_many([dict(c) for c in _DEFAULT_CHANNELS])


async def _sync_from_tickets(db, existing_values: set):
    """
    Discover any channel values present in tickets that are not yet in the
    channels collection and add them automatically.  This makes the system
    self-extending: new integrations that write tickets with a new channel value
    will surface as a tab without any manual code change.
    """
    distinct_channels = await db.tickets.distinct("channel")
    new_channels = []
    max_order_doc = await db.channels.find_one(sort=[("order", -1)])
    next_order = (max_order_doc["order"] + 1) if max_order_doc else len(_DEFAULT_CHANNELS)

    for ch in distinct_channels:
        if ch and ch not in existing_values:
            new_channels.append({
                "id": ch,
                "name": ch.replace("_", " ").title(),
                "value": ch,
                "icon": ch,
                "order": next_order,
                "enabled": True,
            })
            next_order += 1

    if new_channels:
        await db.channels.insert_many(new_channels)


@router.get("")
async def list_channels(agent=Depends(get_current_agent)):
    """Return all enabled channels, ordered. Seeds defaults + auto-discovers new ones from tickets."""
    db = get_db()
    await _ensure_seeded(db)

    channels = await db.channels.find(
        {"enabled": True}, {"_id": 0}
    ).sort("order", 1).to_list(200)

    existing_values = {c["value"] for c in channels}
    await _sync_from_tickets(db, existing_values)

    # Re-fetch after potential sync
    channels = await db.channels.find(
        {"enabled": True}, {"_id": 0}
    ).sort("order", 1).to_list(200)

    return {"channels": channels}


class ChannelPayload(BaseModel):
    name: str
    value: str
    icon: Optional[str] = None
    order: Optional[int] = None
    enabled: bool = True


@router.post("")
async def create_channel(data: ChannelPayload, agent=Depends(get_current_agent)):
    """Add a new sales channel (e.g. Instagram, Telegram)."""
    db = get_db()
    await _ensure_seeded(db)

    existing = await db.channels.find_one({"value": data.value})
    if existing:
        raise HTTPException(status_code=400, detail=f"Channel '{data.value}' already exists")

    if data.order is None:
        max_doc = await db.channels.find_one(sort=[("order", -1)])
        data_order = (max_doc["order"] + 1) if max_doc else 10
    else:
        data_order = data.order

    channel = {
        "id": data.value,
        "name": data.name,
        "value": data.value,
        "icon": data.icon or data.value,
        "order": data_order,
        "enabled": data.enabled,
    }
    await db.channels.insert_one(channel)
    channel.pop("_id", None)
    return channel


@router.patch("/{channel_id}")
async def update_channel(channel_id: str, data: ChannelPayload, agent=Depends(get_current_agent)):
    """Enable/disable or rename a channel."""
    db = get_db()
    result = await db.channels.update_one(
        {"id": channel_id},
        {"$set": {k: v for k, v in data.model_dump().items() if v is not None}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Channel not found")
    updated = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    return updated
