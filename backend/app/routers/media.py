from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.database import get_db
from app.services.whatsapp_service import get_whatsapp_config, download_media
import httpx

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

router = APIRouter(prefix="/media", tags=["Media"])


async def _fetch_media_bytes(url: str, access_token: str) -> tuple:
    """Fetch media binary from a URL with auth. Returns (response, content_type) or raises."""
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "application/octet-stream")
        return r, content_type


@router.get("/whatsapp/{message_id}")
async def proxy_whatsapp_media(message_id: str):
    """Proxy WhatsApp media so the browser can display it without Meta auth.

    Strategy:
    1. If the message has a whatsapp_media_id → re-fetch the download URL from Meta
       (the original URL expires within minutes, so we always get a fresh one).
    2. Fall back to the stored whatsapp_media_url if no media_id is available.
    """
    db = get_db()
    msg = await db.messages.find_one({"id": message_id})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    wa_media_id = msg.get("whatsapp_media_id")
    wa_url = msg.get("whatsapp_media_url")

    if not wa_media_id and not wa_url:
        raise HTTPException(status_code=404, detail="No WhatsApp media for this message")

    # Determine merchant config via ticket
    ticket = await db.tickets.find_one({"id": msg.get("ticket_id")}) if msg.get("ticket_id") else None
    merchant_id = ticket.get("merchant_id") if ticket else None
    config = await get_whatsapp_config(merchant_id)
    access_token = config.get("access_token")

    try:
        # Strategy 1: Re-fetch fresh download URL using media_id
        if wa_media_id and access_token:
            fresh_url = await download_media(wa_media_id, config)
            if fresh_url:
                r, content_type = await _fetch_media_bytes(fresh_url, access_token)
                return StreamingResponse(r.aiter_bytes(), media_type=content_type)

        # Strategy 2: Try the stored URL (may still work if recent)
        if wa_url:
            r, content_type = await _fetch_media_bytes(wa_url, access_token)
            return StreamingResponse(r.aiter_bytes(), media_type=content_type)

        raise HTTPException(status_code=502, detail="Could not fetch media from Meta")

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Upstream media fetch failed: {e.response.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
