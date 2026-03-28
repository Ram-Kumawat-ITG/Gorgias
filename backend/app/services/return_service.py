# Return service — tag management, resolution automation, tracking helpers
from datetime import datetime
from app.database import get_db
from app.services.shopify_client import shopify_get, shopify_post, shopify_put, ShopifyAPIError
from app.services.activity_service import log_activity
from app.models.return_request import STATUS_TAGS, ALL_RETURN_TAGS


# ═══════════════════════════════════════════════════════
#  SHOPIFY ORDER TAG MANAGEMENT
# ═══════════════════════════════════════════════════════

async def update_return_tag(order_id: str, new_tag: str):
    """Remove old return tags from a Shopify order and apply the new one."""
    try:
        order_data = await shopify_get(f"/orders/{order_id}.json")
        order = order_data.get("order", {})
        existing_tags = [t.strip() for t in (order.get("tags") or "").split(",") if t.strip()]

        # Remove all existing return tags
        cleaned = [t for t in existing_tags if t not in ALL_RETURN_TAGS]

        # Add new tag
        if new_tag:
            cleaned.append(new_tag)

        new_tags_str = ", ".join(cleaned)
        await shopify_put(f"/orders/{order_id}.json", {"order": {"tags": new_tags_str}})
        return new_tags_str
    except Exception as e:
        print(f"Warning: failed to update return tag on order {order_id}: {e}")
        return None


def get_tag_for_status(status: str, resolution: str = "") -> str:
    """Get the Shopify tag for a given return status."""
    if status == "resolved":
        return STATUS_TAGS.get(f"resolved_{resolution}", "")
    return STATUS_TAGS.get(status, "")


# ═══════════════════════════════════════════════════════
#  RESOLUTION AUTOMATION
# ═══════════════════════════════════════════════════════

async def process_resolution(return_doc: dict) -> dict:
    """Called when status reaches 'received'. Auto-resolves via refund or replacement."""
    db = get_db()
    return_id = return_doc["id"]
    resolution = return_doc["resolution"]
    order_id = return_doc["order_id"]

    try:
        if resolution == "refund":
            result = await _process_refund(order_id, return_doc.get("items", []))
            tag = get_tag_for_status("resolved", "refund")
            updates = {
                "status": "resolved", "resolved_at": datetime.utcnow(),
                "refund_id": result.get("refund_id"), "return_tag": tag,
                "updated_at": datetime.utcnow(),
            }
            note = f"Refund processed. ID: {result.get('refund_id', 'N/A')}"

        elif resolution == "replacement":
            result = await _create_replacement_order(return_doc)
            if result.get("out_of_stock"):
                # Pause — notify admin, don't resolve yet
                await log_activity(
                    entity_type="return", entity_id=return_id,
                    event="return.replacement_paused", actor_type="system",
                    description=f"Replacement paused: {result['out_of_stock_items']} out of stock",
                    customer_email=return_doc.get("customer_email"),
                )
                return {"error": f"Out of stock: {result['out_of_stock_items']}. Admin action required."}

            tag = get_tag_for_status("resolved", "replacement")
            updates = {
                "status": "resolved", "resolved_at": datetime.utcnow(),
                "replacement_order_id": result.get("order_id"), "return_tag": tag,
                "updated_at": datetime.utcnow(),
            }
            note = f"Replacement order created. ID: {result.get('order_id', 'N/A')}"
        else:
            return {"error": f"Unknown resolution: {resolution}"}

        # Update return record
        status_entry = {
            "status": "resolved", "timestamp": datetime.utcnow(),
            "actor_type": "system", "note": note,
        }
        await db.returns.update_one(
            {"id": return_id},
            {"$set": updates, "$push": {"status_history": status_entry}},
        )

        # Update Shopify order tag
        await update_return_tag(order_id, tag)

        await log_activity(
            entity_type="return", entity_id=return_id,
            event="return.resolved", actor_type="system",
            description=note, customer_email=return_doc.get("customer_email"),
            metadata={"resolution": resolution, "result": result},
        )
        return {"status": "resolved", **result}

    except Exception as e:
        error_note = f"Auto-resolution failed: {str(e)}"
        await db.returns.update_one(
            {"id": return_id},
            {"$push": {"status_history": {
                "status": "received", "timestamp": datetime.utcnow(),
                "actor_type": "system", "note": error_note,
            }}},
        )
        return {"error": error_note}


