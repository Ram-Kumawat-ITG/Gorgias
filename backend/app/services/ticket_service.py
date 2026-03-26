# Ticket service — handles ticket creation from email and manual sources
from datetime import datetime, timedelta
from app.database import get_db
from app.models.ticket import TicketInDB
from app.models.message import MessageInDB
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.activity_service import log_activity


async def apply_sla_policy(ticket_doc: dict) -> dict:
    db = get_db()
    policy = await db.sla_policies.find_one(
        {"priority": ticket_doc["priority"], "is_active": True}
    )
    if policy:
        ticket_doc["sla_policy_id"] = policy["id"]
        ticket_doc["sla_due_at"] = datetime.utcnow() + timedelta(
            hours=policy["resolution_hours"]
        )
        ticket_doc["sla_status"] = "ok"
    return ticket_doc


async def create_ticket_from_email(customer_email: str, subject: str, body: str) -> dict:
    db = get_db()
    customer = await fetch_and_sync_customer(customer_email)

    existing = await db.tickets.find_one(
        {"customer_email": customer_email, "status": {"$in": ["open", "pending"]}}
    )

    if existing:
        msg = MessageInDB(
            ticket_id=existing["id"],
            body=body,
            sender_type="customer",
        )
        await db.messages.insert_one(msg.model_dump())
        await db.tickets.update_one(
            {"id": existing["id"]}, {"$set": {"updated_at": datetime.utcnow()}}
        )
        await log_activity(
            entity_type="message",
            entity_id=msg.id,
            event="message.received",
            actor_type="customer",
            description=f"Customer replied to ticket: {existing['subject']}",
            customer_email=customer_email,
        )
        # Run automations
        try:
            from app.services.automation_engine import evaluate_automations
            await evaluate_automations("message.received", existing, msg.model_dump())
        except Exception:
            pass
        existing["_id"] = str(existing["_id"])
        return existing

    ticket = TicketInDB(
        subject=subject,
        customer_email=customer_email,
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or None,
        shopify_customer_id=customer.get("shopify_customer_id"),
        channel="email",
    )
    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    msg = MessageInDB(
        ticket_id=ticket.id,
        body=body,
        sender_type="customer",
    )
    await db.messages.insert_one(msg.model_dump())

    await log_activity(
        entity_type="ticket",
        entity_id=ticket.id,
        event="ticket.created",
        actor_type="customer",
        description=f"Ticket created via email: {subject}",
        customer_email=customer_email,
    )

    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("ticket.created", ticket_doc)
    except Exception:
        pass

    ticket_doc.pop("_id", None)
    return ticket_doc
