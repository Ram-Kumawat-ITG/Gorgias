# Twitter webhook router — handles CRC verification and Account Activity API events
from fastapi import APIRouter, Request, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import get_db
from app.services.twitter_service import get_twitter_config, verify_crc, _build_oauth1_header, register_webhook

twitter_router = APIRouter(prefix="/twitter", tags=["Twitter"])
webhook_router = APIRouter(prefix="/webhooks/twitter", tags=["Twitter Webhooks"])


@webhook_router.get("")
async def crc_challenge(crc_token: str = Query(None)):
    """Twitter CRC challenge — called by Twitter to verify the webhook URL."""
    if not crc_token:
        return JSONResponse(
            content={"status": "Twitter webhook endpoint is active. Awaiting CRC challenge from Twitter."},
            status_code=200,
        )

    consumer_secret = settings.twitter_api_secret or ""
    if not consumer_secret:
        try:
            db = get_db()
            if db is not None:
                merchant = await db.merchants.find_one(
                    {"twitter_api_secret": {"$exists": True, "$ne": ""}, "is_active": True}
                )
                if merchant:
                    consumer_secret = merchant.get("twitter_api_secret") or ""
        except Exception as e:
            print(f"Twitter CRC — DB lookup failed: {e}")

    if not consumer_secret:
        print("Twitter CRC challenge failed: twitter_api_secret not configured.")
        raise HTTPException(
            status_code=500,
            detail="Twitter API Secret not configured. Save credentials first.",
        )

    try:
        response_token = verify_crc(crc_token, consumer_secret)
        return JSONResponse(content={"response_token": response_token})
    except Exception as e:
        print(f"Twitter CRC computation error: {e}")
        raise HTTPException(status_code=500, detail=f"CRC computation failed: {str(e)}")


@twitter_router.post("/register-webhook")
async def register_twitter_webhook(
    merchant_id: str,
    webhook_url: str = Body(embed=True)
):
    result = await register_webhook(webhook_url, merchant_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@twitter_router.post("/test")
async def test_connection(request: Request):
    """Test Twitter API connection with OAuth 1.0a User Context (required for webhooks)."""
    import httpx
    body = await request.json()
    merchant_id = body.get("merchant_id")
    config = await get_twitter_config(merchant_id)

    # Validate User Context credentials required for webhooks
    required_creds = ["api_key", "api_secret", "access_token", "access_token_secret"]
    missing = [cred for cred in required_creds if not config.get(cred)]
    if missing:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing Twitter credentials: {', '.join(missing)}. Generate Access Token/Secret in Developer Portal."
        )

    url = "https://api.twitter.com/2/users/me"
    auth_header = _build_oauth1_header("GET", url, {}, config)

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                url,
                headers={"Authorization": auth_header},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            user = data.get("data", {})
            return {
                "status": "connected",
                "username": user.get("username", ""),
                "name": user.get("name", ""),
                "id": user.get("id", ""),
                "message": "OAuth 1.0a User Context verified - Webhook-ready!"
            }
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if e.response.text else str(e)
        raise HTTPException(status_code=400, detail=f"Twitter API error: {error_detail}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@webhook_router.post("")
async def receive_webhook(request: Request):
    """Receive Twitter Account Activity API events (DMs and @mentions)."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Handle Direct Message events
    if "direct_message_events" in payload:
        await _handle_dm_events(payload)

    # Handle @mention / tweet events
    if "tweet_create_events" in payload:
        await _handle_tweet_events(payload)

    return {"status": "ok"}


async def _handle_dm_events(payload: dict):
    """Process incoming Twitter DM events from Account Activity API."""
    events = payload.get("direct_message_events", [])
    users = payload.get("users", {})  # {user_id: user_object} lookup map
    for_user_id = payload.get("for_user_id", "")  # Our Twitter account's user ID

    for event in events:
        # Only handle message_create events (not read receipts etc.)
        if event.get("type") != "message_create":
            continue

        msg_create = event.get("message_create", {})
        sender_id = msg_create.get("sender_id", "")

        # Skip messages sent by the account itself (outbound)
        if sender_id == for_user_id:
            continue

        message_data = msg_create.get("message_data", {})
        text = message_data.get("text", "")
        tw_message_id = event.get("id", "")

        # Extract media attachment if present
        media_url = ""
        media_type = ""
        attachment = message_data.get("attachment", {})
        if attachment.get("type") == "media":
            media = attachment.get("media", {})
            media_type = media.get("type", "")  # photo, video, animated_gif
            media_url = media.get("media_url_https", "")

        # Get sender info from users lookup
        sender_info = users.get(sender_id, {})
        sender_name = sender_info.get("name", "")
        sender_handle = sender_info.get("screen_name", "")

        merchant_id = await _find_merchant_by_for_user_id(for_user_id)

        from app.services.ticket_service import create_ticket_from_twitter
        await create_ticket_from_twitter(
            twitter_sender_id=sender_id,
            sender_name=sender_name,
            sender_handle=sender_handle,
            message_body=text,
            tw_message_id=tw_message_id,
            twitter_type="dm",
            media_url=media_url,
            media_type=media_type,
            merchant_id=merchant_id,
        )


async def _handle_tweet_events(payload: dict):
    """Process incoming @mention tweet events from Account Activity API."""
    events = payload.get("tweet_create_events", [])
    for_user_id = payload.get("for_user_id", "")

    for tweet in events:
        user = tweet.get("user", {})
        sender_id = str(user.get("id_str", ""))

        # Skip retweets and our own tweets
        if tweet.get("retweeted_status") or sender_id == for_user_id:
            continue

        tweet_id = tweet.get("id_str", "")
        # Use full_text if available (extended tweets), otherwise text
        text = tweet.get("full_text", tweet.get("text", ""))
        sender_name = user.get("name", "")
        sender_handle = user.get("screen_name", "")

        # Extract first media attachment if present
        media_url = ""
        media_type = ""
        entities = tweet.get("extended_entities", tweet.get("entities", {}))
        media_list = entities.get("media", [])
        if media_list:
            first_media = media_list[0]
            media_type = first_media.get("type", "")
            media_url = first_media.get("media_url_https", "")

        merchant_id = await _find_merchant_by_for_user_id(for_user_id)

        from app.services.ticket_service import create_ticket_from_twitter
        await create_ticket_from_twitter(
            twitter_sender_id=sender_id,
            sender_name=sender_name,
            sender_handle=sender_handle,
            message_body=text,
            tw_message_id=tweet_id,
            twitter_type="mention",
            media_url=media_url,
            media_type=media_type,
            merchant_id=merchant_id,
        )


async def _find_merchant_by_for_user_id(for_user_id: str):
    """Find the merchant whose Twitter account has the given user ID."""
    if not for_user_id:
        return None
    db = get_db()
    merchant = await db.merchants.find_one(
        {"twitter_user_id": for_user_id, "is_active": True}
    )
    return merchant["id"] if merchant else None
