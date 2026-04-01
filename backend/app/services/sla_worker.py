# SLA breach detection worker — runs on a schedule to mark overdue tickets as breached
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_db

scheduler = AsyncIOScheduler()


async def check_sla_breaches():
    """Mark tickets as SLA-breached when sla_due_at has passed and ticket is still open."""
    db = get_db()
    if db is None:
        return
    now = datetime.now(timezone.utc)
    try:
        result = await db.tickets.update_many(
            {
                "sla_due_at": {"$lte": now},
                "sla_status": "ok",
                "status": {"$nin": ["resolved", "closed"]},
            },
            {"$set": {"sla_status": "breached", "updated_at": now}},
        )
        if result.modified_count:
            print(f"SLA worker: {result.modified_count} ticket(s) marked as breached")
    except Exception as e:
        print(f"SLA worker error: {e}")


def start_sla_scheduler():
    scheduler.add_job(check_sla_breaches, "interval", minutes=5, id="sla_check")
    scheduler.start()
    print("SLA scheduler started (5-minute interval)")


def stop_sla_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
