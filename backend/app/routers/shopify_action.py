"""
Shopify action API route.
- GET  /{ticket_id}/order-details  — Shopify GraphQL order info + policy checks for QuickActionPanel
- POST /{ticket_id}                — Execute a Shopify mutation (full-refund, partial-refund, cancel, etc.)
"""
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import get_db
from app.routers.auth import get_current_agent

router = APIRouter(prefix="/shopify-action", tags=["shopify-action"])

# ── Shopify GraphQL helper ────────────────────────────────────────────────────

_GQL_QUERY = """
query GetOrderDetails($id: ID!) {
  order(id: $id) {
    id
    name
    createdAt
    cancelledAt
    displayFinancialStatus
    displayFulfillmentStatus
    totalPriceSet   { shopMoney { amount currencyCode } }
    totalRefundedSet { shopMoney { amount currencyCode } }
    lineItems(first: 20) {
      edges {
        node {
          title
          quantity
          originalUnitPriceSet { shopMoney { amount currencyCode } }
          variant {
            id
            title
            inventoryItem {
              inventoryLevels(first: 10) {
                edges { node { available } }
              }
            }
          }
        }
      }
    }
    fulfillments(first: 5) {
      displayStatus
      createdAt
      trackingInfo { number company url }
    }
    transactions(first: 10) {
      id
      kind
      status
      amountSet { shopMoney { amount currencyCode } }
      parentTransaction { id }
    }
    refunds(first: 10) {
      id
      createdAt
    }
    customer {
      id
      numberOfOrders
    }
  }
}
"""


async def _shopify_gql(order_numeric_id: str) -> dict:
    """Call Shopify GraphQL Admin API and return the `order` node."""
    domain = (settings.shopify_store_domain or "").strip()
    token = (settings.shopify_access_token or "").strip()
    if not domain or not token:
        raise HTTPException(status_code=503, detail="Shopify credentials not configured.")

    gid = f"gid://shopify/Order/{order_numeric_id}"
    url = f"https://{domain}/admin/api/2024-01/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    }
    payload = {"query": _GQL_QUERY, "variables": {"id": gid}}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=payload, headers=headers)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Shopify GraphQL returned HTTP {resp.status_code}",
        )
    body = resp.json()
    if body.get("errors"):
        raise HTTPException(status_code=502, detail=str(body["errors"]))

    order = body.get("data", {}).get("order")
    if not order:
        raise HTTPException(status_code=404, detail="Order not found in Shopify.")
    return order


# ── Policy-check helpers ─────────────────────────────────────────────────────

_ISSUE_LABELS = {
    "wrong_item":    ("Wrong item received",    "Seller error",       "amber"),
    "damaged":       ("Item arrived damaged",    "Seller error",       "amber"),
    "missing":       ("Item missing",            "Seller error",       "amber"),
    "changed_mind":  ("Changed mind",            "Customer choice",    "yellow"),
    "late":          ("Delayed delivery",        "Delayed delivery",   "yellow"),
    "other":         ("Other issue",             "Other",              "yellow"),
}

_REFUND_WINDOW_DAYS = 7  # default merchant policy


def _fmt_date(iso):  # iso: str or None → str or None
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{dt.strftime('%b')} {dt.day}"
    except Exception:
        return None


def _build_tracking(order: dict) -> list:
    fulfillments = order.get("fulfillments") or []
    first_ff = fulfillments[0] if fulfillments else {}
    ff_status = (first_ff.get("displayStatus") or "").upper()
    ff_date = _fmt_date(first_ff.get("createdAt"))

    created = _fmt_date(order.get("createdAt"))
    paid = any(
        t.get("kind") in ("SALE", "CAPTURE") and t.get("status") == "SUCCESS"
        for t in (order.get("transactions") or [])
    )
    shipped = bool(fulfillments)
    delivered = ff_status in ("DELIVERED", "IN_TRANSIT") if ff_status else False

    return [
        {"label": "Order placed",       "date": created,  "done": True},
        {"label": "Payment confirmed",  "date": created,  "done": paid},
        {"label": "Processing",         "date": None,     "done": shipped or paid},
        {"label": "Shipped",            "date": ff_date,  "done": shipped},
        {"label": "Delivered",          "date": None,     "done": delivered},
    ]


