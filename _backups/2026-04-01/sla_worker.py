# SLA breach detection worker — runs on a schedule to update ticket SLA statuses
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_db
from app.services.activity_service import log_activity

scheduler = AsyncIOScheduler()


def _compute_new_status(now: datetime, sla_warning_at, sla_due_at) -> str:
    """Determine the correct SLA status given the current time."""
    if sla_due_at and now >= sla_due_at:
        return "breached"
    if sla_warning_at and now >= sla_warning_at:
        return "warning"
    return "ok"


def _status_description(new_status: str, sla_due_at) -> str:
    due_str = sla_due_at.strftime("%Y-%m-%d %H:%M UTC") if sla_due_at else "unknown"
    if new_status == "breached":
        return f"SLA deadline passed (due: {due_str})"
    if new_status == "warning":
        return f"Approaching SLA deadline (due: {due_str})"
    return "SLA status restored to OK"


async def check_sla_breaches(ticket_id: str = None, channel: str = None):
    """Evaluate SLA status for open tickets and transition ok → warning → breached.

    Logs an activity event on every status change so the timeline stays current.
    Accepts optional ticket_id / channel filters for targeted or testing runs.
    """
    db = get_db()
    if db is None:
        return

    now = datetime.utcnow()

    query: dict = {
        "status": {"$nin": ["resolved", "closed"]},
        "sla_due_at": {"$ne": None},  # only tickets with an SLA policy applied
    }
    if ticket_id:
        query["id"] = ticket_id
    if channel:
        query["channel"] = channel

    tickets = await db.tickets.find(query).to_list(1000)

    updated = 0
    for ticket in tickets:
        old_status = ticket.get("sla_status", "ok")
        new_status = _compute_new_status(
            now,
            ticket.get("sla_warning_at"),
            ticket.get("sla_due_at"),
        )

        if new_status == old_status:
            continue

        await db.tickets.update_one(
            {"id": ticket["id"]},
            {"$set": {"sla_status": new_status, "updated_at": now}},
        )

        await log_activity(
            entity_type="ticket",
            entity_id=ticket["id"],
            event=f"sla.{new_status}",
            actor_type="system",
            description=_status_description(new_status, ticket.get("sla_due_at")),
            customer_email=ticket.get("customer_email"),
            metadata={
                "old_status": old_status,
                "new_status": new_status,
                "sla_due_at": str(ticket.get("sla_due_at")),
                "sla_warning_at": str(ticket.get("sla_warning_at")),
            },
        )
        updated += 1

    if updated:
        print(f"SLA worker: {updated} ticket(s) updated")


def start_sla_scheduler():
    scheduler.add_job(check_sla_breaches, "interval", minutes=5, id="sla_check")
    scheduler.start()
    print("SLA scheduler started (5-minute interval)")


def stop_sla_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
