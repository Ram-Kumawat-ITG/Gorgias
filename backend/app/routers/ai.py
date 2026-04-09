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
        # Ensure the AI reply is a plain string before saving. Some agents
        # return structured objects like {'reply': 'text', ...}.
        if isinstance(ai_reply, dict):
            body_text = ai_reply.get("reply") or ai_reply.get("message") or str(ai_reply)
        else:
            body_text = str(ai_reply)

        reply_msg = MessageInDB(
            ticket_id=ticket_id,
            body=body_text,
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
            "ai_reply": body_text,
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


# ── Multi-channel notification helper ────────────────────────────────────────

async def _notify_customer(
    ticket: dict,
    ticket_id: str,
    message_wa: str,
    message_email: str,
    email_subject: str,
    message_ig: str,
    agent_id: str,
) -> bool:
    """Send a notification to the customer on the same channel they used.

    Returns True if notification was sent successfully.
    """
    from app.models.message import MessageInDB

    db = get_db()
    channel = ticket.get("channel", "")
    merchant_id = ticket.get("merchant_id")
    notified = False

    # ── WhatsApp ─────────────────────────────────────────────────────────────
    if channel == "whatsapp":
        wa_phone = ticket.get("whatsapp_phone", "")
        if wa_phone and message_wa:
            try:
                from app.services.whatsapp_service import get_whatsapp_config, send_text_message
                config = await get_whatsapp_config(merchant_id)
                wa_result = await send_text_message(wa_phone, message_wa, config)
                msg_list = wa_result.get("messages") or []
                sent_id = msg_list[0].get("id") if msg_list else None
                msg_doc = MessageInDB(
                    ticket_id=ticket_id,
                    body=message_wa,
                    sender_type="agent",
                    sender_id=agent_id,
                    channel="whatsapp",
                    ai_generated=False,
                    whatsapp_message_id=sent_id,
                    whatsapp_status="sent" if sent_id else "failed",
                )
                await db.messages.insert_one(msg_doc.model_dump())
                notified = bool(sent_id)
            except Exception as e:
                print(f"[notify] WhatsApp failed: {e}")

    # ── Email ────────────────────────────────────────────────────────────────
    elif channel == "email":
        customer_email = (
            ticket.get("pending_action_email")
            or ticket.get("customer_email", "")
        )
        if customer_email and message_email:
            try:
                from app.services.mailgun_service import send_reply_email
                await send_reply_email(customer_email, email_subject, message_email, ticket_id)
                msg_doc = MessageInDB(
                    ticket_id=ticket_id,
                    body=message_email,
                    sender_type="agent",
                    sender_id=agent_id,
                    channel="email",
                    ai_generated=False,
                )
                await db.messages.insert_one(msg_doc.model_dump())
                notified = True
            except Exception as e:
                print(f"[notify] Email failed: {e}")

    # ── Instagram ────────────────────────────────────────────────────────────
    elif channel == "instagram":
        ig_user_id = ticket.get("instagram_user_id", "")
        if ig_user_id and message_ig:
            try:
                from app.services.instagram_service import (
                    get_instagram_config,
                    send_text_message as ig_send,
                )
                config = await get_instagram_config(merchant_id)
                ig_result = await ig_send(ig_user_id, message_ig, config)
                sent_ok = "error" not in ig_result
                msg_doc = MessageInDB(
                    ticket_id=ticket_id,
                    body=message_ig,
                    sender_type="agent",
                    sender_id=agent_id,
                    channel="instagram",
                    ai_generated=False,
                    instagram_status="sent" if sent_ok else "failed",
                )
                await db.messages.insert_one(msg_doc.model_dump())
                notified = sent_ok
            except Exception as e:
                print(f"[notify] Instagram failed: {e}")

    return notified


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
    customer_name = ticket.get("customer_name") or "there"

    now = datetime.now(timezone.utc)
    shopify_result = None

    # ── Execute the Shopify action ───────────────────────────────────────────
    if action_type == "cancel" and order_id:
        try:
            from app.services.shopify_client import shopify_post as _shopify_post
            await _shopify_post(f"/orders/{order_id}/cancel.json", {})
            shopify_result = "cancelled"
        except Exception as e:
            shopify_result = f"error: {e}"

    elif action_type == "refund" and order_id:
        try:
            from app.services.shopify_client import shopify_get as _shopify_get, shopify_post as _shopify_post
            # Find the original paid transaction to refund against
            txns = await _shopify_get(f"/orders/{order_id}/transactions.json")
            parent_id = None
            for t in txns.get("transactions", []):
                if t.get("kind") in ("sale", "capture") and t.get("status") == "success":
                    parent_id = t["id"]
                    break
            if parent_id:
                order_data = await _shopify_get(f"/orders/{order_id}.json")
                total_price = order_data.get("order", {}).get("total_price", "0.00")
                refund_payload = {
                    "refund": {
                        "notify": True,
                        "transactions": [{
                            "parent_id": parent_id,
                            "amount": total_price,
                            "kind": "refund",
                            "gateway": "manual",
                        }],
                    }
                }
                await _shopify_post(f"/orders/{order_id}/refunds.json", refund_payload)
                shopify_result = "refunded"
            else:
                shopify_result = "refund_approved_no_transaction"
        except Exception as e:
            shopify_result = f"error: {e}"

    elif action_type == "replace" and order_id:
        try:
            from app.services.shopify_client import shopify_put as _shopify_put
            await _shopify_put(
                f"/orders/{order_id}.json",
                {"order": {"tags": "replacement-requested", "note": "Replacement approved by admin via helpdesk."}},
            )
            shopify_result = "replacement_tagged"
        except Exception as e:
            shopify_result = f"error: {e}"

    elif action_type == "return" and order_id:
        try:
            from app.services.shopify_client import shopify_put as _shopify_put
            await _shopify_put(
                f"/orders/{order_id}.json",
                {"order": {"tags": "return-requested", "note": "Return approved by admin via helpdesk."}},
            )
            shopify_result = "return_tagged"
        except Exception as e:
            shopify_result = f"error: {e}"
    else:
        shopify_result = "approved"

    # ── Build channel-specific messages ──────────────────────────────────────
    type_labels = {
        "refund": "Refund", "replace": "Replacement",
        "return": "Return", "cancel": "Cancellation",
    }
    label = type_labels.get(action_type, "Request")

    outcome_lines = {
        "cancel": "If you made a payment, the refund will be processed within 5–7 business days.",
        "refund": "The refund will be credited to your original payment method within 5–7 business days.",
        "replace": "A replacement order has been created and will be shipped shortly. Tracking details will be sent to your email.",
        "return": "Your return has been initiated. Our team will be in touch with pickup/drop-off details shortly.",
    }
    outcome = outcome_lines.get(action_type, "Our team will be in touch if any further action is needed.")

    # WhatsApp (bold with * and emojis)
    wa_msg = (
        f"🎉 Great news, {customer_name}!\n\n"
        f"Your *{label} Request* for Order *#{order_number}* has been *approved and processed*.\n\n"
        f"{outcome}\n\n"
        f"Thank you for your patience 🙏 Is there anything else I can help you with?"
    )

    # Email (plain text, more formal)
    email_subject = f"Your {label} Has Been Approved — Order #{order_number}"
    email_msg = (
        f"Hi {customer_name},\n\n"
        f"We're happy to let you know that your {label} request for "
        f"Order #{order_number} has been approved and processed!\n\n"
        f"{outcome}\n\n"
        f"If you have any questions, feel free to reply to this email.\n\n"
        f"Warm regards,\nSupport Team"
    )

    # Instagram DM (concise)
    ig_msg = (
        f"🎉 Your {label} request for Order #{order_number} has been approved and processed!\n\n"
        f"{outcome}\n\n"
        f"Let us know if you need anything else 😊"
    )

    # ── Update ticket ────────────────────────────────────────────────────────
    await db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "status": "resolved",
            "pending_action_approved_at": now,
            "resolved_at": now,
            "updated_at": now,
        }},
    )

    # ── Notify customer on original channel ──────────────────────────────────
    notified = await _notify_customer(
        ticket=ticket,
        ticket_id=ticket_id,
        message_wa=wa_msg,
        message_email=email_msg,
        email_subject=email_subject,
        message_ig=ig_msg,
        agent_id=agent["id"],
    )

    return {
        "status": "approved",
        "action_type": action_type,
        "shopify_result": shopify_result,
        "customer_notified": notified,
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
    customer_name = ticket.get("customer_name") or "there"
    rejection_reason = (body.rejection_reason or "").strip()
    now = datetime.now(timezone.utc)

    type_labels = {
        "refund": "Refund", "replace": "Replacement",
        "return": "Return", "cancel": "Cancellation",
    }
    label = type_labels.get(action_type, "Request")

    reason_wa = f"\n\nHere's why: _{rejection_reason}_" if rejection_reason else ""
    reason_email = f"\n\nReason: {rejection_reason}" if rejection_reason else ""
    reason_ig = f"\nReason: {rejection_reason}" if rejection_reason else ""

    # WhatsApp
    wa_msg = (
        f"Hi {customer_name}, we've reviewed your *{label} Request* "
        f"for Order *#{order_number}*.\n\n"
        f"Unfortunately, we were *unable to approve* this request at this time. 😔"
        f"{reason_wa}\n\n"
        f"If you feel this decision is incorrect or need further help, "
        f"our support team is happy to assist. 🙏"
    )

    # Email
    email_subject = f"Update on Your {label} Request — Order #{order_number}"
    email_msg = (
        f"Hi {customer_name},\n\n"
        f"Thank you for your patience. After reviewing your {label} request "
        f"for Order #{order_number}, we regret to inform you that we were "
        f"unable to approve it at this time."
        f"{reason_email}\n\n"
        f"If you'd like to discuss this further, please reply to this email "
        f"and our team will be happy to assist.\n\n"
        f"Warm regards,\nSupport Team"
    )

    # Instagram DM
    ig_msg = (
        f"Hi {customer_name}, we reviewed your {label} request "
        f"for Order #{order_number}.\n\n"
        f"Unfortunately, it couldn't be approved this time. 😔"
        f"{reason_ig}\n\n"
        f"Feel free to DM us if you'd like to discuss further 🙏"
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

    notified = await _notify_customer(
        ticket=ticket,
        ticket_id=ticket_id,
        message_wa=wa_msg,
        message_email=email_msg,
        email_subject=email_subject,
        message_ig=ig_msg,
        agent_id=agent["id"],
    )

    return {
        "status": "rejected",
        "action_type": action_type,
        "rejection_reason": rejection_reason,
        "customer_notified": notified,
    }
