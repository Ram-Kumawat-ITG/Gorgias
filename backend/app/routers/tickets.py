# Ticket management router — CRUD operations for support tickets
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone
from app.routers.auth import get_current_agent
from app.config import settings
from app.database import get_db
from app.models.ticket import TicketCreate, TicketUpdate, TicketInDB
from app.models.message import MessageCreate, MessageInDB
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.ticket_service import apply_sla_policy, classify_ticket_type, _get_admin_agent_id
from app.services.activity_service import log_activity

router = APIRouter(prefix="/tickets", tags=["Tickets"])


# ---------------------------------------------------------------------------
# Multi-tenant Shopify context — reads optional headers, falls back to .env
# ---------------------------------------------------------------------------

class ShopifyContext:
    """Resolved Shopify credentials for the current request."""
    def __init__(self, store_domain: str, access_token: str):
        self.store_domain = store_domain
        self.access_token = access_token


async def get_shopify_context(
    x_store_domain: Optional[str] = Header(None),
    x_access_token: Optional[str] = Header(None),
) -> ShopifyContext:
    """Extract Shopify credentials from request headers.

    - Both headers present  → use them (external tenant).
    - Neither header present → fall back to .env values (owner store).
    - Only one header present → 422 error.
    """
    has_domain = bool(x_store_domain)
    has_token = bool(x_access_token)

    if has_domain != has_token:
        raise HTTPException(
            status_code=422,
            detail="Both X-Store-Domain and X-Access-Token headers are required together. Pass both or neither.",
        )

    if has_domain and has_token:
        # Basic format validation
        if not x_store_domain.endswith(".myshopify.com"):
            raise HTTPException(
                status_code=422,
                detail="X-Store-Domain must end with .myshopify.com (e.g. my-store.myshopify.com)",
            )
        return ShopifyContext(store_domain=x_store_domain, access_token=x_access_token)

    # Fallback to .env values
    return ShopifyContext(
        store_domain=settings.shopify_store_domain,
        access_token=settings.shopify_access_token,
    )


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
            # Default inbox view — open + pending + pending_admin_action (excludes resolved/closed)
            query["status"] = {"$in": ["open", "pending", "pending_admin_action"]}
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
async def create_ticket(
    data: TicketCreate,
    agent=Depends(get_current_agent),
    ctx: ShopifyContext = Depends(get_shopify_context),
):
    db = get_db()
    customer = await fetch_and_sync_customer(
        data.customer_email,
        store_domain=ctx.store_domain,
        access_token=ctx.access_token,
    )

    admin_id = await _get_admin_agent_id()
    ticket = TicketInDB(
        subject=data.subject,
        customer_email=data.customer_email,
        customer_name=data.customer_name or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or None,
        shopify_customer_id=data.shopify_customer_id or customer.get("shopify_customer_id"),
        store_domain=ctx.store_domain,
        channel=data.channel.value if hasattr(data.channel, "value") else data.channel,
        priority=data.priority.value if hasattr(data.priority, "value") else data.priority,
        tags=data.tags,
        ticket_type=classify_ticket_type(data.subject, data.initial_message or ""),
        assignee_id=admin_id,
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

    updates["updated_at"] = datetime.now(timezone.utc)

    if "status" in updates:
        old_status = ticket.get("status")
        new_status = updates["status"]

        # ── Ticket resolved ───────────────────────────────────────────────────
        if new_status == "resolved" and old_status != "resolved":
            updates["resolved_at"] = datetime.utcnow()

            # If this is a cancel_requested ticket, trigger Shopify order cancellation
            if ticket.get("ticket_type") == "cancel_requested" and ticket.get("cancel_requested_order_id"):
                try:
                    from app.services.order_service import cancel_order
                    order_id = ticket["cancel_requested_order_id"]
                    cancel_result = await cancel_order(order_id)
                    if cancel_result:
                        await log_activity(
                            entity_type="order",
                            entity_id=order_id,
                            event="order.cancelled",
                            actor_type="agent",
                            actor_id=agent["id"],
                            actor_name=agent["full_name"],
                            description=f"Order {order_id} cancelled via Shopify (ticket resolved)",
                            customer_email=ticket.get("customer_email"),
                        )
                        # Notify customer about successful cancellation
                        customer_email = ticket.get("customer_email", "")
                        channel = ticket.get("channel", "email")
                        cancel_notify_msg = (
                            "Your order has been successfully cancelled. "
                            "If you have any questions, feel free to reach out to us."
                        )
                        if channel == "whatsapp":
                            cancel_notify_msg = (
                                "Your order has been successfully cancelled. ✅\n"
                                "If you need anything else, feel free to reach out! 🙏"
                            )
                            try:
                                from app.services.whatsapp_service import get_whatsapp_config, send_text_message as wa_send
                                wa_phone = ticket.get("whatsapp_phone")
                                if wa_phone:
                                    wa_cfg = await get_whatsapp_config(ticket.get("merchant_id"))
                                    await wa_send(wa_phone, cancel_notify_msg, wa_cfg)
                            except Exception as e:
                                print(f"WhatsApp cancel notification error: {e}")
                        elif channel == "instagram":
                            cancel_notify_msg = (
                                "Your order has been successfully cancelled! ✅ "
                                "Let us know if you need anything else."
                            )
                            try:
                                from app.services.instagram_service import get_instagram_config, send_text_message as ig_send
                                ig_user_id = ticket.get("instagram_user_id")
                                if ig_user_id:
                                    ig_cfg = await get_instagram_config(ticket.get("merchant_id"))
                                    await ig_send(ig_user_id, cancel_notify_msg, ig_cfg)
                            except Exception as e:
                                print(f"Instagram cancel notification error: {e}")
                        else:  # email
                            try:
                                from app.services.mailgun_service import send_reply_email
                                await send_reply_email(
                                    to=customer_email,
                                    subject=f"Re: {ticket.get('subject', 'Order Cancellation')}",
                                    body=cancel_notify_msg,
                                    ticket_id=ticket_id,
                                )
                            except Exception as e:
                                print(f"Email cancel notification error: {e}")

                        # Save notification as message in ticket thread
                        notify_msg = MessageInDB(
                            ticket_id=ticket_id,
                            body=cancel_notify_msg,
                            sender_type="agent",
                            channel=channel,
                        )
                        await db.messages.insert_one(notify_msg.model_dump())
                    else:
                        print(f"Failed to cancel order {order_id} on Shopify")
                except Exception as e:
                    print(f"Order cancellation on ticket resolve error: {e}")
            now = datetime.now(timezone.utc)
            updates["resolved_at"] = now

            # Mark resolution SLA as met if resolved before the deadline
            sla_due = ticket.get("sla_due_at")
            current_sla_status = ticket.get("sla_status", "ok")
            if sla_due and now <= sla_due and current_sla_status != "breached":
                updates["sla_status"] = "met"

            # Mark first response SLA as met if agent did reply at some point
            if ticket.get("first_response_at") and ticket.get("first_response_sla_status") == "pending":
                updates["first_response_sla_status"] = "met"

        # ── Ticket reopened ───────────────────────────────────────────────────
        if old_status in ("resolved", "closed") and new_status in ("open", "pending", "in_progress"):
            # Build a minimal ticket doc to recalculate SLA from now
            merged = {**ticket, **updates}
            merged = await apply_sla_policy(merged)
            # Pull only the SLA fields from the recalculated doc
            for sla_field in (
                "sla_policy_id", "sla_due_at", "sla_warning_at", "sla_status",
                "first_response_due_at",
            ):
                if sla_field in merged:
                    updates[sla_field] = merged[sla_field]
            # Only reset first_response_sla_status if the agent hasn't responded yet
            if not ticket.get("first_response_at"):
                updates["first_response_sla_status"] = merged.get("first_response_sla_status", "pending")

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

    ticket_updates = {"updated_at": datetime.now(timezone.utc)}

    if data.sender_type == "agent" and not data.is_internal_note and not ticket.get("first_response_at"):
        now = datetime.now(timezone.utc)
        ticket_updates["first_response_at"] = now
        ticket_updates["status"] = "pending"

        # Determine whether the first response SLA was met or missed
        first_response_due = ticket.get("first_response_due_at")
        if first_response_due:
            if now <= first_response_due:
                ticket_updates["first_response_sla_status"] = "met"
            else:
                ticket_updates["first_response_sla_status"] = "breached"
        else:
            # No deadline was set — treat as met
            ticket_updates["first_response_sla_status"] = "met"

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
                from app.services.whatsapp_service import get_whatsapp_config, send_text_message
                config = await get_whatsapp_config(ticket.get("merchant_id"))
                wa_phone = ticket.get("whatsapp_phone")
                if wa_phone:
                    result = await send_text_message(wa_phone, data.body, config)
                    wa_msg_id = (result.get("messages") or [{}])[0].get("id", "")
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
                        print(f"WhatsApp send failed for ticket {ticket_id}: {result}")
                        await db.messages.update_one(
                            {"id": msg.id},
                            {"$set": {"whatsapp_status": "failed", "channel": "whatsapp"}},
                        )
            except Exception as e:
                print(f"WhatsApp send error: {e}")
                await db.messages.update_one(
                    {"id": msg.id},
                    {"$set": {"whatsapp_status": "failed"}},
                )
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
