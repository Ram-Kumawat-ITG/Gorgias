# SLA policy management — CRUD endpoints for configuring SLA policies
from fastapi import APIRouter, Depends, HTTPException
from app.routers.auth import get_current_agent
from app.database import get_db
from app.models.sla_policy import SLAPolicyCreate, SLAPolicyInDB

router = APIRouter(prefix="/sla-policies", tags=["SLA Policies"])


@router.get("")
async def list_sla_policies(agent=Depends(get_current_agent)):
    """Return all SLA policies, active ones first."""
    db = get_db()
    policies = await db.sla_policies.find({}).sort("is_active", -1).to_list(100)
    for p in policies:
        p["_id"] = str(p["_id"])
    return policies


@router.post("")
async def create_sla_policy(data: SLAPolicyCreate, agent=Depends(get_current_agent)):
    """Create a new SLA policy.

    Only one active policy per priority level is recommended.
    If a policy for the same priority already exists and is active, it will remain —
    the new policy will still be created but consider deactivating the old one.
    """
    db = get_db()
    policy = SLAPolicyInDB(
        name=data.name,
        priority=data.priority,
        first_response_hours=data.first_response_hours,
        resolution_hours=data.resolution_hours,
        warning_hours=data.warning_hours,
        applies_to_channels=data.applies_to_channels,
        is_active=data.is_active,
    )
    policy_doc = policy.model_dump()
    await db.sla_policies.insert_one(policy_doc)
    policy_doc.pop("_id", None)
    return policy_doc


@router.post("/apply-retroactive")
async def apply_retroactive_sla(agent=Depends(get_current_agent)):
    """Find all open tickets with no SLA deadlines and apply the matching policy.

    Use this after creating policies for the first time to backfill existing tickets.
    Tickets already assigned a policy (sla_due_at is set) are skipped.
    """
    db = get_db()
    from app.services.ticket_service import apply_sla_policy

    tickets = await db.tickets.find({
        "status": {"$nin": ["resolved", "closed"]},
        "$or": [{"sla_due_at": None}, {"sla_due_at": {"$exists": False}}],
    }).to_list(5000)

    updated = 0
    skipped = 0
    for ticket in tickets:
        ticket_copy = {k: v for k, v in ticket.items() if k != "_id"}
        updated_ticket = await apply_sla_policy(ticket_copy)

        if updated_ticket.get("sla_due_at"):
            await db.tickets.update_one(
                {"id": ticket["id"]},
                {"$set": {
                    "sla_policy_id": updated_ticket.get("sla_policy_id"),
                    "sla_due_at": updated_ticket.get("sla_due_at"),
                    "sla_warning_at": updated_ticket.get("sla_warning_at"),
                    "sla_status": updated_ticket.get("sla_status", "ok"),
                    "first_response_due_at": updated_ticket.get("first_response_due_at"),
                    "first_response_sla_status": updated_ticket.get("first_response_sla_status", "pending"),
                }},
            )
            updated += 1
        else:
            skipped += 1

    return {"updated": updated, "skipped": skipped, "total": len(tickets)}


@router.get("/{policy_id}")
async def get_sla_policy(policy_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    policy = await db.sla_policies.find_one({"id": policy_id})
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")
    policy["_id"] = str(policy["_id"])
    return policy


@router.patch("/{policy_id}")
async def update_sla_policy(policy_id: str, data: SLAPolicyCreate, agent=Depends(get_current_agent)):
    """Update an existing SLA policy.

    Sends the full policy object — all fields are replaced with the provided values.
    Changes take effect for new tickets only; existing tickets keep their current deadlines.
    """
    db = get_db()
    policy = await db.sla_policies.find_one({"id": policy_id})
    if not policy:
        raise HTTPException(status_code=404, detail="SLA policy not found")

    updates = {
        "name": data.name,
        "priority": data.priority,
        "first_response_hours": data.first_response_hours,
        "resolution_hours": data.resolution_hours,
        "warning_hours": data.warning_hours,
        "applies_to_channels": data.applies_to_channels,
        "is_active": data.is_active,
    }
    await db.sla_policies.update_one({"id": policy_id}, {"$set": updates})
    updated = await db.sla_policies.find_one({"id": policy_id})
    updated["_id"] = str(updated["_id"])
    return updated


@router.delete("/{policy_id}")
async def delete_sla_policy(policy_id: str, agent=Depends(get_current_agent)):
    """Delete an SLA policy permanently.

    Existing tickets that were assigned this policy keep their deadlines unchanged.
    """
    db = get_db()
    result = await db.sla_policies.delete_one({"id": policy_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="SLA policy not found")
    return {"status": "deleted"}
