# WhatsApp Cloud API service — sends messages and verifies webhooks via Meta Graph API
import hashlib
import hmac
import httpx
from datetime import datetime, timedelta
from app.config import settings
from app.database import get_db

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


async def get_whatsapp_config(merchant_id: str = None) -> dict:
    """Get WhatsApp config — merchant-specific first, then fall back to global .env."""
    if merchant_id:
        db = get_db()
        merchant = await db.merchants.find_one({"id": merchant_id, "is_active": True})
        if merchant and merchant.get("whatsapp_phone_number_id"):
            return {
                "phone_number_id": merchant["whatsapp_phone_number_id"],
                "access_token": merchant["whatsapp_access_token"],
                "app_secret": merchant["whatsapp_app_secret"],
                "waba_id": merchant["whatsapp_waba_id"],
                "verify_token": merchant["whatsapp_verify_token"],
            }
    return {
        "phone_number_id": settings.whatsapp_phone_number_id,
        "access_token": settings.whatsapp_access_token,
        "app_secret": settings.whatsapp_app_secret,
        "waba_id": settings.whatsapp_waba_id,
        "verify_token": settings.whatsapp_verify_token,
    }


async def send_text_message(to_phone: str, text: str, config: dict) -> dict:
    """Send a free-form text message to a WhatsApp number."""
    phone_number_id = config["phone_number_id"]
    access_token = config["access_token"]

    if not phone_number_id or not access_token:
        print("WhatsApp not configured — skipping message send")
        return {"error": "not_configured"}

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15.0)
            r.raise_for_status()
            data = r.json()
            print(f"WhatsApp message sent to {to_phone}: {data}")
            return data
    except Exception as e:
        print(f"WhatsApp send failed: {e}")
        return {"error": str(e)}


async def send_template_message(
    to_phone: str,
    template_name: str,
    language_code: str,
    components: list,
    config: dict,
) -> dict:
    """Send a pre-approved template message (for outside 24-hour window)."""
    phone_number_id = config["phone_number_id"]
    access_token = config["access_token"]

    if not phone_number_id or not access_token:
        print("WhatsApp not configured — skipping template send")
        return {"error": "not_configured"}

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components,
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15.0)
            r.raise_for_status()
            data = r.json()
            print(f"WhatsApp template sent to {to_phone}: {data}")
            return data
    except Exception as e:
        print(f"WhatsApp template send failed: {e}")
        return {"error": str(e)}


async def send_media_message(
    to_phone: str,
    media_type: str,
    media_url: str,
    caption: str,
    config: dict,
) -> dict:
    """Send media (image/document/video/audio) via WhatsApp."""
    phone_number_id = config["phone_number_id"]
    access_token = config["access_token"]

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    media_obj = {"link": media_url}
    if caption and media_type in ("image", "video", "document"):
        media_obj["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": media_type,
        media_type: media_obj,
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15.0)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"WhatsApp media send failed: {e}")
        return {"error": str(e)}


async def download_media(media_id: str, config: dict) -> str:
    """Download media from WhatsApp — returns the media URL for download."""
    access_token = config["access_token"]
    url = f"{GRAPH_API_BASE}/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, timeout=10.0)
            r.raise_for_status()
            data = r.json()
            return data.get("url", "")
    except Exception as e:
        print(f"WhatsApp media download failed: {e}")
        return ""


async def mark_as_read(message_id: str, config: dict):
    """Send read receipt for a WhatsApp message."""
    phone_number_id = config["phone_number_id"]
    access_token = config["access_token"]

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=10.0)
    except Exception as e:
        print(f"WhatsApp mark_as_read failed: {e}")


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
    return datetime.utcnow() - last_customer_msg_at < timedelta(hours=24)
