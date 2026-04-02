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


class ApproveRejectRequest(BaseModel):
    rejection_reason: Optional[str] = None


@router.post("/approve-action/{ticket_id}")
async def approve_pending_action(ticket_id: str, agent=Depends(get_current_agent)):
    """Approve a pending_admin_action ticket — execute the Shopify action and notify customer."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.get("status") != "pending_admin_action":
        raise HTTPException(status_code=400, detail="Ticket is not pending admin action")

    action_type = ticket.get("pending_action_type", "")
    order_id = ticket.get("pending_action_order_id", "")
    order_number = ticket.get("pending_action_order_number", "")
    wa_phone = ticket.get("whatsapp_phone", "")
    merchant_id = ticket.get("merchant_id")

    now = datetime.now(timezone.utc)
    shopify_result = None
    customer_msg = ""

    # Execute the Shopify action
    if action_type == "cancel" and order_id:
        try:
            from app.services.shopify_client import shopify_post as _shopify_post
            await _shopify_post(f"/orders/{order_id}/cancel.json", {})
            shopify_result = "cancelled"
            customer_msg = (
                f"✅ Your order *#{order_number}* has been successfully cancelled.\n\n"
                f"If you made a payment, the refund will be processed within 5–7 business days. 💳"
            )
        except Exception as e:
            shopify_result = f"error: {e}"
            customer_msg = (
                f"✅ Your cancellation request has been approved!\n\n"
                f"Our team is processing your order *#{order_number}* now. 🙏"
            )
    elif action_type == "refund" and order_id:
        shopify_result = "refund_approved"
        customer_msg = (
            f"🎉 Your *Refund Request* has been approved!\n\n"
            f"The refund for order *#{order_number}* will reflect in your account within 5–7 business days. 💰"
        )
    elif action_type == "replace" and order_id:
        shopify_result = "replace_approved"
        customer_msg = (
            f"🎉 Your *Replacement Request* has been approved!\n\n"
            f"A replacement for order *#{order_number}* will be shipped shortly. 📦\n"
            f"Tracking details will be sent to your email."
        )
    elif action_type == "return" and order_id:
        shopify_result = "return_approved"
        customer_msg = (
            f"🎉 Your *Return Request* has been approved!\n\n"
            f"A pickup for order *#{order_number}* is being scheduled. 📦\n"
            f"Our team will share the pickup details with you shortly."
        )
    else:
        customer_msg = (
            f"🎉 Your request has been approved and processed successfully!\n\n"
            f"Our team will be in touch if any further action is needed. 🙏"
        )

    # Update ticket
    await db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "status": "resolved",
            "pending_action_approved_at": now,
            "updated_at": now,
        }},
    )

    # Notify customer via WhatsApp
    wa_notify_result = None
    if wa_phone and customer_msg:
        try:
            from app.services.whatsapp_service import get_whatsapp_config, send_text_message
            from app.models.message import MessageInDB
            config = await get_whatsapp_config(merchant_id)
            wa_notify_result = await send_text_message(wa_phone, customer_msg, config)
            msg_list = wa_notify_result.get("messages") or []
            sent_id = msg_list[0].get("id") if msg_list else None
            notify_msg = MessageInDB(
                ticket_id=ticket_id,
                body=customer_msg,
                sender_type="agent",
                sender_id=agent["id"],
                channel="whatsapp",
                ai_generated=False,
                whatsapp_message_id=sent_id,
                whatsapp_status="sent" if sent_id else "failed",
            )
            await db.messages.insert_one(notify_msg.model_dump())
        except Exception as e:
            print(f"[approve_action] WhatsApp notify failed: {e}")

    return {
        "status": "approved",
        "action_type": action_type,
        "shopify_result": shopify_result,
        "customer_notified": wa_notify_result is not None,
    }


@router.post("/reject-action/{ticket_id}")
async def reject_pending_action(
    ticket_id: str,
    body: ApproveRejectRequest,
    agent=Depends(get_current_agent),
):
    """Reject a pending_admin_action ticket and notify the customer."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.get("status") != "pending_admin_action":
        raise HTTPException(status_code=400, detail="Ticket is not pending admin action")

    action_type = ticket.get("pending_action_type", "request")
    order_number = ticket.get("pending_action_order_number", "")
    wa_phone = ticket.get("whatsapp_phone", "")
    merchant_id = ticket.get("merchant_id")
    rejection_reason = (body.rejection_reason or "").strip()
    now = datetime.now(timezone.utc)

    type_labels = {
        "refund": "Refund", "replace": "Replacement",
        "return": "Return", "cancel": "Cancellation",
    }
    label = type_labels.get(action_type, "Request")

    reason_line = f"\n\nReason: _{rejection_reason}_" if rejection_reason else ""
    customer_msg = (
        f"Unfortunately, your *{label} Request* was not approved this time. 😔"
        f"{reason_line}\n\n"
        f"If you need further assistance, feel free to contact our support team. 🙏"
    )

    await db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "status": "open",
            "pending_action_rejected_at": now,
            "pending_action_rejection_reason": rejection_reason,
            "updated_at": now,
        }},
    )

    if wa_phone and customer_msg:
        try:
            from app.services.whatsapp_service import get_whatsapp_config, send_text_message
            from app.models.message import MessageInDB
            config = await get_whatsapp_config(merchant_id)
            wa_result = await send_text_message(wa_phone, customer_msg, config)
            msg_list = wa_result.get("messages") or []
            sent_id = msg_list[0].get("id") if msg_list else None
            notify_msg = MessageInDB(
                ticket_id=ticket_id,
                body=customer_msg,
                sender_type="agent",
                sender_id=agent["id"],
                channel="whatsapp",
                ai_generated=False,
                whatsapp_message_id=sent_id,
                whatsapp_status="sent" if sent_id else "failed",
            )
            await db.messages.insert_one(notify_msg.model_dump())
        except Exception as e:
            print(f"[reject_action] WhatsApp notify failed: {e}")

    return {
        "status": "rejected",
        "action_type": action_type,
        "rejection_reason": rejection_reason,
    }
