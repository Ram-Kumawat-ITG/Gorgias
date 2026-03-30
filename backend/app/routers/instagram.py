# Instagram webhook handler — receive DMs via Meta Graph API webhooks
# Setup:
#   1. Add META_APP_SECRET, META_VERIFY_TOKEN, META_PAGE_ACCESS_TOKEN to .env
#   2. In Meta Developer Console → Webhooks, subscribe to "messages" field
#   3. Set webhook URL to: https://<your-domain>/webhooks/instagram
import hashlib
import hmac
import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Query
from app.config import settings
from app.database import get_db
from app.models.ticket import TicketInDB
from app.models.message import MessageInDB
from app.services.activity_service import log_activity

router = APIRouter(prefix="/webhooks/instagram", tags=["Instagram"])


def _verify_meta_signature(body: bytes, signature_header: str) -> bool:
    """Verify X-Hub-Signature-256 sent by Meta on every webhook delivery."""
    if not settings.meta_app_secret:
        return True  # Skip in dev when secret not configured
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        settings.meta_app_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ── Webhook verification challenge (GET) ─────────────────────────────────────

@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Meta calls this endpoint (GET) when you register the webhook in the Developer Console.
    Respond with the challenge value to confirm ownership.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed — check META_VERIFY_TOKEN")


# ── Incoming DM / mention events (POST) ──────────────────────────────────────

@router.post("")
async def receive_event(request: Request):
    """
    Handle incoming Instagram DM events.
    Each event may contain multiple entries and messaging objects.
    Idempotency: open tickets from the same sender are re-used (messages appended).
    """
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_meta_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid Meta signature")

    payload = json.loads(body)
    db = get_db()

    for entry in payload.get("entry", []):
        # Instagram DMs come under "messaging"
        for event in entry.get("messaging", []):
            sender_id = (event.get("sender") or {}).get("id", "")
            recipient_id = (event.get("recipient") or {}).get("id", "")
            message_data = event.get("message") or {}
            message_text = message_data.get("text", "").strip()
            message_mid = message_data.get("mid", "")

            # Skip echo messages (sent by the page itself) and empty messages
            if message_data.get("is_echo") or not message_text or not sender_id:
                continue

            # Idempotency: don't process the same message_id twice
            if message_mid:
                dup = await db.tickets.find_one({"channel_meta.message_ids": message_mid})
                if dup:
                    continue

            # Check for an existing open/pending ticket from this sender
            existing = await db.tickets.find_one({
                "channel": "instagram",
                "channel_meta.sender_id": sender_id,
                "status": {"$in": ["open", "pending"]},
            })

            if existing:
                ticket_id = existing["id"]
                # Append message to existing thread
                msg = MessageInDB(
                    ticket_id=ticket_id,
                    body=message_text,
                    sender_type="customer",
                )
                await db.messages.insert_one(msg.model_dump())
                await db.tickets.update_one(
                    {"id": ticket_id},
                    {
                        "$set": {"updated_at": datetime.utcnow(), "status": "open"},
                        "$push": {"channel_meta.message_ids": message_mid},
                    },
                )
            else:
                # Create a new ticket for this Instagram sender
                ticket = TicketInDB(
                    subject=f"Instagram DM from {sender_id}",
                    customer_email=f"ig_{sender_id}@instagram.placeholder",
                    customer_name=f"Instagram User {sender_id[:8]}",
                    channel="instagram",
                    priority="normal",
                    tags=["instagram"],
                )
                ticket_doc = ticket.model_dump()
                ticket_doc["channel_meta"] = {
                    "platform": "instagram",
                    "sender_id": sender_id,
                    "page_id": recipient_id,
                    "message_ids": [message_mid] if message_mid else [],
                }
                await db.tickets.insert_one(ticket_doc)

                msg = MessageInDB(
                    ticket_id=ticket.id,
                    body=message_text,
                    sender_type="customer",
                )
                await db.messages.insert_one(msg.model_dump())

                await log_activity(
                    entity_type="ticket",
                    entity_id=ticket.id,
                    event="ticket.created",
                    actor_type="system",
                    description=f"Instagram DM received from sender {sender_id[:8]}",
                    customer_email=ticket_doc["customer_email"],
                    metadata={"platform": "instagram", "sender_id": sender_id},
                )

    return {"status": "ok"}
