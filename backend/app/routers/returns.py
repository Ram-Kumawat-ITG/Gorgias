# Returns router — custom return management with tags, tracking, resolution automation
from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime, timedelta, timezone
from app.routers.auth import get_current_agent
from app.database import get_db
from app.services.shopify_client import shopify_get, ShopifyAPIError
from app.services.activity_service import log_activity
from app.services.return_service import process_resolution, update_return_tag, get_tag_for_status
from app.models.return_request import (
    ReturnCreate, ReturnStatusUpdate, ReturnTrackingUpdate, ReturnInDB,
    RETURN_STATUSES, RETURN_REASONS, RESOLUTION_TYPES,
)

router = APIRouter(prefix="/returns", tags=["Returns"])

RETURN_WINDOW_DAYS = 7        # single source of truth for return window
REPLACEMENT_WINDOW_DAYS = 7   # replacement eligibility window
REFUND_WINDOW_DAYS = 7        # refund eligibility window

WINDOW_DAYS_BY_TYPE = {
    "return": RETURN_WINDOW_DAYS,
    "replace": REPLACEMENT_WINDOW_DAYS,
    "replacement": REPLACEMENT_WINDOW_DAYS,
    "refund": REFUND_WINDOW_DAYS,
}

VALID_TRANSITIONS = {
    "requested": ["approved", "rejected"],
    "approved": ["shipped", "rejected", "cancelled"],
    "shipped": ["received", "cancelled"],
    "received": [],       # resolved is automated
    "resolved": [],
    "rejected": [],
    "cancelled": [],
}


# ─── STATS (must be before /{return_id} to avoid route conflict) ───
@router.get("/stats/overview")
async def return_stats(agent=Depends(get_current_agent)):
    db = get_db()
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    results = await db.returns.aggregate(pipeline).to_list(10)
    by_status = {r["_id"]: r["count"] for r in results}
    res_pipeline = [{"$group": {"_id": "$resolution", "count": {"$sum": 1}}}]
    res_results = await db.returns.aggregate(res_pipeline).to_list(10)
    by_resolution = {r["_id"]: r["count"] for r in res_results}
    total = await db.returns.count_documents({})
    return {"total": total, "by_status": by_status, "by_resolution": by_resolution}


