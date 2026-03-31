# WhatsApp webhook router — handles Meta webhook verification and inbound messages
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime
from app.config import settings
from app.database import get_db
from app.services.whatsapp_service import (
    verify_webhook_signature,
    get_whatsapp_config,
    mark_as_read,
    download_media,
)
from app.services.activity_service import log_activity

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp"])


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification — responds with hub.challenge if token matches."""
    if hub_mode == "subscribe":
        # Check global config first
        global_token = settings.whatsapp_verify_token
        if global_token and hub_verify_token == global_token:
            return PlainTextResponse(content=hub_challenge)

        # Always fall through to merchant lookup — covers both "no global token" and
        # "global token set but this webhook is for a different (merchant) WABA"
        db = get_db()
        merchant = await db.merchants.find_one(
            {"whatsapp_verify_token": hub_verify_token, "is_active": True}
        )
        if merchant:
            return PlainTextResponse(content=hub_challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/test")
async def test_connection(request: Request):
    """Test WhatsApp API connection by verifying credentials are valid."""
    import httpx
    body = await request.json()
    merchant_id = body.get("merchant_id")

    # Use inline credentials if provided (e.g. validating before save),
    # otherwise fall back to the stored config for this merchant.
    phone_number_id = body.get("phone_number_id") or ""
    access_token = body.get("access_token") or ""

    if not phone_number_id or not access_token:
        config = await get_whatsapp_config(merchant_id)
        phone_number_id = phone_number_id or config.get("phone_number_id", "")
        access_token = access_token or config.get("access_token", "")

    if not phone_number_id or not access_token:
        raise HTTPException(status_code=400, detail="WhatsApp credentials not configured")

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://graph.facebook.com/v21.0/{phone_number_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "status": "connected",
                "phone_number": data.get("display_phone_number", ""),
                "quality_rating": data.get("quality_rating", ""),
                "verified_name": data.get("verified_name", ""),
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"WhatsApp API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@router.post("")
async def receive_webhook(request: Request):
    """Receive inbound WhatsApp messages and status updates from Meta."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Verify signature — try global secret first, then merchant-specific secret.
    # Only hard-reject when a secret IS configured but the signature doesn't match.
    if signature:
        global_secret = settings.whatsapp_app_secret
        sig_ok = bool(global_secret) and verify_webhook_signature(body, signature, global_secret)

        if not sig_ok:
            # Parse payload to find phone_number_id → look up merchant secret
            import json as _json
            try:
                _temp = _json.loads(body)
                _phone_id = (
                    _temp.get("entry", [{}])[0]
                    .get("changes", [{}])[0]
                    .get("value", {})
                    .get("metadata", {})
                    .get("phone_number_id", "")
                )
                if _phone_id:
                    _db = get_db()
                    _merchant = await _db.merchants.find_one(
                        {"whatsapp_phone_number_id": _phone_id, "is_active": True}
                    )
                    if _merchant and _merchant.get("whatsapp_app_secret"):
                        sig_ok = verify_webhook_signature(body, signature, _merchant["whatsapp_app_secret"])
            except Exception:
                pass

        # Reject only if a secret was configured but the signature didn't match
        if not sig_ok and global_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Meta sends webhook data in entry[].changes[].value
    entries = payload.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Handle incoming messages
            if "messages" in value:
                await _handle_messages(value)

            # Handle message status updates (sent/delivered/read)
            if "statuses" in value:
                await _handle_statuses(value)

    return {"status": "ok"}


async def _handle_messages(value: dict):
    """Process incoming customer messages."""
    db = get_db()
    metadata = value.get("metadata", {})
    phone_number_id = metadata.get("phone_number_id", "")

    # Find merchant by phone_number_id
    merchant = await db.merchants.find_one(
        {"whatsapp_phone_number_id": phone_number_id, "is_active": True}
    )
    merchant_id = merchant["id"] if merchant else None

    contacts = value.get("contacts", [])
    messages = value.get("messages", [])

    for msg in messages:
        wa_message_id = msg.get("id", "")
        from_phone = msg.get("from", "")  # customer's phone number
        msg_type = msg.get("type", "text")
        timestamp = msg.get("timestamp", "")

        # Extract message body based on type
        body = ""
        media_url = ""
        media_type = ""

        if msg_type == "text":
            body = msg.get("text", {}).get("body", "")
        elif msg_type in ("image", "video", "document", "audio"):
            media_obj = msg.get(msg_type, {})
            body = media_obj.get("caption", f"[{msg_type} received]")
            media_id = media_obj.get("id", "")
            media_type = msg_type
            if media_id:
                config = await get_whatsapp_config(merchant_id)
                media_url = await download_media(media_id, config)
        elif msg_type == "location":
            loc = msg.get("location", {})
            body = f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"
        elif msg_type == "contacts":
            body = "[Contact card received]"
        elif msg_type == "sticker":
            body = "[Sticker received]"
        else:
            body = f"[{msg_type} message received]"

        # Get contact name
        contact_name = ""
        for c in contacts:
            if c.get("wa_id") == from_phone:
                profile = c.get("profile", {})
                contact_name = profile.get("name", "")
                break

        # Mark as read
        try:
            config = await get_whatsapp_config(merchant_id)
            await mark_as_read(wa_message_id, config)
        except Exception:
            pass

        # Create or update ticket via ticket_service
        from app.services.ticket_service import create_ticket_from_whatsapp
        await create_ticket_from_whatsapp(
            phone=from_phone,
            customer_name=contact_name,
            message_body=body,
            wa_message_id=wa_message_id,
            media_url=media_url,
            media_type=media_type,
            merchant_id=merchant_id,
        )


async def _handle_statuses(value: dict):
    """Process message delivery status updates (sent/delivered/read/failed)."""
    db = get_db()
    statuses = value.get("statuses", [])

    for status in statuses:
        wa_message_id = status.get("id", "")
        status_value = status.get("status", "")  # sent, delivered, read, failed

        if wa_message_id:
            await db.messages.update_one(
                {"whatsapp_message_id": wa_message_id},
                {"$set": {"whatsapp_status": status_value}},
            )

            # Log failures
            if status_value == "failed":
                errors = status.get("errors", [])
                error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
                print(f"WhatsApp message {wa_message_id} failed: {error_msg}")
