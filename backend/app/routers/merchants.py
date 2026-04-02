# Merchant router — CRUD for managing merchant email and Shopify configurations
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from app.routers.auth import get_current_agent
from app.database import get_db
from app.models.merchant import MerchantCreate, MerchantUpdate, MerchantInDB

router = APIRouter(prefix="/merchants", tags=["Merchants"])


@router.get("")
async def list_merchants(agent=Depends(get_current_agent)):
    db = get_db()
    merchants = await db.merchants.find().to_list(100)
    for m in merchants:
        m["_id"] = str(m["_id"])
        m["mailgun_api_key"] = "***hidden***"
        m["shopify_access_token"] = "***hidden***"
    return merchants


@router.post("")
async def create_merchant(data: MerchantCreate, agent=Depends(get_current_agent)):
    db = get_db()
    existing = await db.merchants.find_one({"support_email": data.support_email})
    if existing:
        raise HTTPException(status_code=400, detail="Merchant with this support email already exists")
    merchant = MerchantInDB(**data.model_dump())
    await db.merchants.insert_one(merchant.model_dump())
    doc = merchant.model_dump()
    doc["mailgun_api_key"] = "***hidden***"
    doc["shopify_access_token"] = "***hidden***"
    return doc


@router.patch("/{merchant_id}")
async def update_merchant(merchant_id: str, data: MerchantUpdate, agent=Depends(get_current_agent)):
    db = get_db()
    merchant = await db.merchants.find_one({"id": merchant_id})
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.merchants.update_one({"id": merchant_id}, {"$set": updates})
    updated = await db.merchants.find_one({"id": merchant_id})
    updated["_id"] = str(updated["_id"])
    updated["mailgun_api_key"] = "***hidden***"
    updated["shopify_access_token"] = "***hidden***"
    return updated


@router.delete("/{merchant_id}")
async def delete_merchant(merchant_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    result = await db.merchants.delete_one({"id": merchant_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return {"status": "deleted"}