# ─── RETURNS FOR AN ORDER (must be before /{return_id}) ───
@router.get("/order/{order_id}")
async def get_returns_for_order(order_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    returns = await db.returns.find({"order_id": order_id}).sort("created_at", -1).to_list(20)
    for r in returns:
        r["_id"] = str(r["_id"])
    return returns


# ─── LIST ───
@router.get("")
async def list_returns(
    status: str = "", resolution: str = "", days: int = Query(0, ge=0),
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    agent=Depends(get_current_agent),
):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    if resolution:
        query["resolution"] = resolution
    if days > 0:
        query["created_at"] = {"$gte": datetime.now(timezone.utc) - timedelta(days=days)}
    total = await db.returns.count_documents(query)
    skip = (page - 1) * limit
    returns = await db.returns.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    for r in returns:
        r["_id"] = str(r["_id"])
    return {"returns": returns, "total": total, "page": page, "limit": limit}


# ─── INVENTORY CHECK (must be before /{return_id}) ───
@router.get("/{return_id}/inventory")
async def check_return_inventory(return_id: str, agent=Depends(get_current_agent)):
    """Read-only: fetch current Shopify inventory for each returned item."""
    db = get_db()
    ret = await db.returns.find_one({"id": return_id})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    try:
        order_data = await shopify_get(f"/orders/{ret['order_id']}.json")
        order = order_data.get("order", {})
    except ShopifyAPIError as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch order: {e.message}")

    # Build lookup: line_item_id → variant_id
    order_line_items = {str(li["id"]): li for li in order.get("line_items", [])}

    results = []
    for item in ret.get("items", []):
        entry = {
            "title": item.get("title", ""),
            "variant_title": item.get("variant_title"),
            "sku": item.get("sku"),
            "inventory_quantity": None,
            "inventory_policy": None,
            "error": None,
        }
        line_item = order_line_items.get(str(item.get("line_item_id", "")))
        if not line_item:
            entry["error"] = "Line item not found in order"
            results.append(entry)
            continue

        variant_id = line_item.get("variant_id")
        if not variant_id:
            entry["error"] = "No variant ID on line item"
            results.append(entry)
            continue

        try:
            variant_data = await shopify_get(f"/variants/{variant_id}.json")
            variant = variant_data.get("variant", {})
            entry["variant_id"] = str(variant_id)
            entry["inventory_quantity"] = variant.get("inventory_quantity")
            entry["inventory_policy"] = variant.get("inventory_management")  # "shopify" or null
        except ShopifyAPIError:
            entry["error"] = "Could not fetch variant from Shopify"

        results.append(entry)

    return {"items": results}


# ─── ORDER-LEVEL POLICY CHECK (no return record required) ───
@router.get("/order/{order_id}/policy-check")
async def order_policy_check(
    order_id: str,
    ticket_type: str = Query(None, description="Ticket type: return, replace, refund"),
    customer_email: str = Query(None, description="Customer email for history lookup"),
    agent=Depends(get_current_agent),
):
    """Return/replacement/refund window & payment policy for an order — works even without a return record."""
    db = get_db()
    window_baseline = None
    baseline_label = None
    financial_status = "unknown"
    order_customer_email = customer_email
    try:
        order_data = await shopify_get(f"/orders/{order_id}.json")
        order = order_data.get("order", {})
        financial_status = order.get("financial_status", "unknown")
        if not order_customer_email:
            order_customer_email = order.get("email") or order.get("contact_email")
        fulfillments = order.get("fulfillments") or []
        if fulfillments:
            raw = fulfillments[-1].get("created_at") or ""
            if raw:
                window_baseline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                baseline_label = "fulfillment"
        else:
            # Order not yet fulfilled — policy window hasn't started
            baseline_label = "not_fulfilled"
    except Exception:
        pass

    if window_baseline and window_baseline.tzinfo is None:
        window_baseline = window_baseline.replace(tzinfo=timezone.utc)

    # Use ticket-type-specific window days
    window_days = WINDOW_DAYS_BY_TYPE.get(ticket_type, RETURN_WINDOW_DAYS)

    within_window = None
    days_since_baseline = None
    if window_baseline:
        now = datetime.now(timezone.utc)
        days_since_baseline = (now - window_baseline).days
        within_window = days_since_baseline <= window_days

    # ── Customer ticket history by type ──────────────────────────────────────
    prior_refunds = 0
    prior_replacements = 0
    prior_returns = 0
    if order_customer_email:
        prior_refunds = await db.tickets.count_documents({
            "customer_email": order_customer_email,
            "ticket_type": "refund",
            "status": "resolved",
        })
        prior_replacements = await db.tickets.count_documents({
            "customer_email": order_customer_email,
            "ticket_type": {"$in": ["replace", "replacement"]},
            "status": "resolved",
        })
        prior_returns = await db.tickets.count_documents({
            "customer_email": order_customer_email,
            "ticket_type": "return",
            "status": "resolved",
        })

    return {
        "return_window": {
            "pass": within_window,
            "days": window_days,
            "days_since_baseline": days_since_baseline,
            "baseline": baseline_label,
        },
        "financial_status": financial_status,
        "prior_refunds": {"count": prior_refunds},
        "prior_replacements": {"count": prior_replacements},
        "prior_returns": {"count": prior_returns},
    }


# ─── POLICY CHECK ───
@router.get("/{return_id}/policy-check")
async def return_policy_check(return_id: str, agent=Depends(get_current_agent)):
    """Evaluate return eligibility policy checks for a given return request."""
    db = get_db()
    ret = await db.returns.find_one({"id": return_id})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    # ── 1. Return window (7 days from fulfillment date, fallback to order created_at) ──
    window_baseline = None
    baseline_label = None
    try:
        order_data = await shopify_get(f"/orders/{ret['order_id']}.json")
        order = order_data.get("order", {})
        fulfillments = order.get("fulfillments") or []
        if fulfillments:
            raw = fulfillments[-1].get("created_at") or ""
            if raw:
                window_baseline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                baseline_label = "fulfillment"
        else:
            # Order not yet fulfilled — policy window hasn't started
            baseline_label = "not_fulfilled"
    except Exception:
        pass

    return_requested_at = ret.get("created_at")
    if isinstance(return_requested_at, str):
        return_requested_at = datetime.fromisoformat(return_requested_at.replace("Z", "+00:00"))
    if return_requested_at and return_requested_at.tzinfo is None:
        return_requested_at = return_requested_at.replace(tzinfo=timezone.utc)
    if window_baseline and window_baseline.tzinfo is None:
        window_baseline = window_baseline.replace(tzinfo=timezone.utc)

    within_window = None
    days_since_baseline = None
    if window_baseline:
        # Use current time so remaining days decrease daily (not frozen at filing date)
        now = datetime.now(timezone.utc)
        days_since_baseline = (now - window_baseline).days
        within_window = days_since_baseline <= RETURN_WINDOW_DAYS

    # ── 2. Reason eligibility ────────────────────────────────────────────────
    SELLER_ERROR_REASONS = {"wrong_item", "defective", "size_issue", "damaged_in_shipping", "not_as_described"}
    INELIGIBLE_REASONS = {"changed_mind"}
    reason = ret.get("reason", "")
    if reason in SELLER_ERROR_REASONS:
        reason_status = "eligible"
        reason_label = "Seller error"
    elif reason in INELIGIBLE_REASONS:
        reason_status = "not_eligible"
        reason_label = "Customer decision"
    else:
        reason_status = "review"
        reason_label = "Review required"

    # ── 3. Return pickup initiated ───────────────────────────────────────────
    PICKUP_INITIATED_STATUSES = {"shipped", "received", "resolved"}
    pickup_initiated = ret.get("status") in PICKUP_INITIATED_STATUSES

    # ── 4. Customer return history (all non-cancelled returns, excluding this one) ──
    customer_email = ret.get("customer_email")
    prior_count = await db.returns.count_documents({
        "customer_email": customer_email,
        "id": {"$ne": ret.get("id")},
        "status": {"$nin": ["cancelled"]},
    })

    # ── 5. Customer ticket history by type (resolved tickets) ──
    prior_refunds = 0
    prior_replacements = 0
    prior_returns_tickets = 0
    if customer_email:
        prior_refunds = await db.tickets.count_documents({
            "customer_email": customer_email,
            "ticket_type": "refund",
            "status": "resolved",
        })
        prior_replacements = await db.tickets.count_documents({
            "customer_email": customer_email,
            "ticket_type": {"$in": ["replace", "replacement"]},
            "status": "resolved",
        })
        prior_returns_tickets = await db.tickets.count_documents({
            "customer_email": customer_email,
            "ticket_type": "return",
            "status": "resolved",
        })

    return {
        "return_window": {
            "pass": within_window,
            "days": RETURN_WINDOW_DAYS,
            "days_since_baseline": days_since_baseline,
            "baseline": baseline_label,
        },
        "reason_eligibility": {
            "status": reason_status,
            "reason": reason,
            "label": reason_label,
        },
        "pickup_initiated": {
            "pass": pickup_initiated,
            "current_status": ret.get("status"),
        },
        "prior_returns": {
            "count": prior_count,
        },
        "prior_refunds": {"count": prior_refunds},
        "prior_replacements": {"count": prior_replacements},
        "prior_returns_tickets": {"count": prior_returns_tickets},
    }


# ─── GET ONE ───
@router.get("/{return_id}")
async def get_return(return_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    ret = await db.returns.find_one({"id": return_id})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    ret["_id"] = str(ret["_id"])
    return ret


# ─── CREATE (admin) ───
@router.post("")
async def create_return(data: ReturnCreate, agent=Depends(get_current_agent)):
    db = get_db()
    if data.reason not in RETURN_REASONS:
        raise HTTPException(status_code=400, detail=f"Invalid reason")
    if data.resolution not in RESOLUTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid resolution")
    if not data.items:
        raise HTTPException(status_code=400, detail="At least one item required")

    try:
        order_data = await shopify_get(f"/orders/{data.order_id}.json")
        order = order_data.get("order", {})
    except ShopifyAPIError as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch order: {e.message}")

    customer = order.get("customer") or {}
    tag = get_tag_for_status("requested")

    ret = ReturnInDB(
        order_id=data.order_id,
        order_number=order.get("order_number"),
        customer_email=order.get("email") or customer.get("email") or "",
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
        customer_id=str(customer.get("id", "")),
        items=[item.model_dump() for item in data.items],
        reason=data.reason, reason_notes=data.reason_notes,
        resolution=data.resolution, return_tag=tag,
        images=data.images or [],
        status_history=[{
            "status": "requested", "timestamp": datetime.now(timezone.utc),
            "actor_type": "admin", "actor_id": agent["id"],
            "actor_name": agent.get("full_name", ""), "note": "Return created by admin",
        }],
        initiated_by="admin", initiated_by_id=agent["id"],
    )
    doc = ret.model_dump()
    await db.returns.insert_one(doc)
    doc.pop("_id", None)

    # Apply tag to Shopify order
    await update_return_tag(data.order_id, tag)

    await log_activity(
        entity_type="return", entity_id=ret.id, event="return.created",
        actor_type="admin", actor_id=agent["id"], actor_name=agent.get("full_name", ""),
        description=f"Return request for order #{order.get('order_number')} — {data.resolution}",
        customer_email=ret.customer_email,
    )
    return doc


# ─── CREATE (customer — no auth) ───
@router.post("/customer-initiate")
async def create_return_customer(data: ReturnCreate):
    db = get_db()
    if data.reason not in RETURN_REASONS:
        raise HTTPException(status_code=400, detail="Invalid reason")
    if data.resolution not in RESOLUTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid resolution")
    if not data.items:
        raise HTTPException(status_code=400, detail="At least one item required")

    try:
        order_data = await shopify_get(f"/orders/{data.order_id}.json")
        order = order_data.get("order", {})
    except ShopifyAPIError as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch order: {e.message}")

    customer = order.get("customer") or {}
    tag = get_tag_for_status("requested")

    ret = ReturnInDB(
        order_id=data.order_id,
        order_number=order.get("order_number"),
        customer_email=order.get("email") or customer.get("email") or "",
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
        customer_id=str(customer.get("id", "")),
        items=[item.model_dump() for item in data.items],
        reason=data.reason, reason_notes=data.reason_notes,
        resolution=data.resolution, return_tag=tag,
        images=data.images or [],
        status_history=[{
            "status": "requested", "timestamp": datetime.now(timezone.utc),
            "actor_type": "customer", "note": "Return created by customer",
        }],
        initiated_by="customer",
    )
    doc = ret.model_dump()
    await db.returns.insert_one(doc)
    doc.pop("_id", None)
    await update_return_tag(data.order_id, tag)
    return doc


# ─── UPDATE STATUS ───
@router.post("/{return_id}/status")
async def update_return_status(return_id: str, data: ReturnStatusUpdate, agent=Depends(get_current_agent)):
    db = get_db()
    ret = await db.returns.find_one({"id": return_id})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    current = ret["status"]
    new_status = data.status

    if new_status not in RETURN_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status")

    valid_next = VALID_TRANSITIONS.get(current, [])
    if new_status not in valid_next:
        raise HTTPException(status_code=400, detail=f"Cannot go from '{current}' to '{new_status}'. Valid: {', '.join(valid_next) or 'none'}")

    tag = get_tag_for_status(new_status, ret.get("resolution", ""))
    status_entry = {
        "status": new_status, "timestamp": datetime.now(timezone.utc),
        "actor_type": "admin", "actor_id": agent["id"],
        "actor_name": agent.get("full_name", ""),
        "note": data.note or f"Status → {new_status}",
    }
    updates = {"status": new_status, "return_tag": tag, "updated_at": datetime.now(timezone.utc)}

    await db.returns.update_one(
        {"id": return_id},
        {"$set": updates, "$push": {"status_history": status_entry}},
    )
    await update_return_tag(ret["order_id"], tag)
    await log_activity(
        entity_type="return", entity_id=return_id,
        event=f"return.{new_status}", actor_type="admin",
        actor_id=agent["id"], actor_name=agent.get("full_name", ""),
        description=f"Return {current} → {new_status}",
        customer_email=ret.get("customer_email"),
    )

    # AUTOMATION: received → auto-resolve
    if new_status == "received":
        updated = await db.returns.find_one({"id": return_id})
        result = await process_resolution(updated)
        return {"status": "received", "resolution_result": result}

    return {"status": new_status, "previous": current}


# ─── ADD TRACKING ───
@router.post("/{return_id}/tracking")
async def add_tracking(return_id: str, data: ReturnTrackingUpdate, agent=Depends(get_current_agent)):
    db = get_db()
    ret = await db.returns.find_one({"id": return_id})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    if ret["status"] not in ("approved", "shipped"):
        raise HTTPException(status_code=400, detail="Tracking can only be added after approval")

    updates = {
        "tracking_number": data.tracking_number,
        "courier": data.courier,
        "tracking_status": "pending",
        "updated_at": datetime.now(timezone.utc),
    }

    # Auto-transition to shipped if still approved
    if ret["status"] == "approved":
        tag = get_tag_for_status("shipped")
        updates["status"] = "shipped"
        updates["return_tag"] = tag
        status_entry = {
            "status": "shipped", "timestamp": datetime.now(timezone.utc),
            "actor_type": "admin", "actor_id": agent["id"],
            "actor_name": agent.get("full_name", ""),
            "note": f"Tracking added: {data.courier} #{data.tracking_number}",
        }
        await db.returns.update_one(
            {"id": return_id},
            {"$set": updates, "$push": {"status_history": status_entry}},
        )
        await update_return_tag(ret["order_id"], tag)
    else:
        await db.returns.update_one({"id": return_id}, {"$set": updates})

    await log_activity(
        entity_type="return", entity_id=return_id,
        event="return.tracking_added", actor_type="admin",
        description=f"Tracking: {data.courier} #{data.tracking_number}",
        customer_email=ret.get("customer_email"),
    )
    return {"status": "tracking_added", "courier": data.courier, "tracking_number": data.tracking_number}


# ─── CHECK TRACKING STATUS (manual poll — no courier API yet) ───
@router.post("/{return_id}/tracking/check")
async def check_tracking(return_id: str, agent=Depends(get_current_agent)):
    """Placeholder for courier API integration. For now, returns current tracking info.
    When a courier API is integrated (e.g. AfterShip), this will poll the API and
    auto-update status to 'received' when delivery is confirmed."""
    db = get_db()
    ret = await db.returns.find_one({"id": return_id})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    # TODO: Integrate courier API here. Recommended: AfterShip (free tier: 50 trackings/month)
    # When integrated:
    # 1. Call AfterShip GET /trackings/{courier}/{tracking_number}
    # 2. If delivery confirmed → auto-update status to "received" → trigger resolution
    # 3. Store latest tracking events in the return record

    await db.returns.update_one(
        {"id": return_id},
        {"$set": {"tracking_last_checked": datetime.now(timezone.utc)}},
    )
    return {
        "tracking_number": ret.get("tracking_number"),
        "courier": ret.get("courier"),
        "tracking_status": ret.get("tracking_status", "pending"),
        "note": "Courier API not yet integrated. Use 'Mark as Received' to manually confirm delivery.",
    }


# ─── CANCEL RETURN (only before received) ───
@router.post("/{return_id}/cancel")
async def cancel_return(return_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    ret = await db.returns.find_one({"id": return_id})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    if ret["status"] in ("received", "resolved"):
        raise HTTPException(status_code=400, detail="Cannot cancel after item is received")
    if ret["status"] in ("cancelled", "rejected"):
        raise HTTPException(status_code=400, detail="Return is already cancelled/rejected")

    status_entry = {
        "status": "cancelled", "timestamp": datetime.now(timezone.utc),
        "actor_type": "admin", "actor_id": agent["id"],
        "actor_name": agent.get("full_name", ""),
        "note": "Return cancelled",
    }
    await db.returns.update_one(
        {"id": return_id},
        {"$set": {"status": "cancelled", "return_tag": "", "updated_at": datetime.now(timezone.utc)},
         "$push": {"status_history": status_entry}},
    )
    # Remove return tag from order
    await update_return_tag(ret["order_id"], "")
    return {"status": "cancelled"}


# ─── DELETE ───
@router.delete("/{return_id}")
async def delete_return(return_id: str, agent=Depends(get_current_agent)):
    db = get_db()
    ret = await db.returns.find_one({"id": return_id})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    if ret["status"] == "resolved":
        raise HTTPException(status_code=400, detail="Cannot delete a resolved return")
    await db.returns.delete_one({"id": return_id})
    # Remove tag from order
    await update_return_tag(ret["order_id"], "")
    return {"status": "deleted"}
