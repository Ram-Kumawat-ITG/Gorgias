# SLA policies router — CRUD for SLA policies and compliance reporting
from fastapi import APIRouter, Depends, HTTPException
from app.routers.auth import get_current_agent
from app.database import get_db
from app.models.sla_policy import SLAPolicyCreate, SLAPolicyInDB

router = APIRouter(prefix="/sla-policies", tags=["SLA"])


@router.get("")
async def list_sla_policies(agent=Depends(get_current_agent)):
    db = get_db()
    policies = await db.sla_policies.find().to_list(100)
    for p in policies:
        p["_id"] = str(p["_id"])
    return policies


@router.post("")
async def create_sla_policy(data: SLAPolicyCreate, agent=Depends(get_current_agent)):
    db = get_db()
    policy = SLAPolicyInDB(
        name=data.name,
        priority=data.priority,
        first_response_hours=data.first_response_hours,
        resolution_hours=data.resolution_hours,
        applies_to_channels=data.applies_to_channels,
        is_active=data.is_active,
    )
    doc = policy.model_dump()
    await db.sla_policies.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/{policy_id}")
async def delete_sla_policy(policy_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    result = await db.sla_policies.delete_one({"id": policy_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="SLA policy not found")
    return {"status": "deleted"}


@router.get("/report")
async def sla_report(agent=Depends(get_current_agent)):
    db = get_db()
    pipeline = [
        {"$group": {"_id": "$sla_status", "count": {"$sum": 1}}},
    ]
    results = await db.tickets.aggregate(pipeline).to_list(10)
    report = {r["_id"]: r["count"] for r in results}
    return report
