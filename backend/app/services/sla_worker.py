# SLA worker — background job checking for SLA breaches and warnings every minute
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_db
from app.models.message import MessageInDB


scheduler = AsyncIOScheduler()


async def check_sla_breaches():
    db = get_db()
    if db is None:
        return

    now = datetime.utcnow()
    breached = db.tickets.find({
        "sla_due_at": {"$lt": now},
        "sla_status": {"$ne": "breached"},
        "status": {"$nin": ["resolved", "closed"]},
    })

    async for ticket in breached:
        await db.tickets.update_one(
            {"id": ticket["id"]},
            {"$set": {"sla_status": "breached"}},
        )
        msg = MessageInDB(
            ticket_id=ticket["id"],
            body="SLA resolution time has been breached.",
            sender_type="system",
            is_internal_note=True,
        )
        await db.messages.insert_one(msg.model_dump())

        from app.services.activity_service import log_activity
        await log_activity(
            entity_type="ticket",
            entity_id=ticket["id"],
            event="sla.breached",
            actor_type="system",
            description=f"SLA breached for ticket: {ticket.get('subject', '')}",
            customer_email=ticket.get("customer_email"),
        )


async def check_sla_warnings():
    db = get_db()
    if db is None:
        return

    now = datetime.utcnow()
    tickets = db.tickets.find({
        "sla_due_at": {"$gt": now},
        "sla_status": "ok",
        "status": {"$nin": ["resolved", "closed"]},
        "sla_policy_id": {"$ne": None},
    })

    async for ticket in tickets:
        created = ticket.get("created_at", now)
        due = ticket.get("sla_due_at", now)
        total_seconds = (due - created).total_seconds()
        elapsed_seconds = (now - created).total_seconds()

        if total_seconds > 0 and (elapsed_seconds / total_seconds) >= 0.8:
            await db.tickets.update_one(
                {"id": ticket["id"]},
                {"$set": {"sla_status": "warning"}},
            )


def start_sla_scheduler():
    scheduler.add_job(check_sla_breaches, "interval", minutes=1, id="sla_breach_check")
    scheduler.add_job(check_sla_warnings, "interval", minutes=5, id="sla_warning_check")
    scheduler.start()
    print("SLA scheduler started")