def _build_inventory(order: dict) -> list:
    result = []
    for edge in (order.get("lineItems") or {}).get("edges", []):
        node = edge["node"]
        variant = node.get("variant") or {}
        inv_item = variant.get("inventoryItem") or {}
        levels = (inv_item.get("inventoryLevels") or {}).get("edges", [])
        available = sum(
            int(e["node"].get("available") or 0) for e in levels
        )
        variant_title = (variant.get("title") or "").strip()
        if variant_title.lower() in ("", "default title"):
            variant_title = ""
        price_obj = (node.get("originalUnitPriceSet") or {}).get("shopMoney", {})
        result.append({
            "title":         node.get("title", ""),
            "variant_title": variant_title,
            "quantity":      node.get("quantity", 1),
            "price":         price_obj.get("amount", "0.00"),
            "currency":      price_obj.get("currencyCode", ""),
            "available":     available,
            "stock_label":   "In stock" if available > 0 else "Unavailable",
        })
    return result


def _build_policy(
    order: dict,
    ticket: dict,
    prior_refund_count: int,
    mins_since_last_msg,   # float or None
) -> dict:
    fin_status = (order.get("displayFinancialStatus") or "").lower()
    ful_status = (order.get("displayFulfillmentStatus") or "").lower()
    cancelled = bool(order.get("cancelledAt"))
    total_price = float((order.get("totalPriceSet") or {}).get("shopMoney", {}).get("amount") or 0)
    total_refunded = float((order.get("totalRefundedSet") or {}).get("shopMoney", {}).get("amount") or 0)

    # ── Refund window ────────────────────────────────────────────────────────
    days_since = 0
    try:
        created_iso = order.get("createdAt", "")
        if created_iso:
            created_dt = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
            days_since = (datetime.now(timezone.utc) - created_dt).days
    except Exception:
        pass
    days_left = _REFUND_WINDOW_DAYS - days_since
    if days_left > 0:
        rw = {"label": f"{days_left} day{'s' if days_left != 1 else ''} left", "color": "amber"}
    else:
        rw = {"label": "Window expired", "color": "red"}

    # ── Reason ───────────────────────────────────────────────────────────────
    issue = ticket.get("pending_action_issue", "") or ""
    _, reason_label, reason_color = _ISSUE_LABELS.get(issue, ("", "Review required", "yellow"))
    reason = {"label": reason_label, "color": reason_color}

    # ── Pickup / fulfillment ─────────────────────────────────────────────────
    if "delivered" in ful_status:
        pickup = {"label": "Delivered", "color": "green"}
    elif "shipped" in ful_status or "fulfilled" in ful_status:
        pickup = {"label": "Fulfilled", "color": "amber"}
    elif "partial" in ful_status:
        pickup = {"label": "Partial", "color": "amber"}
    else:
        pickup = {"label": "Not shipped", "color": "green"}

    # ── Payment status ───────────────────────────────────────────────────────
    fin_map = {
        "paid":                ("Paid",                 "green"),
        "partially refunded":  ("Partially refunded",   "red"),
        "refunded":            ("Fully refunded",        "red"),
        "pending":             ("Pending",               "amber"),
        "voided":              ("Voided",                "amber"),
        "authorized":          ("Authorized",            "amber"),
    }
    pay_label, pay_color = fin_map.get(fin_status, (fin_status.title(), "gray"))
    payment_status = {"label": pay_label, "color": pay_color}

    # ── Refund eligible ──────────────────────────────────────────────────────
    if total_refunded >= total_price and total_price > 0:
        refund_elig = {"label": "Already refunded", "color": "red"}
    elif total_refunded > 0:
        rem = total_price - total_refunded
        refund_elig = {"label": f"Partial refund exists — {rem:.2f} remaining", "color": "amber"}
    elif fin_status in ("paid", "authorized"):
        refund_elig = {"label": "Eligible", "color": "green"}
    else:
        refund_elig = {"label": "Not eligible", "color": "red"}

    # ── Cancel eligible ──────────────────────────────────────────────────────
    if cancelled:
        cancel_elig = {"label": "Already cancelled", "color": "red"}
    elif "fulfilled" in ful_status or "shipped" in ful_status:
        cancel_elig = {"label": "Fulfilled — cannot cancel", "color": "amber"}
    elif "partial" in ful_status:
        cancel_elig = {"label": "Partially fulfilled", "color": "amber"}
    else:
        cancel_elig = {"label": "Eligible to cancel", "color": "green"}

    # ── Customer refund history ───────────────────────────────────────────────
    if prior_refund_count == 0:
        hist = {"label": "No prior refunds", "count": 0, "color": "green"}
    elif prior_refund_count <= 2:
        hist = {"label": f"{prior_refund_count} prior refund{'s' if prior_refund_count > 1 else ''}", "count": prior_refund_count, "color": "amber"}
    else:
        hist = {"label": f"{prior_refund_count} prior refunds — high frequency", "count": prior_refund_count, "color": "red"}

    # ── 24h messaging window ──────────────────────────────────────────────────
    if mins_since_last_msg is None:
        msg_win = {"label": "Unknown", "color": "gray"}
    elif mins_since_last_msg <= 1440:  # 24 hours = 1440 minutes
        h = mins_since_last_msg / 60
        msg_win = {"label": f"Active — {h:.1f}h since last msg", "color": "green"}
    else:
        h = mins_since_last_msg / 60
        msg_win = {"label": f"Expired — {h:.1f}h since last msg", "color": "red"}

    return {
        "refund_window":    rw,
        "reason":           reason,
        "pickup":           pickup,
        "payment_status":   payment_status,
        "refund_eligible":  refund_elig,
        "cancel_eligible":  cancel_elig,
        "refund_history":   hist,
        "messaging_window": msg_win,
    }