async def _process_refund(order_id: str, items: list) -> dict:
    """Refund returned items using existing Shopify refund flow."""
    locations = await shopify_get("/locations.json")
    locs = locations.get("locations", [])
    location_id = locs[0]["id"] if locs else None

    refund_line_items = []
    for item in items:
        entry = {
            "line_item_id": int(item["line_item_id"]),
            "quantity": item["quantity"],
            "restock_type": "return",
        }
        if location_id:
            entry["location_id"] = location_id
        refund_line_items.append(entry)

    calc_payload = {"refund": {"refund_line_items": refund_line_items}}
    calc = await shopify_post(f"/orders/{order_id}/refunds/calculate.json", calc_payload)
    transactions = calc.get("refund", {}).get("transactions", [])
    for t in transactions:
        if t.get("kind") == "suggested_refund":
            t["kind"] = "refund"

    refund_payload = {
        "refund": {
            "refund_line_items": refund_line_items,
            "transactions": transactions,
            "notify": True,
        }
    }
    result = await shopify_post(f"/orders/{order_id}/refunds.json", refund_payload)
    return {"refund_id": str(result.get("refund", {}).get("id", ""))}


async def _create_replacement_order(return_doc: dict) -> dict:
    """Create zero-charge replacement order after stock verification."""
    customer_id = return_doc.get("customer_id")
    if not customer_id:
        raise Exception("No customer ID — cannot create replacement")

    # Fetch original order to get variant IDs
    order_data = await shopify_get(f"/orders/{return_doc['order_id']}.json")
    order = order_data.get("order", {})
    order_items = {str(li["id"]): li for li in order.get("line_items", [])}

    # Stock check
    out_of_stock = []
    line_items = []
    for item in return_doc.get("items", []):
        oli = order_items.get(str(item["line_item_id"]), {})
        variant_id = oli.get("variant_id")

        if variant_id:
            # Check inventory
            try:
                prod_data = await shopify_get(f"/variants/{variant_id}.json")
                variant = prod_data.get("variant", {})
                available = variant.get("inventory_quantity", 0)
                if available < item["quantity"]:
                    out_of_stock.append(f"{item['title']} (need {item['quantity']}, have {available})")
            except Exception:
                pass  # Can't check — proceed anyway
            line_items.append({"variant_id": variant_id, "quantity": item["quantity"]})
        else:
            line_items.append({
                "title": item["title"], "price": "0.00", "quantity": item["quantity"],
            })

    if out_of_stock:
        return {"out_of_stock": True, "out_of_stock_items": ", ".join(out_of_stock)}

    # Create draft with zero charge (applied_discount covers full amount)
    draft_payload = {
        "draft_order": {
            "customer": {"id": int(customer_id)},
            "line_items": line_items,
            "use_customer_default_address": True,
            "note": f"Replacement for return {return_doc['id']} (order #{return_doc.get('order_number')})",
            "tags": "replacement, return",
            "applied_discount": {
                "value_type": "percentage",
                "value": "100",
                "description": "Replacement order — no charge",
            },
        }
    }
    draft_result = await shopify_post("/draft_orders.json", draft_payload)
    draft = draft_result.get("draft_order", {})
    draft_id = draft.get("id")

    complete = await shopify_put(f"/draft_orders/{draft_id}/complete.json", {})
    new_order_id = complete.get("draft_order", {}).get("order_id")

    return {"order_id": str(new_order_id or ""), "draft_id": str(draft_id)}
