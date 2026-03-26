# History router — activity timeline for customers, tickets, orders, and messages
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from app.routers.auth import get_current_agent
from app.database import get_db

router = APIRouter(prefix="/history", tags=["History"])


@router.get("/customer/{email}")
async def customer_history(
    email: str,
    days: int = Query(90, ge=1, le=365),
    event_types: str = "",
    limit: int = Query(50, ge=1, le=200),
    agent=Depends(get_current_agent),
):
    db = get_db()
    since = datetime.utcnow() - timedelta(days=days)
    query = {"customer_email": email, "created_at": {"$gte": since}}

    if event_types:
        types = [t.strip() for t in event_types.split(",")]
        query["entity_type"] = {"$in": types}

    events = await db.activity_logs.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for e in events:
        e["_id"] = str(e["_id"])
    return {"customer_email": email, "total": len(events), "events": events}


@router.get("/ticket/{ticket_id}")
async def ticket_history(ticket_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    events = await db.activity_logs.find(
        {"entity_id": ticket_id}
    ).sort("created_at", 1).to_list(200)
    for e in events:
        e["_id"] = str(e["_id"])
    return events


@router.get("/orders/{email}")
async def order_history(email: str, agent=Depends(get_current_agent)):
    db = get_db()
    order_events = await db.activity_logs.find(
        {"entity_type": "order", "customer_email": email}
    ).sort("created_at", -1).to_list(100)
    for e in order_events:
        e["_id"] = str(e["_id"])

    orders = await db.order_snapshots.find(
        {"email": email}
    ).sort("created_at", -1).to_list(20)
    for o in orders:
        o["_id"] = str(o["_id"])

    return {"order_events": order_events, "orders": orders}


@router.get("/messages/{email}")
async def message_history(
    email: str,
    limit: int = Query(100, ge=1, le=500),
    agent=Depends(get_current_agent),
):
    db = get_db()
    tickets = await db.tickets.find(
        {"customer_email": email}
    ).to_list(100)

    ticket_ids = [t["id"] for t in tickets]
    ticket_map = {t["id"]: t.get("subject", "") for t in tickets}

    messages = await db.messages.find(
        {"ticket_id": {"$in": ticket_ids}}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    for m in messages:
        m["_id"] = str(m["_id"])
        m["ticket_subject"] = ticket_map.get(m.get("ticket_id"), "")

    return {
        "customer_email": email,
        "total_tickets": len(ticket_ids),
        "messages": messages,
    }
