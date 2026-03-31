from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.database import get_db
from app.services.whatsapp_service import get_whatsapp_config
import httpx

router = APIRouter(prefix="/media", tags=["Media"])


@router.get("/whatsapp/{message_id}")
async def proxy_whatsapp_media(message_id: str):
    """Proxy WhatsApp media URLs so the browser can fetch them without Meta auth.

    Looks up the message by id, finds whatsapp_media_url and the ticket merchant_id,
    then performs a server-side GET to the Meta URL with the merchant access token
    and streams the result back with the original content-type.
    """
    db = get_db()
    msg = await db.messages.find_one({"id": message_id})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    wa_url = msg.get("whatsapp_media_url")
    if not wa_url:
        raise HTTPException(status_code=404, detail="No WhatsApp media for this message")

    # Determine merchant config via ticket
    ticket = await db.tickets.find_one({"id": msg.get("ticket_id")}) if msg.get("ticket_id") else None
    merchant_id = ticket.get("merchant_id") if ticket else None
    config = await get_whatsapp_config(merchant_id)
    access_token = config.get("access_token")

    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(wa_url, headers=headers)
            r.raise_for_status()
            content_type = r.headers.get("content-type", "application/octet-stream")
            return StreamingResponse(r.aiter_bytes(), media_type=content_type)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Upstream media fetch failed: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
