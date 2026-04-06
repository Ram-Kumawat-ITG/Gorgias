# Admin merchant management — register stores, issue API keys, manage access.
# All endpoints require admin agent authentication.
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from app.routers.auth import get_current_agent
from app.database import get_db
from app.services.api_key_service import generate_api_key, hash_api_key, get_key_prefix
import uuid

router = APIRouter(prefix="/api/admin/merchants", tags=["Admin - Merchants"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class MerchantRegisterRequest(BaseModel):
    shop_domain: str
    app_name: Optional[str] = None
    permissions: List[str] = ["create_ticket"]
    rate_limit: int = 100


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register")
async def register_merchant(
    data: MerchantRegisterRequest,
    agent=Depends(get_current_agent),
):
    """Register a new external store and generate an API key.

    The raw API key is returned ONCE in this response.
    The developer must save it — we only store the hash.
    """
    if not data.shop_domain.endswith(".myshopify.com"):
        raise HTTPException(status_code=422, detail="shop_domain must end with .myshopify.com")

    db = get_db()
    existing = await db.merchants.find_one({"shopify_store_domain": data.shop_domain})
    if existing:
        raise HTTPException(status_code=400, detail="Store already registered")

    raw_key = generate_api_key()
    now = datetime.now(timezone.utc)

    doc = {
        "id": str(uuid.uuid4()),
        "name": data.shop_domain.replace(".myshopify.com", ""),
        "support_email": "",
        "mailgun_api_key": "",
        "mailgun_domain": "",
        "shopify_store_domain": data.shop_domain,
        "shopify_access_token": "",
        "whatsapp_phone_number_id": "",
        "whatsapp_waba_id": "",
        "whatsapp_access_token": "",
        "whatsapp_verify_token": "",
        "whatsapp_app_secret": "",
        # "instagram_page_id": "",        # disabled
        # "instagram_access_token": "",   # disabled
        # "instagram_app_secret": "",     # disabled
        # "instagram_verify_token": "",   # disabled
        # "twitter_api_key": "",          # disabled
        # "twitter_api_secret": "",       # disabled
        # "twitter_access_token": "",     # disabled
        # "twitter_access_token_secret": "",  # disabled
        # "twitter_bearer_token": "",     # disabled
        # "twitter_env_name": "production",   # disabled
        # "twitter_user_id": "",          # disabled
        # API key fields
        "api_key_hash": hash_api_key(raw_key),
        "api_key_prefix": get_key_prefix(raw_key),
        "permissions": data.permissions,
        "rate_limit": data.rate_limit,
        "app_name": data.app_name or "",
        "created_by": agent.get("id", "unknown"),
        "last_used_at": None,
        "installed_at": now,
        "is_active": True,
        "created_at": now,
    }
    await db.merchants.insert_one(doc)

    return {
        "shop_domain": data.shop_domain,
        "merchant_id": doc["id"],
        "api_key": raw_key,
        "api_key_prefix": doc["api_key_prefix"],
        "permissions": data.permissions,
        "rate_limit": data.rate_limit,
        "message": "Save this API key now. It will NOT be shown again.",
    }


@router.get("")
async def list_merchants(agent=Depends(get_current_agent)):
    """List all registered external merchants (API key is hidden)."""
    db = get_db()
    merchants = await db.merchants.find().sort("created_at", -1).to_list(200)
    result = []
    for m in merchants:
        result.append({
            "merchant_id": m.get("id"),
            "shop_domain": m.get("shopify_store_domain", ""),
            "app_name": m.get("app_name", ""),
            "api_key_prefix": m.get("api_key_prefix", ""),
            "permissions": m.get("permissions", []),
            "rate_limit": m.get("rate_limit", 100),
            "is_active": m.get("is_active", True),
            "last_used_at": m.get("last_used_at"),
            "installed_at": m.get("installed_at"),
            "created_at": m.get("created_at"),
            "created_by": m.get("created_by"),
        })
    return {"merchants": result, "total": len(result)}


@router.post("/{shop_domain}/regenerate-key")
async def regenerate_key(shop_domain: str, agent=Depends(get_current_agent)):
    """Generate a new API key for a merchant, invalidating the old one.

    The new raw key is returned ONCE.
    """
    db = get_db()
    merchant = await db.merchants.find_one({"shopify_store_domain": shop_domain})
    if not merchant:
        raise HTTPException(status_code=404, detail="Store not found")

    raw_key = generate_api_key()
    await db.merchants.update_one(
        {"shopify_store_domain": shop_domain},
        {"$set": {
            "api_key_hash": hash_api_key(raw_key),
            "api_key_prefix": get_key_prefix(raw_key),
        }},
    )

    return {
        "shop_domain": shop_domain,
        "api_key": raw_key,
        "api_key_prefix": get_key_prefix(raw_key),
        "message": "New API key generated. Old key is now invalid. Save this key — it will NOT be shown again.",
    }


@router.patch("/{shop_domain}/deactivate")
async def deactivate_merchant(shop_domain: str, agent=Depends(get_current_agent)):
    """Deactivate a merchant — their API key will stop working immediately."""
    db = get_db()
    result = await db.merchants.update_one(
        {"shopify_store_domain": shop_domain},
        {"$set": {"is_active": False}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    return {"shop_domain": shop_domain, "is_active": False, "message": "Store deactivated. API access revoked."}


@router.patch("/{shop_domain}/activate")
async def activate_merchant(shop_domain: str, agent=Depends(get_current_agent)):
    """Re-activate a previously deactivated merchant."""
    db = get_db()
    result = await db.merchants.update_one(
        {"shopify_store_domain": shop_domain},
        {"$set": {"is_active": True}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    return {"shop_domain": shop_domain, "is_active": True, "message": "Store reactivated. API access restored."}
