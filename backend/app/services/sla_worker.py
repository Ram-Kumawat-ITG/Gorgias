# SLA breach detection worker — runs on a schedule to update ticket SLA statuses
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_db
from app.services.activity_service import log_activity

scheduler = AsyncIOScheduler()


def _compute_resolution_status(now: datetime, sla_warning_at, sla_due_at) -> str:
    """Determine the correct resolution SLA status given the current time."""
    if sla_due_at and now >= sla_due_at:
        return "breached"
    if sla_warning_at and now >= sla_warning_at:
        return "warning"
    return "ok"


def _resolution_status_description(new_status: str, sla_due_at) -> str:
    due_str = sla_due_at.strftime("%Y-%m-%d %H:%M UTC") if sla_due_at else "unknown"
    if new_status == "breached":
        return f"SLA deadline passed (due: {due_str})"
    if new_status == "warning":
        return f"Approaching SLA deadline (due: {due_str})"
    return "SLA status restored to OK"


async def check_sla_breaches(ticket_id: str = None, channel: str = None):
    """Evaluate SLA status for open tickets and transition ok → warning → breached.

    Also checks whether the first response deadline has been missed on tickets
    where the agent has not yet replied.

    Logs an activity event on every status change so the timeline stays current.
    Accepts optional ticket_id / channel filters for targeted or testing runs.
    """
    db = get_db()
    if db is None:
        return

    now = datetime.now(timezone.utc)

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
        try:
            ticket_updates = {}

            # ── Resolution SLA ────────────────────────────────────────────────────
            old_status = ticket.get("sla_status", "ok")
            new_status = _compute_resolution_status(
                now,
                ticket.get("sla_warning_at"),
                ticket.get("sla_due_at"),
            )

            if new_status != old_status:
                ticket_updates["sla_status"] = new_status

                try:
                    await log_activity(
                        entity_type="ticket",
                        entity_id=ticket["id"],
                        event=f"sla.{new_status}",
                        actor_type="system",
                        description=_resolution_status_description(new_status, ticket.get("sla_due_at")),
                        customer_email=ticket.get("customer_email"),
                        metadata={
                            "old_status": old_status,
                            "new_status": new_status,
                            "sla_due_at": str(ticket.get("sla_due_at")),
                            "sla_warning_at": str(ticket.get("sla_warning_at")),
                        },
                    )
                except Exception as log_err:
                    print(f"SLA worker: log_activity failed for ticket {ticket.get('id')}: {log_err}")

                # Fire automation engine on breach
                if new_status == "breached":
                    try:
                        from app.services.automation_engine import evaluate_automations
                        await evaluate_automations("sla.breached", ticket)
                    except Exception:
                        pass

            # ── First Response SLA ────────────────────────────────────────────────
            first_response_due = ticket.get("first_response_due_at")
            first_response_at = ticket.get("first_response_at")
            old_fr_status = ticket.get("first_response_sla_status", "pending")

            if (
                first_response_due
                and not first_response_at               # agent has not yet replied
                and old_fr_status == "pending"          # not already marked breached
                and now >= first_response_due
            ):
                ticket_updates["first_response_sla_status"] = "breached"

                try:
                    await log_activity(
                        entity_type="ticket",
                        entity_id=ticket["id"],
                        event="sla.first_response_breached",
                        actor_type="system",
                        description=f"First response deadline passed (due: {first_response_due.strftime('%Y-%m-%d %H:%M UTC')})",
                        customer_email=ticket.get("customer_email"),
                        metadata={
                            "first_response_due_at": str(first_response_due),
                            "channel": ticket.get("channel"),
                        },
                    )
                except Exception as log_err:
                    print(f"SLA worker: log_activity failed for ticket {ticket.get('id')}: {log_err}")

                try:
                    from app.services.automation_engine import evaluate_automations
                    await evaluate_automations("sla.first_response_breached", ticket)
                except Exception:
                    pass

            # ── Write all changes in a single DB call ─────────────────────────────
            if ticket_updates:
                ticket_updates["updated_at"] = now
                await db.tickets.update_one(
                    {"id": ticket["id"]},
                    {"$set": ticket_updates},
                )
                updated += 1

        except Exception as e:
            print(f"SLA worker: unexpected error processing ticket {ticket.get('id')}: {e}")

    if updated:
        print(f"SLA worker: {updated} ticket(s) updated")


def start_sla_scheduler():
    scheduler.add_job(check_sla_breaches, "interval", minutes=1, id="sla_check")
    scheduler.start()
    print("SLA scheduler started (1-minute interval)")


def stop_sla_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