# ── GET order-details ─────────────────────────────────────────────────────────

@router.get("/{ticket_id}/order-details")
async def get_order_details(ticket_id: str, agent=Depends(get_current_agent)):
    """
    Fetch comprehensive order data for the QuickActionPanel popup.
    Uses Shopify GraphQL Admin API for a single-roundtrip fetch.
    Also queries MongoDB for customer refund history and messaging window.
    """
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    order_id = ticket.get("pending_action_order_id", "")
    if not order_id:
        return {"order": None, "error": "No Shopify order linked to this ticket."}

    # ── Call Shopify GraphQL ──────────────────────────────────────────────────
    order = await _shopify_gql(order_id)

    # ── Customer prior-refund count (from helpdesk DB) ───────────────────────
    customer_email = ticket.get("customer_email", "")
    prior_refund_count = 0
    if customer_email:
        prior_refund_count = await db.tickets.count_documents({
            "customer_email": customer_email,
            "pending_action_type": "refund",
            "status": "resolved",
            "id": {"$ne": ticket_id},
        })

    # ── Last customer message timestamp (for 24h window) ─────────────────────
    mins_since_last_msg = None
    try:
        last_msg = await db.messages.find_one(
            {"ticket_id": ticket_id, "sender_type": "customer"},
            sort=[("created_at", -1)],
        )
        if last_msg and last_msg.get("created_at"):
            ts = last_msg["created_at"]
            if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - ts
            mins_since_last_msg = delta.total_seconds() / 60
    except Exception:
        pass

    # ── Build response ────────────────────────────────────────────────────────
    money = (order.get("totalPriceSet") or {}).get("shopMoney", {})
    refunded_money = (order.get("totalRefundedSet") or {}).get("shopMoney", {})
    total_price = money.get("amount", "0.00")
    total_refunded = float(refunded_money.get("amount") or 0)
    currency = money.get("currencyCode", "USD")
    refundable = max(0, float(total_price) - total_refunded)

    customer_orders = int((order.get("customer") or {}).get("numberOfOrders") or 0)

    created_iso = order.get("createdAt", "")
    formatted_date = _fmt_date(created_iso) or "—"

    # Refund window days left
    days_since = 0
    try:
        if created_iso:
            dt = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
            days_since = (datetime.now(timezone.utc) - dt).days
    except Exception:
        pass
    days_left = max(0, _REFUND_WINDOW_DAYS - days_since)

    return {
        "order": {
            "name":               order.get("name", ""),
            "total_price":        total_price,
            "currency":           currency,
            "formatted_date":     formatted_date,
            "financial_status":   order.get("displayFinancialStatus", ""),
            "fulfillment_status": order.get("displayFulfillmentStatus", ""),
            "cancelled":          bool(order.get("cancelledAt")),
        },
        "tracking":             _build_tracking(order),
        "inventory":            _build_inventory(order),
        "policy":               _build_policy(order, ticket, prior_refund_count, mins_since_last_msg),
        "refundable_amount":    f"{refundable:.2f}",
        "refund_window_days_left": days_left,
        "customer_order_count": customer_orders,
    }





