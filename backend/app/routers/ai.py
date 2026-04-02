# AI router — generates reply suggestions, conversation analysis, and autonomous ticket processing
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from app.routers.auth import get_current_agent
from app.services.ai_service import generate_reply_suggestion
from app.services.ai_agent_service import analyze_conversation
from app.database import get_db

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


@router.post("/process-ticket/{ticket_id}")
async def process_ticket(ticket_id: str, agent=Depends(get_current_agent)):
    """
    Fully autonomous ticket processor.
    Reads the ticket, runs the AI Sales Agent, executes Shopify actions,
    sends the reply via WhatsApp, and saves it in the ticket thread.
    Only works for WhatsApp tickets — returns analysis suggestions for other channels.
    """
    db = get_db()

    # ── Fetch ticket ──────────────────────────────────────────────────────────
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    channel = ticket.get("channel", "")

    # ── Fetch full message history ────────────────────────────────────────────
    raw_messages = await db.messages.find(
        {"ticket_id": ticket_id, "is_internal_note": {"$ne": True}},
        sort=[("created_at", 1)],
    ).to_list(500)

    if not raw_messages:
        return {
            "status": "skipped",
            "reason": "No messages found in this ticket",
            "reply_sent": False,
        }

    last_msg = raw_messages[-1]

    # ── For WhatsApp — run the full autonomous agent ──────────────────────────
    if channel == "whatsapp":
        wa_phone = ticket.get("whatsapp_phone")
        merchant_id = ticket.get("merchant_id")
        customer_name = ticket.get("customer_name") or ""
        current_message = last_msg.get("body", "")

        if not wa_phone:
            return {"status": "error", "reason": "No WhatsApp phone on ticket", "reply_sent": False}

        from app.services.whatsapp_ai_agent import process_whatsapp_message
        from app.services.whatsapp_service import get_whatsapp_config, send_text_message
        from app.models.message import MessageInDB

        ai_reply = await process_whatsapp_message(
            ticket_id=ticket_id,
            phone_number_id="",  # resolved inside process_whatsapp_message via merchant
            customer_phone=wa_phone,
            current_message=current_message,
            merchant_id=merchant_id,
            customer_name=customer_name,
        )

        if not ai_reply:
            return {
                "status": "error",
                "reason": "AI agent returned no reply — check GROQ_API_KEY",
                "reply_sent": False,
            }

        # Send via WhatsApp API
        config = await get_whatsapp_config(merchant_id)
        wa_result = await send_text_message(wa_phone, ai_reply, config)
        messages_list = wa_result.get("messages") or []
        sent_id = messages_list[0].get("id") if messages_list else None
        wa_status = "sent" if sent_id else "failed"

        # Capture any send error detail to surface to the frontend
        send_error = None
        if not sent_id:
            send_error = (
                wa_result.get("error")
                or wa_result.get("detail")
                or str(wa_result)
            )
            print(
                f"[WhatsApp] process-ticket send FAILED\n"
                f"  ticket={ticket_id} to={wa_phone}\n"
                f"  error={send_error}\n"
                f"  config phone_number_id={config.get('phone_number_id')}\n"
                f"  token_set={bool(config.get('access_token'))}"
            )

        # Always save the AI reply to the ticket thread (even if send failed)
        reply_msg = MessageInDB(
            ticket_id=ticket_id,
            body=ai_reply,
            sender_type="agent",
            sender_id=agent["id"],
            channel="whatsapp",
            ai_generated=True,
            whatsapp_message_id=sent_id,
            whatsapp_status=wa_status,
        )
        await db.messages.insert_one(reply_msg.model_dump())

        # Update ticket — stamp first_response_at if this is the first agent reply
        now = datetime.now(timezone.utc)
        ticket_updates = {"updated_at": now}

        if not ticket.get("first_response_at"):
            ticket_updates["first_response_at"] = now
            first_response_due = ticket.get("first_response_due_at")
            if first_response_due:
                ticket_updates["first_response_sla_status"] = "met" if now <= first_response_due else "breached"
            else:
                ticket_updates["first_response_sla_status"] = "met"

        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": ticket_updates},
        )

        return {
            "status": "success",
            "reply_sent": wa_status == "sent",
            "whatsapp_status": wa_status,
            "ai_reply": ai_reply,
            "message_id": reply_msg.id,
            "send_error": send_error,  # None when sent OK, error string when failed
        }

    # ── For non-WhatsApp tickets — return AI analysis only ───────────────────
    msgs = [
        {"sender": m.get("sender_type", "customer"), "message": m.get("body", "")}
        for m in raw_messages
    ]
    analysis = await analyze_conversation(
        msgs,
        subject=ticket.get("subject", ""),
        customer_email=ticket.get("customer_email", ""),
        shopify_order_id=ticket.get("shopify_order_id"),
    )
    return {
        "status": "analysis_only",
        "channel": channel,
        "reply_sent": False,
        "analysis": analysis,
    }
