# Automations router — CRUD for if-then automation rules
from fastapi import APIRouter, Depends, HTTPException
from app.routers.auth import get_current_agent
from app.database import get_db
from app.models.automation_rule import AutomationRuleCreate, AutomationRuleInDB

router = APIRouter(prefix="/automations", tags=["Automations"])


@router.get("")
async def list_automations(agent=Depends(get_current_agent)):
    db = get_db()
    rules = await db.automation_rules.find().sort("priority", 1).to_list(100)
    for r in rules:
        r["_id"] = str(r["_id"])
    return rules


@router.post("")
async def create_automation(data: AutomationRuleCreate, agent=Depends(get_current_agent)):
    db = get_db()
    rule = AutomationRuleInDB(
        name=data.name,
        trigger_event=data.trigger_event,
        conditions=data.conditions,
        actions=data.actions,
        stop_processing=data.stop_processing,
        priority=data.priority,
        is_active=data.is_active,
    )
    doc = rule.model_dump()
    await db.automation_rules.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/{rule_id}")
async def update_automation(rule_id: str, data: AutomationRuleCreate, agent=Depends(get_current_agent)):
    db = get_db()
    updates = data.model_dump()
    result = await db.automation_rules.update_one({"id": rule_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    updated = await db.automation_rules.find_one({"id": rule_id})
    updated["_id"] = str(updated["_id"])
    return updated


@router.delete("/{rule_id}")
async def delete_automation(rule_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    result = await db.automation_rules.delete_one({"id": rule_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    return {"status": "deleted"}
