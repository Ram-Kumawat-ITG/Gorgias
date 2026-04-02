# Instagram Messenger API service — sends DMs via Meta Graph API
import hashlib
import hmac
import httpx
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.database import get_db

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


async def get_instagram_config(merchant_id: str = None) -> dict:
    """Get Instagram config — merchant-specific first, then fall back to global .env."""
    if merchant_id:
        db = get_db()
        merchant = await db.merchants.find_one({"id": merchant_id, "is_active": True})
        if merchant and merchant.get("instagram_page_id"):
            return {
                "page_id": merchant["instagram_page_id"],
                "access_token": merchant["instagram_access_token"],
                "app_secret": merchant["instagram_app_secret"],
                "verify_token": merchant["instagram_verify_token"],
            }
    return {
        "page_id": settings.instagram_page_id,
        "access_token": settings.instagram_access_token,
        "app_secret": settings.instagram_app_secret,
        "verify_token": settings.instagram_verify_token,
    }


async def send_text_message(to_igsid: str, text: str, config: dict) -> dict:
    """Send a text message to an Instagram user via Messenger API."""
    page_id = config["page_id"]
    access_token = config["access_token"]

    if not page_id or not access_token:
        print("Instagram not configured — skipping message send")
        return {"error": "not_configured"}

    url = f"{GRAPH_API_BASE}/{page_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"id": to_igsid},
        "message": {"text": text},
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15.0)
            r.raise_for_status()
            data = r.json()
            print(f"Instagram message sent to {to_igsid}: {data}")
            return data
    except Exception as e:
        print(f"Instagram send failed: {e}")
        return {"error": str(e)}


async def mark_as_seen(sender_igsid: str, config: dict):
    """Send seen receipt to an Instagram user."""
    page_id = config["page_id"]
    access_token = config["access_token"]

    url = f"{GRAPH_API_BASE}/{page_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"id": sender_igsid},
        "sender_action": "mark_seen",
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=10.0)
    except Exception as e:
        print(f"Instagram mark_as_seen failed: {e}")


def verify_webhook_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    """Validate Meta's X-Hub-Signature-256 header."""
    if not signature or not app_secret:
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def is_within_24h_window(last_customer_msg_at: datetime) -> bool:
    """Check if we're still within the 24-hour free-form messaging window."""
    if not last_customer_msg_at:
        return False
    return datetime.now(timezone.utc) - last_customer_msg_at < timedelta(hours=24)
