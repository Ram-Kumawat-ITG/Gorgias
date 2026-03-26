# Macros router — CRUD for canned response templates with Jinja2 rendering
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from app.routers.auth import get_current_agent
from app.database import get_db
from app.models.macro import MacroCreate, MacroInDB
from app.services.macro_service import render_macro

router = APIRouter(prefix="/macros", tags=["Macros"])


@router.get("")
async def list_macros(search: str = "", agent=Depends(get_current_agent)):
    db = get_db()
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"body": {"$regex": search, "$options": "i"}},
        ]
    macros = await db.macros.find(query).sort("name", 1).to_list(100)
    for m in macros:
        m["_id"] = str(m["_id"])
    return macros


@router.post("")
async def create_macro(data: MacroCreate, agent=Depends(get_current_agent)):
    db = get_db()
    macro = MacroInDB(
        name=data.name,
        body=data.body,
        tags=data.tags,
        actions=data.actions,
        created_by=agent["id"],
    )
    doc = macro.model_dump()
    await db.macros.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/{macro_id}")
async def update_macro(macro_id: str, data: MacroCreate, agent=Depends(get_current_agent)):
    db = get_db()
    updates = {k: v for k, v in data.model_dump().items()}
    result = await db.macros.update_one({"id": macro_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Macro not found")
    updated = await db.macros.find_one({"id": macro_id})
    updated["_id"] = str(updated["_id"])
    return updated


@router.delete("/{macro_id}")
async def delete_macro(macro_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    result = await db.macros.delete_one({"id": macro_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Macro not found")
    return {"status": "deleted"}


@router.post("/{macro_id}/preview")
async def preview_macro(macro_id: str, ticket_id: str = Query(...), agent=Depends(get_current_agent)):
    db = get_db()
    macro = await db.macros.find_one({"id": macro_id})
    if not macro:
        raise HTTPException(status_code=404, detail="Macro not found")
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    rendered = await render_macro(macro["body"], ticket)
    return {"rendered": rendered, "raw": macro["body"]}
