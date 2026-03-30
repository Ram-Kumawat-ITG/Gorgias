# Mailgun inbound email handler — creates tickets from incoming support emails
import hashlib
import hmac
import time
from fastapi import APIRouter, Request, HTTPException
from app.config import settings
from app.services.ticket_service import create_ticket_from_email
from app.database import get_db

router = APIRouter(prefix="/webhooks/email", tags=["Email"])


def _verify_mailgun_signature(token: str, timestamp: str, signature: str) -> bool:
    """Verify Mailgun webhook signature using HMAC-SHA256."""
    if not settings.mailgun_webhook_signing_key:
        return True  # Skip verification when key not configured (dev mode)
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:  # reject stale requests older than 5 minutes
            return False
    except (ValueError, TypeError):
        return False
    expected = hmac.new(
        settings.mailgun_webhook_signing_key.encode("utf-8"),
        (timestamp + token).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/inbound")
async def inbound_email(request: Request):
    form = await request.form()
    sender = form.get("sender", "")
    subject = form.get("subject", "No Subject")
    body = form.get("stripped-text") or form.get("body-plain", "")
    recipient = form.get("recipient", "")

    # Signature verification — enforced only when signing key is configured
    token = form.get("token", "")
    timestamp = form.get("timestamp", "")
    signature = form.get("signature", "")
    if settings.mailgun_webhook_signing_key and not _verify_mailgun_signature(token, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid Mailgun signature")

    if not body or not body.strip():
        return {"status": "skipped", "reason": "empty body"}

    # Identify merchant by recipient email
    merchant_id = None
    db = get_db()
    if recipient:
        merchant = await db.merchants.find_one({"support_email": recipient, "is_active": True})
        if merchant:
            merchant_id = merchant["id"]

    ticket = await create_ticket_from_email(
        customer_email=sender,
        subject=subject,
        body=body.strip(),
        merchant_id=merchant_id,
    )
    return {"status": "received", "ticket_id": ticket.get("id")}
