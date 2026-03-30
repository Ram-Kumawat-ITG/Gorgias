# AI router — generates GPT-4 reply suggestions and conversation analysis
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.routers.auth import get_current_agent
from app.services.ai_service import generate_reply_suggestion
from app.services.ai_agent_service import analyze_conversation

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/suggest/{ticket_id}")
async def suggest_reply(ticket_id: str, agent=Depends(get_current_agent)):
    suggestion = await generate_reply_suggestion(ticket_id)
    return {"suggestion": suggestion}


class MessageInput(BaseModel):
    sender: str
    message: str


class AnalyzeRequest(BaseModel):
    subject: str = ""
    customer_email: str = ""
    shopify_order_id: Optional[str] = None
    messages: List[MessageInput]


@router.post("/analyze")
async def analyze_ticket(data: AnalyzeRequest, agent=Depends(get_current_agent)):
    msgs = [{"sender": m.sender, "message": m.message} for m in data.messages]
    result = await analyze_conversation(msgs, data.subject, data.customer_email, data.shopify_order_id)
    return result
