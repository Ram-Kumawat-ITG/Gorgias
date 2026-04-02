# Analytics router — aggregated metrics for the dashboard
import asyncio
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta, timezone
from app.routers.auth import get_current_agent
from app.database import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview")
async def analytics_overview(days: int = Query(30, ge=1, le=365), agent=Depends(get_current_agent)):
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async def tickets_by_status():
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        return await db.tickets.aggregate(pipeline).to_list(10)

    async def tickets_by_channel():
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
        ]
        return await db.tickets.aggregate(pipeline).to_list(10)

    async def daily_volume():
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id": 1}},
        ]
        return await db.tickets.aggregate(pipeline).to_list(365)

    async def avg_first_response():
        pipeline = [
            {"$match": {"created_at": {"$gte": since}, "first_response_at": {"$ne": None}}},
            {"$project": {
                "response_ms": {"$subtract": ["$first_response_at", "$created_at"]},
            }},
            {"$group": {
                "_id": None,
                "avg_ms": {"$avg": "$response_ms"},
            }},
        ]
        result = await db.tickets.aggregate(pipeline).to_list(1)
        if result and result[0].get("avg_ms"):
            return round(result[0]["avg_ms"] / 60000, 1)
        return 0

    async def sla_compliance():
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$sla_status", "count": {"$sum": 1}}},
        ]
        return await db.tickets.aggregate(pipeline).to_list(10)

    async def top_customers():
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$customer_email", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        return await db.tickets.aggregate(pipeline).to_list(10)

    async def activity_breakdown():
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        return await db.activity_logs.aggregate(pipeline).to_list(20)

    async def channel_counts():
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
        ]
        return await db.tickets.aggregate(pipeline).to_list(10)

    (
        by_status,
        by_channel,
        volume,
        avg_response,
        sla,
        top_cust,
        activity,
        channels,
    ) = await asyncio.gather(
        tickets_by_status(),
        tickets_by_channel(),
        daily_volume(),
        avg_first_response(),
        sla_compliance(),
        top_customers(),
        activity_breakdown(),
        channel_counts(),
    )

    return {
        "tickets_by_status": {r["_id"]: r["count"] for r in by_status},
        "tickets_by_channel": {r["_id"]: r["count"] for r in by_channel},
        "daily_volume": [{"date": r["_id"], "count": r["count"]} for r in volume],
        "avg_first_response_minutes": avg_response,
        "sla_compliance": {r["_id"]: r["count"] for r in sla},
        "top_customers": [{"email": r["_id"], "count": r["count"]} for r in top_cust],
        "activity_breakdown": {r["_id"]: r["count"] for r in activity},
        "channel_counts": {r["_id"]: r["count"] for r in channels},
    }
