# Instagram webhook router — handles Meta webhook verification and inbound DMs
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime
from app.config import settings
from app.database import get_db
from app.services.instagram_service import (
    verify_webhook_signature,
    get_instagram_config,
    mark_as_seen,
)
from app.services.activity_service import log_activity

router = APIRouter(prefix="/webhooks/instagram", tags=["Instagram"])


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification — responds with hub.challenge if token matches."""
    if hub_mode == "subscribe":
        verify_token = settings.instagram_verify_token
        if not verify_token:
            db = get_db()
            merchant = await db.merchants.find_one(
                {"instagram_verify_token": hub_verify_token, "is_active": True}
            )
            if merchant:
                return PlainTextResponse(content=hub_challenge)
            raise HTTPException(status_code=403, detail="Invalid verify token")

        if hub_verify_token == verify_token:
            return PlainTextResponse(content=hub_challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/test")
async def test_connection(request: Request):
    """Test Instagram API connection by verifying credentials are valid."""
    import httpx
    body = await request.json()
    merchant_id = body.get("merchant_id")
    config = await get_instagram_config(merchant_id)

    page_id = config.get("page_id", "")
    access_token = config.get("access_token", "")

    if not page_id or not access_token:
        raise HTTPException(status_code=400, detail="Instagram credentials not configured")

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://graph.facebook.com/v21.0/{page_id}",
                params={"fields": "id,name,instagram_business_account", "access_token": access_token},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "status": "connected",
                "page_name": data.get("name", ""),
                "page_id": data.get("id", ""),
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Instagram API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@router.post("")
async def receive_webhook(request: Request):
    """Receive inbound Instagram DMs and read receipts from Meta."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Verify signature — try global config first
    app_secret = settings.instagram_app_secret
    if app_secret and not verify_webhook_signature(body, signature, app_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Instagram sends data in entry[].messaging[]
    entries = payload.get("entry", [])
    for entry in entries:
        page_id = entry.get("id", "")
        for messaging in entry.get("messaging", []):
            if "message" in messaging:
                await _handle_message(messaging, page_id)
            elif "read" in messaging:
                await _handle_read(messaging)

    return {"status": "ok"}


async def _handle_message(messaging: dict, page_id: str):
    """Process incoming Instagram DM."""
    db = get_db()

    # Find merchant by instagram_page_id
    merchant = await db.merchants.find_one(
        {"instagram_page_id": page_id, "is_active": True}
    )
    merchant_id = merchant["id"] if merchant else None

    sender_igsid = messaging.get("sender", {}).get("id", "")
    msg_obj = messaging.get("message", {})
    ig_message_id = msg_obj.get("mid", "")
    timestamp = messaging.get("timestamp", "")

    # Skip echo messages (messages sent by the page itself)
    if msg_obj.get("is_echo"):
        return

    # Extract message content
    body = ""
    media_url = ""
    media_type = ""

    if "text" in msg_obj:
        body = msg_obj["text"]
    elif "attachments" in msg_obj:
        attachments = msg_obj["attachments"]
        if attachments:
            att = attachments[0]
            media_type = att.get("type", "")
            media_url = att.get("payload", {}).get("url", "")
            body = f"[{media_type} received]"

    if not body and not media_url:
        body = "[message received]"

    # Mark as seen
    try:
        config = await get_instagram_config(merchant_id)
        await mark_as_seen(sender_igsid, config)
    except Exception:
        pass

    # Create or update ticket
    from app.services.ticket_service import create_ticket_from_instagram
    ticket = await create_ticket_from_instagram(
        igsid=sender_igsid,
        message_body=body,
        ig_message_id=ig_message_id,
        media_url=media_url,
        media_type=media_type,
        merchant_id=merchant_id,
    )

    # Run AI Sales Agent and auto-reply
    try:
        from app.services.instagram_sales_agent_service import process_instagram_message
        from app.services.instagram_service import send_text_message
        config = await get_instagram_config(merchant_id)
        reply_text = await process_instagram_message(
            igsid=sender_igsid,
            ticket_id=ticket["id"],
            message_body=body,
        )
        await send_text_message(sender_igsid, reply_text, config)
    except Exception as agent_err:
        print(f"Instagram AI agent error for {sender_igsid}: {agent_err}")


async def _handle_read(messaging: dict):
    """Process Instagram read receipt — update message status."""
    db = get_db()
    sender_igsid = messaging.get("sender", {}).get("id", "")
    watermark = messaging.get("read", {}).get("watermark", 0)

    if sender_igsid:
        # Mark all agent messages to this user as read (up to watermark timestamp)
        await db.messages.update_many(
            {
                "instagram_sender_igsid": sender_igsid,
                "sender_type": "agent",
                "instagram_status": {"$in": ["sent", "delivered"]},
            },
            {"$set": {"instagram_status": "read"}},
        )