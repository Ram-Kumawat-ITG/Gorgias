# SLA router — manual trigger for SLA status checks
from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.routers.auth import get_current_agent
from app.services.sla_worker import check_sla_breaches

router = APIRouter(prefix="/sla", tags=["SLA"])


@router.post("/check")
async def manual_sla_check(
    ticket_id: Optional[str] = Query(None, description="Check a single ticket by ID"),
    channel: Optional[str] = Query(None, description="Filter by channel: whatsapp, email, instagram"),
    agent=Depends(get_current_agent),
):
    """Manually trigger SLA status evaluation.

    Without filters — checks all open tickets.
    With ticket_id — checks that specific ticket only.
    With channel — checks all open tickets for that channel.
    """
    await check_sla_breaches(ticket_id=ticket_id, channel=channel)
    return {"status": "ok", "message": "SLA check complete"}
