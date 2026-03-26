# Ticket management router — CRUD operations for support tickets
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from app.routers.auth import get_current_agent
from app.database import get_db
from app.models.ticket import TicketCreate, TicketUpdate, TicketInDB
from app.models.message import MessageCreate, MessageInDB
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.ticket_service import apply_sla_policy
from app.services.activity_service import log_activity

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.get("")
async def list_tickets(
    status: str = None,
    assignee_id: str = None,
    tag: str = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    agent=Depends(get_current_agent),
):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    if assignee_id:
        query["assignee_id"] = assignee_id
    if tag:
        query["tags"] = tag

    total = await db.tickets.count_documents(query)
    skip = (page - 1) * limit
    tickets = await db.tickets.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    for t in tickets:
        t["_id"] = str(t["_id"])
    return {"tickets": tickets, "total": total, "page": page, "limit": limit}


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

    return msg.model_dump()
