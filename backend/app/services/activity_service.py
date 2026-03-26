# Activity logging service — records every meaningful state change to activity_logs
from app.database import get_db
from app.models.activity_log import ActivityLog
from datetime import datetime


async def log_activity(
    entity_type: str,
    entity_id: str,
    event: str,
    actor_type: str,
    description: str,
    customer_email: str = None,
    actor_id: str = None,
    actor_name: str = None,
    metadata: dict = None,
):
    db = get_db()
    log = ActivityLog(
        entity_type=entity_type,
        entity_id=entity_id,
        customer_email=customer_email,
        event=event,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        description=description,
        metadata=metadata,
        created_at=datetime.utcnow(),
    )
    await db.activity_logs.insert_one(log.model_dump())