class ShopifyActionRequest(BaseModel):
    action: str  # full-refund | partial-refund | cancel | replacement | return-label
    partial_amount: Optional[float] = None
    cancel_reason: Optional[str] = "CUSTOMER"


@router.post("/{ticket_id}")
async def execute_shopify_action(
    ticket_id: str,
    body: ShopifyActionRequest,
    agent=Depends(get_current_agent),
):
    """
    Execute a specific Shopify action on a pending_admin_action ticket.
    Used by the QuickActionPanel — supports all action types with per-type
    responses (e.g. partial refund with a specific amount).
    """
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.get("status") != "pending_admin_action":
        raise HTTPException(status_code=400, detail="Ticket is not pending admin action")

    action = body.action
    order_id = ticket.get("pending_action_order_id", "")
    order_number = ticket.get("pending_action_order_number", "")
    customer_name = ticket.get("customer_name") or "there"
    action_type = ticket.get("pending_action_type", "")

    if not order_id:
        raise HTTPException(
            status_code=400,
            detail="No Shopify order ID linked to this ticket. Cannot execute Shopify action.",
        )

    if action not in ("full-refund", "partial-refund", "cancel", "replacement", "return-label"):
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    from app.services.shopify_client import shopify_get, shopify_post, shopify_put

    now = datetime.now(timezone.utc)
    shopify_result = ""
    message = ""
    currency = ""

    # ── Execute Shopify mutation ──────────────────────────────────────────────

    if action in ("full-refund", "partial-refund"):
        # Fetch transactions to find the paid transaction
        try:
            txns = await shopify_get(f"/orders/{order_id}/transactions.json")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch order transactions: {e}")

        parent_id = None
        gateway = "manual"
        for t in txns.get("transactions", []):
            if t.get("kind") in ("sale", "capture") and t.get("status") == "success":
                parent_id = t["id"]
                gateway = t.get("gateway", "manual")
                break

        if not parent_id:
            raise HTTPException(
                status_code=422,
                detail="No successful payment transaction found for this order.",
            )

        if action == "full-refund":
            order_data = await shopify_get(f"/orders/{order_id}.json")
            total_price = order_data.get("order", {}).get("total_price", "0.00")
            currency = order_data.get("order", {}).get("currency", "")
            refund_amount = total_price
        else:
            # partial-refund
            if not body.partial_amount or body.partial_amount <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="partial_amount is required and must be greater than 0.",
                )
            refund_amount = str(round(body.partial_amount, 2))

        try:
            await shopify_post(
                f"/orders/{order_id}/refunds.json",
                {
                    "refund": {
                        "notify": True,
                        "transactions": [
                            {
                                "parent_id": parent_id,
                                "amount": refund_amount,
                                "kind": "refund",
                                "gateway": gateway,
                            }
                        ],
                    }
                },
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Shopify refund failed: {e}")

        if action == "full-refund":
            shopify_result = "refunded"
            message = (
                f"Full refund of {currency} {refund_amount} processed for order #{order_number}."
            )
        else:
            shopify_result = "partial_refunded"
            message = f"Partial refund of {refund_amount} processed for order #{order_number}."

    elif action == "cancel":
        try:
            await shopify_post(f"/orders/{order_id}/cancel.json", {})
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Shopify cancel failed: {e}")
        shopify_result = "cancelled"
        message = f"Order #{order_number} cancelled successfully."

    elif action == "replacement":
        try:
            await shopify_put(
                f"/orders/{order_id}.json",
                {
                    "order": {
                        "tags": "replacement-requested",
                        "note": f"Replacement approved by admin via helpdesk. Original order #{order_number}.",
                    }
                },
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Shopify tag update failed: {e}")
        shopify_result = "replacement_tagged"
        message = f"Replacement approved for order #{order_number}. Shopify order tagged."

    elif action == "return-label":
        try:
            await shopify_put(
                f"/orders/{order_id}.json",
                {
                    "order": {
                        "tags": "return-requested",
                        "note": f"Return approved by admin via helpdesk. Order #{order_number}.",
                    }
                },
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Shopify tag update failed: {e}")
        shopify_result = "return_tagged"
        message = f"Return approved for order #{order_number}. Shopify order tagged."

    # ── Update ticket to resolved ─────────────────────────────────────────────
    await db.tickets.update_one(
        {"id": ticket_id},
        {
            "$set": {
                "status": "resolved",
                "pending_action_approved_at": now,
                "resolved_at": now,
                "updated_at": now,
            }
        },
    )

    # ── Notify customer on original channel ──────────────────────────────────
    try:
        from app.routers.ai import _notify_customer

        type_labels = {
            "refund": "Refund",
            "replace": "Replacement",
            "return": "Return",
            "cancel": "Cancellation",
        }
        label = type_labels.get(action_type, "Request")

        outcome_lines = {
            "cancel": "If you made a payment, the refund will be processed within 5–7 business days.",
            "refund": "The refund will be credited to your original payment method within 5–7 business days.",
            "replace": "A replacement order has been created and will be shipped shortly. Tracking details will be sent to your email.",
            "return": "Your return has been initiated. Our team will be in touch with pickup/drop-off details shortly.",
        }
        outcome = outcome_lines.get(action_type, "Our team will be in touch if any further action is needed.")

        wa_msg = (
            f"🎉 Great news, {customer_name}!\n\n"
            f"Your *{label} Request* for Order *#{order_number}* has been *approved and processed*.\n\n"
            f"{outcome}\n\n"
            f"Thank you for your patience 🙏 Is there anything else I can help you with?"
        )
        email_subject = f"Your {label} Has Been Approved — Order #{order_number}"
        email_msg = (
            f"Hi {customer_name},\n\n"
            f"We're happy to let you know that your {label} request for "
            f"Order #{order_number} has been approved and processed!\n\n"
            f"{outcome}\n\n"
            f"If you have any questions, feel free to reply to this email.\n\n"
            f"Warm regards,\nSupport Team"
        )
        ig_msg = (
            f"🎉 Your {label} request for Order #{order_number} has been approved!\n\n"
            f"{outcome}\n\nLet us know if you need anything else 😊"
        )

        await _notify_customer(
            ticket=ticket,
            ticket_id=ticket_id,
            message_wa=wa_msg,
            message_email=email_msg,
            email_subject=email_subject,
            message_ig=ig_msg,
            agent_id=agent["id"],
        )
    except Exception:
        # Notification failure should not fail the overall action
        pass

    return {
        "ok": True,
        "action": action,
        "shopify_result": shopify_result,
        "message": message,
    }
