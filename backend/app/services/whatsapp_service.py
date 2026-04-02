# WhatsApp Cloud API service — sends messages and verifies webhooks via Meta Graph API
import hashlib
import hmac
import httpx
from datetime import datetime, timedelta, timezone
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
    phone_number_id = config.get("phone_number_id", "")
    access_token = config.get("access_token", "")

    if not phone_number_id or not access_token:
        msg = f"WhatsApp not configured — phone_number_id={bool(phone_number_id)} access_token={bool(access_token)}"
        print(msg)
        return {"error": "not_configured", "detail": msg}

    # WhatsApp max message length is 4096 characters
    if len(text) > 4096:
        text = text[:4090] + "…"

    # Normalize phone number — remove leading + if present
    to_phone_clean = to_phone.lstrip("+")

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_clean,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15.0)

            # Always read the response body before raise_for_status
            # so we can log the actual Meta API error detail
            try:
                resp_body = r.json()
            except Exception:
                resp_body = {"raw": r.text}

            if r.status_code >= 400:
                error_detail = resp_body.get("error", {})
                error_msg = (
                    error_detail.get("message")
                    or error_detail.get("error_user_msg")
                    or str(resp_body)
                )
                print(
                    f"[WhatsApp] SEND FAILED to={to_phone_clean} "
                    f"status={r.status_code} error={error_msg} "
                    f"full_response={resp_body}"
                )
                return {"error": error_msg, "status_code": r.status_code, "meta_response": resp_body}

            print(f"[WhatsApp] SENT to={to_phone_clean} response={resp_body}")
            return resp_body

    except httpx.TimeoutException:
        print(f"[WhatsApp] TIMEOUT sending to {to_phone_clean}")
        return {"error": "timeout", "detail": "WhatsApp API timed out"}
    except Exception as e:
        print(f"[WhatsApp] NETWORK ERROR sending to {to_phone_clean}: {e}")
        return {"error": "network_error", "detail": str(e)}


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


async def send_interactive_buttons(
    to_phone: str,
    body_text: str,
    buttons: list,
    config: dict,
) -> dict:
    """Send a WhatsApp interactive reply-button message (max 3 buttons).

    buttons format: [{"id": "btn_id", "title": "Button Label"}, ...]
    Button title is capped at 20 chars; button id at 256 chars.
    """
    phone_number_id = config.get("phone_number_id", "")
    access_token = config.get("access_token", "")
    if not phone_number_id or not access_token:
        return {"error": "not_configured"}

    if len(body_text) > 1024:
        body_text = body_text[:1020] + "…"

    to_phone_clean = to_phone.lstrip("+")

    interactive: dict = {
        "type": "button",
        "body": {"text": body_text},
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": btn.get("id", f"btn_{i}")[:256],
                        "title": btn.get("title", "")[:20],
                    },
                }
                for i, btn in enumerate(buttons[:3])
            ]
        },
    }

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_clean,
        "type": "interactive",
        "interactive": interactive,
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15.0)
            try:
                resp_body = r.json()
            except Exception:
                resp_body = {"raw": r.text}
            if r.status_code >= 400:
                err = resp_body.get("error", {})
                print(
                    f"[WhatsApp] Interactive send FAILED to={to_phone_clean} "
                    f"status={r.status_code} error={err}"
                )
                return {"error": str(err), "status_code": r.status_code}
            print(f"[WhatsApp] Interactive SENT to={to_phone_clean}")
            return resp_body
    except Exception as e:
        print(f"[WhatsApp] Interactive message network error: {e}")
        return {"error": str(e)}


async def send_list_message(
    to_phone: str,
    body_text: str,
    button_label: str,
    sections: list,
    config: dict,
    header_text: str = "",
) -> dict:
    """Send a WhatsApp interactive list message (up to 10 items per section).

    sections format: [{"title": "Section Name", "rows": [{"id": "row_id", "title": "Row Title", "description": "Optional"}]}]
    button_label: the text on the button that opens the list (max 20 chars)
    """
    phone_number_id = config.get("phone_number_id", "")
    access_token = config.get("access_token", "")
    if not phone_number_id or not access_token:
        return {"error": "not_configured"}

    if len(body_text) > 1024:
        body_text = body_text[:1020] + "…"

    to_phone_clean = to_phone.lstrip("+")

    interactive: dict = {
        "type": "list",
        "body": {"text": body_text},
        "action": {
            "button": button_label[:20],
            "sections": [
                {
                    "title": sec.get("title", "Options")[:24],
                    "rows": [
                        {
                            "id": row.get("id", f"row_{i}")[:256],
                            "title": row.get("title", "")[:24],
                            **({"description": row["description"][:72]} if row.get("description") else {}),
                        }
                        for i, row in enumerate(sec.get("rows", [])[:10])
                    ],
                }
                for sec in sections[:10]
            ],
        },
    }

    if header_text:
        interactive["header"] = {"type": "text", "text": header_text[:60]}

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_clean,
        "type": "interactive",
        "interactive": interactive,
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15.0)
            try:
                resp_body = r.json()
            except Exception:
                resp_body = {"raw": r.text}
            if r.status_code >= 400:
                err = resp_body.get("error", {})
                print(
                    f"[WhatsApp] List message send FAILED to={to_phone_clean} "
                    f"status={r.status_code} error={err}"
                )
                return {"error": str(err), "status_code": r.status_code}
            print(f"[WhatsApp] List message SENT to={to_phone_clean}")
            return resp_body
    except Exception as e:
        print(f"[WhatsApp] List message network error: {e}")
        return {"error": str(e)}


async def send_image_with_buttons(
    to_phone: str,
    image_url: str,
    body_text: str,
    buttons: list,
    config: dict,
) -> dict:
    """Send an interactive message with an image header and reply buttons.
    Falls back to send_interactive_buttons if no image_url is given."""
    if not image_url:
        return await send_interactive_buttons(to_phone, body_text, buttons, config)

    phone_number_id = config.get("phone_number_id", "")
    access_token = config.get("access_token", "")
    if not phone_number_id or not access_token:
        return {"error": "not_configured"}

    if len(body_text) > 1024:
        body_text = body_text[:1020] + "…"

    to_phone_clean = to_phone.lstrip("+")

    interactive: dict = {
        "type": "button",
        "header": {"type": "image", "image": {"link": image_url}},
        "body": {"text": body_text},
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": btn.get("id", f"btn_{i}")[:256],
                        "title": btn.get("title", "")[:20],
                    },
                }
                for i, btn in enumerate(buttons[:3])
            ]
        },
    }

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_clean,
        "type": "interactive",
        "interactive": interactive,
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15.0)
            try:
                resp_body = r.json()
            except Exception:
                resp_body = {"raw": r.text}
            if r.status_code >= 400:
                err = resp_body.get("error", {})
                print(f"[WhatsApp] Image+buttons send FAILED to={to_phone_clean} status={r.status_code} error={err}")
                return {"error": str(err), "status_code": r.status_code}
            print(f"[WhatsApp] Image+buttons SENT to={to_phone_clean}")
            return resp_body
    except Exception as e:
        print(f"[WhatsApp] Image+buttons network error: {e}")
        return {"error": str(e)}


async def mark_as_read(message_id: str, config: dict):
    """Send read receipt for a WhatsApp message."""
    phone_number_id = config.get("phone_number_id", "")
    access_token = config.get("access_token", "")
    if not phone_number_id or not access_token:
        return

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
    return datetime.now(timezone.utc) - last_customer_msg_at < timedelta(hours=24)
