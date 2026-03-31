# Ticket management router — CRUD operations for support tickets
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from app.routers.auth import get_current_agent
from app.database import get_db
from app.models.ticket import TicketCreate, TicketUpdate, TicketInDB
from app.models.message import MessageCreate, MessageInDB
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.ticket_service import apply_sla_policy, classify_ticket_type
from app.services.activity_service import log_activity

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.get("")
async def list_tickets(
    status: str = None,
    assignee_id: str = None,
    tag: str = None,
    channel: str = None,
    search: str = None,
    ticket_type: str = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    agent=Depends(get_current_agent),
):
    db = get_db()
    query = {}
    if status:
        if status == 'active':
            # Default inbox view — open + pending (excludes resolved/closed)
            query["status"] = {"$in": ["open", "pending"]}
        elif ',' in status:
            query["status"] = {"$in": status.split(',')}
        else:
            query["status"] = status
    if assignee_id:
        query["assignee_id"] = assignee_id
    if tag:
        query["tags"] = tag
    if channel:
        query["channel"] = channel
    if search:
        query["$or"] = [
            {"subject": {"$regex": search, "$options": "i"}},
            {"customer_email": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
        ]
    if ticket_type:
        query["ticket_type"] = ticket_type

    total = await db.tickets.count_documents(query)
    skip = (page - 1) * limit
    tickets = await db.tickets.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    for t in tickets:
        t["_id"] = str(t["_id"])
    pages = max(1, (total + limit - 1) // limit)
    return {"tickets": tickets, "total": total, "page": page, "limit": limit, "pages": pages}


@router.post("")
async def create_ticket(data: TicketCreate, agent=Depends(get_current_agent)):
    db = get_db()
    customer = await fetch_and_sync_customer(data.customer_email)

    ticket = TicketInDB(
        subject=data.subject,
        customer_email=data.customer_email,
        customer_name=data.customer_name or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or None,
        shopify_customer_id=data.shopify_customer_id or customer.get("shopify_customer_id"),
        channel=data.channel.value if hasattr(data.channel, "value") else data.channel,
        priority=data.priority.value if hasattr(data.priority, "value") else data.priority,
        tags=data.tags,
        ticket_type=classify_ticket_type(data.subject, data.initial_message or ""),
    )
    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    if data.initial_message:
        msg = MessageInDB(
            ticket_id=ticket.id,
            body=data.initial_message,
            sender_type="customer",
        )
        await db.messages.insert_one(msg.model_dump())

    await log_activity(
        entity_type="ticket",
        entity_id=ticket.id,
        event="ticket.created",
        actor_type="agent",
        actor_id=agent["id"],
        actor_name=agent["full_name"],
        description=f"Ticket created: {data.subject}",
        customer_email=data.customer_email,
    )

    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("ticket.created", ticket_doc)
    except Exception:
        pass

    ticket_doc.pop("_id", None)
    return ticket_doc


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket["_id"] = str(ticket["_id"])

    # If shopify_order_id is missing, try to find it from order_snapshots
    # (most recent order for this customer's email)
    if not ticket.get("shopify_order_id") and ticket.get("customer_email"):
        snapshot = await db.order_snapshots.find_one(
            {"email": ticket["customer_email"]},
            sort=[("created_at", -1)],
        )
        if snapshot:
            ticket["shopify_order_id"] = snapshot.get("shopify_order_id")
            ticket["shopify_order_number"] = snapshot.get("order_number")

    return ticket


@router.patch("/{ticket_id}")
async def update_ticket(ticket_id: str, data: TicketUpdate, agent=Depends(get_current_agent)):
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        ticket["_id"] = str(ticket["_id"])
        return ticket

    updates["updated_at"] = datetime.utcnow()

    if "status" in updates:
        old_status = ticket.get("status")
        new_status = updates["status"]
        if new_status == "resolved" and old_status != "resolved":
            updates["resolved_at"] = datetime.utcnow()
        if old_status != new_status:
            await log_activity(
                entity_type="ticket",
                entity_id=ticket_id,
                event="ticket.status_changed",
                actor_type="agent",
                actor_id=agent["id"],
                actor_name=agent["full_name"],
                description=f"Status changed from {old_status} to {new_status}",
                customer_email=ticket.get("customer_email"),
                metadata={"old_status": old_status, "new_status": new_status},
            )

    if "ticket_type" in updates:
        old_type = ticket.get("ticket_type", "general")
        new_type = updates["ticket_type"]
        if old_type != new_type:
            await log_activity(
                entity_type="ticket",
                entity_id=ticket_id,
                event="ticket.type_changed",
                actor_type="agent",
                actor_id=agent["id"],
                actor_name=agent["full_name"],
                description=f"Type changed from {old_type} to {new_type}",
                customer_email=ticket.get("customer_email"),
                metadata={"old_type": old_type, "new_type": new_type},
            )

    await db.tickets.update_one({"id": ticket_id}, {"$set": updates})
    updated = await db.tickets.find_one({"id": ticket_id})
    updated["_id"] = str(updated["_id"])
    return updated


@router.delete("/{ticket_id}")
async def delete_ticket(ticket_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    result = await db.tickets.delete_one({"id": ticket_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await db.messages.delete_many({"ticket_id": ticket_id})
    return {"status": "deleted"}


@router.get("/{ticket_id}/messages")
async def list_messages(ticket_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    messages = await db.messages.find(
        {"ticket_id": ticket_id}
    ).sort("created_at", 1).to_list(500)
    for m in messages:
        m["_id"] = str(m["_id"])
    return messages


@router.post("/{ticket_id}/messages")
async def add_message(ticket_id: str, data: MessageCreate, agent=Depends(get_current_agent)):
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = MessageInDB(
        ticket_id=ticket_id,
        body=data.body,
        sender_type=data.sender_type,
        sender_id=agent["id"],
        is_internal_note=data.is_internal_note,
        ai_generated=data.ai_generated,
    )
    await db.messages.insert_one(msg.model_dump())

    ticket_updates = {"updated_at": datetime.utcnow()}
    if data.sender_type == "agent" and not data.is_internal_note and not ticket.get("first_response_at"):
        ticket_updates["first_response_at"] = datetime.utcnow()
        ticket_updates["status"] = "pending"

    await db.tickets.update_one({"id": ticket_id}, {"$set": ticket_updates})

    await log_activity(
        entity_type="message",
        entity_id=msg.id,
        event="message.sent",
        actor_type="agent",
        actor_id=agent["id"],
        actor_name=agent["full_name"],
        description=f"{'Internal note' if data.is_internal_note else 'Reply'} added to ticket",
        customer_email=ticket.get("customer_email"),
    )

    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("message.received", ticket, msg.model_dump())
    except Exception:
        pass

    # Send reply to customer based on ticket channel (not internal note)
    if data.sender_type == "agent" and not data.is_internal_note:
        channel = ticket.get("channel", "email")

        if channel == "whatsapp":
            try:
                from app.services.whatsapp_service import (
                    get_whatsapp_config,
                    send_text_message,
                    send_template_message,
                    is_within_24h_window,
                )
                config = await get_whatsapp_config(ticket.get("merchant_id"))
                wa_phone = ticket.get("whatsapp_phone")
                if wa_phone:
                    last_msg_at = ticket.get("whatsapp_last_customer_msg_at")
                    if is_within_24h_window(last_msg_at):
                        result = await send_text_message(wa_phone, data.body, config)
                        wa_msg_id = ""
                        if "messages" in result:
                            wa_msg_id = result["messages"][0].get("id", "")
                        if wa_msg_id:
                            await db.messages.update_one(
                                {"id": msg.id},
                                {"$set": {
                                    "whatsapp_message_id": wa_msg_id,
                                    "whatsapp_status": "sent",
                                    "channel": "whatsapp",
                                }},
                            )
                    else:
                        result = await send_template_message(
                            to_phone=wa_phone,
                            template_name="customer_support_reply",
                            language_code="en",
                            components=[{
                                "type": "body",
                                "parameters": [{"type": "text", "text": data.body[:1024]}],
                            }],
                            config=config,
                        )
                        print(f"Sent template message (24h window expired): {result}")
            except Exception as e:
                print(f"WhatsApp send error: {e}")
        elif channel == "twitter":
            try:
                from app.services.twitter_service import (
                    get_twitter_config,
                    send_dm,
                    reply_to_tweet,
                )
                config = await get_twitter_config(ticket.get("merchant_id"))
                twitter_sender_id = ticket.get("twitter_sender_id")
                twitter_type = ticket.get("twitter_type", "dm")
                if twitter_sender_id:
                    if twitter_type == "dm":
                        result = await send_dm(twitter_sender_id, data.body, config)
                        tw_msg_id = result.get("data", {}).get("dm_conversation_id", "")
                    else:
                        # mention — reply to the last tweet in this thread
                        last_tweet_id = ticket.get("twitter_last_tweet_id", "")
                        result = await reply_to_tweet(last_tweet_id, data.body, config)
                        tw_msg_id = result.get("data", {}).get("id", "")
                    tw_status = "sent" if "error" not in result else "failed"
                    if tw_msg_id or tw_status == "sent":
                        await db.messages.update_one(
                            {"id": msg.id},
                            {"$set": {
                                "twitter_message_id": tw_msg_id,
                                "twitter_status": tw_status,
                                "twitter_type": twitter_type,
                                "channel": "twitter",
                            }},
                        )
            except Exception as e:
                print(f"Twitter send error: {e}")
        elif channel == "instagram":
            try:
                from app.services.instagram_service import (
                    get_instagram_config,
                    send_text_message,
                    is_within_24h_window,
                )
                config = await get_instagram_config(ticket.get("merchant_id"))
                ig_user_id = ticket.get("instagram_user_id")
                if ig_user_id:
                    last_msg_at = ticket.get("instagram_last_customer_msg_at")
                    if is_within_24h_window(last_msg_at):
                        result = await send_text_message(ig_user_id, data.body, config)
                        ig_msg_id = result.get("message_id", "")
                        if ig_msg_id:
                            await db.messages.update_one(
                                {"id": msg.id},
                                {"$set": {
                                    "instagram_message_id": ig_msg_id,
                                    "instagram_status": "sent",
                                    "instagram_sender_igsid": ig_user_id,
                                    "channel": "instagram",
                                }},
                            )
                    else:
                        print(f"Instagram 24h window expired for ticket {ticket_id} — message not sent")
            except Exception as e:
                print(f"Instagram send error: {e}")
        else:
            # Default: send via email
            try:
                from app.services.mailgun_service import send_reply_email
                await send_reply_email(
                    to=ticket["customer_email"],
                    subject=f"Re: {ticket.get('subject', 'Support Ticket')}",
                    body=data.body,
                    ticket_id=ticket_id,
                )
            except Exception as e:
                print(f"Email send error: {e}")

    return msg.model_dump()
