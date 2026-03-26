# AI router — generates GPT-4 reply suggestions for tickets
from fastapi import APIRouter, Depends
from app.routers.auth import get_current_agent
from app.services.ai_service import generate_reply_suggestion

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/suggest/{ticket_id}")
async def suggest_reply(ticket_id: str, agent=Depends(get_current_agent)):
    suggestion = await generate_reply_suggestion(ticket_id)
    return {"suggestion": suggestion}
