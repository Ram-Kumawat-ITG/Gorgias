# Orders router — complete draft order + regular order management via Shopify API
import asyncio
from fastapi import APIRouter, Depends, Query, HTTPException
from app.routers.auth import get_current_agent
from app.services.shopify_client import (
    shopify_get, shopify_post, shopify_put, shopify_delete, ShopifyAPIError,
)
from app.services.merchant_shopify import get_shopify_creds
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/orders", tags=["Orders"])


# ═══════════════════════════════════════════════════════
#  MODELS
# ═══════════════════════════════════════════════════════

class LineItemPayload(BaseModel):
    title: str = ""
    quantity: int = 1
    price: str = "0.00"
    variant_id: Optional[str] = None


class OrderCreatePayload(BaseModel):
    customer_id: str
    line_items: List[LineItemPayload]
    note: Optional[str] = None
    tags: Optional[str] = None
    financial_status: Optional[str] = "pending"  # "paid" | "pending"
    merchant_id: Optional[str] = None


class CancelPayload(BaseModel):
    reason: str = "other"  # customer, inventory, fraud, declined, other
    restock: bool = True
    email: bool = False
    merchant_id: Optional[str] = None


class RefundLineItem(BaseModel):
    line_item_id: str
    quantity: int
    restock: bool = True


class RefundPayload(BaseModel):
    line_items: List[RefundLineItem] = []
    shipping_full_refund: bool = False
    custom_amount: Optional[str] = None
    note: Optional[str] = None
    notify: bool = True
    merchant_id: Optional[str] = None


class FulfillPayload(BaseModel):
    line_item_ids: List[str] = []   # empty = fulfill all
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    tracking_company: Optional[str] = None
    notify: bool = True
    merchant_id: Optional[str] = None


class OrderUpdatePayload(BaseModel):
    note: Optional[str] = None
    tags: Optional[str] = None


class SendInvoicePayload(BaseModel):
    to: Optional[str] = None
    subject: Optional[str] = None
    custom_message: Optional[str] = None


# ═══════════════════════════════════════════════════════
#  FORMATTERS
# ═══════════════════════════════════════════════════════

def _format_order(o: dict) -> dict:
    """Format a Shopify order for the frontend with full detail."""
    ff = o.get("fulfillments") or []
    customer = o.get("customer") or {}
    shipping = o.get("shipping_address") or {}
    billing = o.get("billing_address") or {}
    refunds = o.get("refunds") or []
    return {
        "id": str(o["id"]),
        "type": "order",
        "name": o.get("name", ""),
        "order_number": o.get("order_number"),
        "email": o.get("email") or customer.get("email"),
        "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
        "customer_id": str(customer.get("id", "")),
        "financial_status": o.get("financial_status"),
        "fulfillment_status": o.get("fulfillment_status"),
        "total_price": o.get("total_price"),
        "subtotal_price": o.get("subtotal_price"),
        "total_tax": o.get("total_tax"),
        "total_discounts": o.get("total_discounts"),
        "currency": o.get("currency"),
        "note": o.get("note") or "",
        "tags": o.get("tags") or "",
        "cancelled_at": o.get("cancelled_at"),
        "cancel_reason": o.get("cancel_reason"),
        "closed_at": o.get("closed_at"),
        "processed_at": o.get("processed_at"),
        "line_items": [
            {
                "id": str(li["id"]),
                "title": li.get("title"),
                "variant_title": li.get("variant_title"),
                "quantity": li.get("quantity"),
                "price": li.get("price"),
                "sku": li.get("sku"),
                "variant_id": str(li["variant_id"]) if li.get("variant_id") else None,
                "product_id": str(li["product_id"]) if li.get("product_id") else None,
                "fulfillable_quantity": li.get("fulfillable_quantity", 0),
                "fulfillment_status": li.get("fulfillment_status"),
            }
            for li in o.get("line_items", [])
        ],
        "shipping_address": {
            "name": shipping.get("name") or "",
            "address1": shipping.get("address1") or "",
            "city": shipping.get("city") or "",
            "province": shipping.get("province") or "",
            "zip": shipping.get("zip") or "",
            "country": shipping.get("country") or "",
        } if shipping else None,
        "fulfillments": [
            {
                "id": str(f["id"]),
                "status": f.get("status"),
                "tracking_number": f.get("tracking_number"),
                "tracking_url": f.get("tracking_url"),
                "tracking_company": f.get("tracking_company"),
                "line_items": [str(li["id"]) for li in f.get("line_items", [])],
                "created_at": f.get("created_at"),
            }
            for f in ff
        ],
        "refunds": [
            {
                "id": str(r["id"]),
                "note": r.get("note"),
                "created_at": r.get("created_at"),
                "refund_line_items": [
                    {"line_item_id": str(rli.get("line_item_id")), "quantity": rli.get("quantity")}
                    for rli in r.get("refund_line_items", [])
                ],
            }
            for r in refunds
        ],
        "created_at": o.get("created_at"),
        "updated_at": o.get("updated_at"),
    }


def _format_draft(d: dict) -> dict:
    """Format a Shopify draft order for the frontend."""
    customer = d.get("customer") or {}
    shipping = d.get("shipping_address") or {}
    return {
        "id": str(d["id"]),
        "type": "draft",
        "name": d.get("name", ""),
        "order_number": None,
        "email": d.get("email") or customer.get("email"),
        "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
        "customer_id": str(customer.get("id", "")),
        "status": d.get("status"),  # open, invoice_sent, completed
        "total_price": d.get("total_price"),
        "subtotal_price": d.get("subtotal_price"),
        "total_tax": d.get("total_tax"),
        "currency": d.get("currency"),
        "note": d.get("note") or "",
        "tags": d.get("tags") or "",
        "order_id": str(d["order_id"]) if d.get("order_id") else None,
        "line_items": [
            {
                "id": str(li["id"]),
                "title": li.get("title"),
                "variant_title": li.get("variant_title"),
                "quantity": li.get("quantity"),
                "price": li.get("price"),
                "sku": li.get("sku"),
                "variant_id": str(li["variant_id"]) if li.get("variant_id") else None,
                "product_id": str(li["product_id"]) if li.get("product_id") else None,
            }
            for li in d.get("line_items", [])
        ],
        "shipping_address": {
            "name": shipping.get("name") or "",
            "address1": shipping.get("address1") or "",
            "city": shipping.get("city") or "",
            "province": shipping.get("province") or "",
            "zip": shipping.get("zip") or "",
            "country": shipping.get("country") or "",
        } if shipping else None,
        "invoice_url": d.get("invoice_url"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


# ═══════════════════════════════════════════════════════
#  PRODUCT SEARCH (for order creation)
# ═══════════════════════════════════════════════════════

@router.get("/products/search")
async def search_products(
    q: str = "", limit: int = Query(250, ge=1, le=250),
    since_id: str = "", agent=Depends(get_current_agent),
):
    try:
        params = {"limit": limit}
        if q:
            params["title"] = q
        if since_id:
            params["since_id"] = since_id
        data = await shopify_get("/products.json", params)
        raw = data.get("products", [])
        products = []
        for p in raw:
            images = p.get("images") or []
            img = images[0].get("src") if images else None
            for v in p.get("variants", []):
                vimg = None
                if v.get("image_id") and images:
                    for im in images:
                        if im.get("id") == v["image_id"]:
                            vimg = im.get("src"); break
                products.append({
                    "id": str(v["id"]), "product_id": str(p["id"]),
                    "title": p["title"] + (f" - {v['title']}" if v.get("title") != "Default Title" else ""),
                    "price": v.get("price", "0.00"),
                    "inventory_quantity": v.get("inventory_quantity", 0),
                    "sku": v.get("sku") or "", "variant_id": str(v["id"]),
                    "image": vimg or img,
                })
        return {"products": products, "has_more": len(raw) == limit,
                "last_product_id": str(raw[-1]["id"]) if raw else None}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ═══════════════════════════════════════════════════════
#  REGULAR ORDERS — LIST / GET / CREATE / UPDATE / CANCEL
# ═══════════════════════════════════════════════════════

@router.get("")
async def list_orders(search: str = "", limit: int = Query(50, ge=1, le=250),
                      status: str = "any", merchant_id: Optional[str] = Query(None),
                      agent=Depends(get_current_agent)):
    store_domain, access_token = await get_shopify_creds(merchant_id)
    try:
        data = await shopify_get("/orders.json", {"limit": limit, "status": status},
                                 store_domain=store_domain, access_token=access_token)
        orders = [_format_order(o) for o in data.get("orders", [])]
        if search:
            s = search.lower()
            orders = [o for o in orders
                      if s in str(o.get("order_number", "")).lower()
                      or s in (o.get("email") or "").lower()
                      or s in (o.get("customer_name") or "").lower()
                      or s in (o.get("name") or "").lower()]
        return {"orders": orders, "total": len(orders)}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/customer/{customer_id}")
async def get_orders_by_customer(customer_id: str, merchant_id: Optional[str] = Query(None),
                                  agent=Depends(get_current_agent)):
    store_domain, access_token = await get_shopify_creds(merchant_id)
    try:
        data = await shopify_get(f"/customers/{customer_id}/orders.json", {"status": "any", "limit": 50},
                                 store_domain=store_domain, access_token=access_token)
        return [_format_order(o) for o in data.get("orders", [])]
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/search")
async def search_orders_by_number(
    order_number: str = Query(..., description="Order number with or without # prefix (e.g. 1741 or #1741)"),
    merchant_id: Optional[str] = Query(None),
    agent=Depends(get_current_agent),
):
    """Fetch a specific Shopify order by order number using the name filter.
    Uses Shopify's built-in name search — returns exact match, never returns 'most recent order'.
    """
    name = order_number if order_number.startswith('#') else f"#{order_number}"
    store_domain, access_token = await get_shopify_creds(merchant_id)
    try:
        data = await shopify_get("/orders.json", {"name": name, "status": "any"},
                                 store_domain=store_domain, access_token=access_token)
        orders = [_format_order(o) for o in data.get("orders", [])]
        return {"orders": orders, "total": len(orders)}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{order_id}")
async def get_order(order_id: str, merchant_id: Optional[str] = Query(None),
                    agent=Depends(get_current_agent)):
    store_domain, access_token = await get_shopify_creds(merchant_id)
    try:
        data = await shopify_get(f"/orders/{order_id}.json",
                                 store_domain=store_domain, access_token=access_token)
        return _format_order(data.get("order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


def _build_draft_payload(data: OrderCreatePayload) -> dict:
    items = []
    for li in data.line_items:
        item = {"quantity": li.quantity, "price": li.price}
        if li.variant_id:
            item["variant_id"] = int(li.variant_id)
        else:
            item["title"] = li.title
        items.append(item)
    payload = {"draft_order": {"customer": {"id": int(data.customer_id)},
               "line_items": items, "use_customer_default_address": True}}
    if data.note:
        payload["draft_order"]["note"] = data.note
    if data.tags:
        payload["draft_order"]["tags"] = data.tags
    return payload


@router.post("")
async def create_order(data: OrderCreatePayload, agent=Depends(get_current_agent)):
    """Create draft then complete it into a confirmed order.
    financial_status='paid'    → payment_pending=false (order marked as paid immediately)
    financial_status='pending' → payment_pending=true  (order awaits payment)

    Shopify needs a moment to finish calculating taxes after draft creation before it
    can be completed — we retry with 1s / 2s / 4s delays to handle this gracefully.
    """
    store_domain, access_token = await get_shopify_creds(data.merchant_id)
    payload = _build_draft_payload(data)
    try:
        draft_result = await shopify_post("/draft_orders.json", payload,
                                         store_domain=store_domain, access_token=access_token)
        draft = draft_result.get("draft_order", {})
        payment_pending = (data.financial_status or "pending") != "paid"

        # Retry completing the draft — Shopify may not have finished tax calculation yet
        complete = None
        for attempt, delay in enumerate([1, 2, 4]):
            await asyncio.sleep(delay)
            try:
                complete = await shopify_put(
                    f"/draft_orders/{draft['id']}/complete.json",
                    {"payment_pending": payment_pending},
                    store_domain=store_domain, access_token=access_token,
                )
                break  # success
            except ShopifyAPIError as e:
                if "not finished calculating" in (e.message or "").lower() and attempt < 2:
                    continue  # wait longer and retry
                raise  # any other error or final attempt → propagate

        order_id = complete.get("draft_order", {}).get("order_id") if complete else None
        if order_id:
            return _format_order((await shopify_get(f"/orders/{order_id}.json",
                                                    store_domain=store_domain, access_token=access_token)).get("order", {}))
        return {"status": "created", "draft_order_id": str(draft["id"])}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.patch("/{order_id}")
async def update_order(order_id: str, data: OrderUpdatePayload, agent=Depends(get_current_agent)):
    payload = {}
    if data.note is not None:
        payload["note"] = data.note
    if data.tags is not None:
        payload["tags"] = data.tags
    try:
        result = await shopify_put(f"/orders/{order_id}.json", {"order": payload})
        return _format_order(result.get("order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{order_id}/cancel")
async def cancel_order(order_id: str, data: CancelPayload, agent=Depends(get_current_agent)):
    store_domain, access_token = await get_shopify_creds(data.merchant_id)
    try:
        payload = {"reason": data.reason, "restock": data.restock, "email": data.email}
        result = await shopify_post(f"/orders/{order_id}/cancel.json", payload,
                                    store_domain=store_domain, access_token=access_token)
        return _format_order(result.get("order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── REFUND ───
@router.post("/{order_id}/refund")
async def refund_order(order_id: str, data: RefundPayload, agent=Depends(get_current_agent)):
    store_domain, access_token = await get_shopify_creds(data.merchant_id)
    creds = dict(store_domain=store_domain, access_token=access_token)
    try:
        refund_payload = {"refund": {"notify": data.notify}}
        if data.note:
            refund_payload["refund"]["note"] = data.note

        location_id = None
        if data.line_items:
            # Shopify requires location_id when restocking
            has_restock = any(li.restock for li in data.line_items)
            if has_restock:
                locations = await shopify_get("/locations.json", **creds)
                locs = locations.get("locations", [])
                if locs:
                    location_id = locs[0]["id"]

            # Send client-requested quantities to calculate — Shopify will validate/cap them
            refund_payload["refund"]["refund_line_items"] = [
                {
                    "line_item_id": int(li.line_item_id),
                    "quantity": li.quantity,
                    "restock_type": "return" if li.restock else "no_restock",
                    **({"location_id": location_id} if li.restock and location_id else {}),
                }
                for li in data.line_items
            ]

        if data.shipping_full_refund:
            refund_payload["refund"]["shipping"] = {"full_refund": True}

        if data.custom_amount:
            # ── Custom-amount (partial) refund ────────────────────────────────
            # Do NOT rely on /calculate for this path — it returns nothing without line items.
            # Fetch the order's transactions directly and find the original payment.
            txns_data = await shopify_get(f"/orders/{order_id}/transactions.json", **creds)
            all_txns = txns_data.get("transactions", [])
            parent_id = None
            # Pass 1 — prefer sale / capture with success status (standard online payments)
            for t in all_txns:
                if t.get("kind") in ("sale", "capture") and t.get("status") == "success":
                    parent_id = t["id"]
                    break
            # Pass 2 — authorization with success (pre-auth then captured orders)
            if not parent_id:
                for t in all_txns:
                    if t.get("kind") == "authorization" and t.get("status") == "success":
                        parent_id = t["id"]
                        break
            # Pass 3 — any non-refund, non-void transaction that succeeded or is pending
            if not parent_id:
                for t in all_txns:
                    if t.get("kind") not in ("refund", "void") and t.get("status") in ("success", "pending"):
                        parent_id = t["id"]
                        break
            if not parent_id:
                raise HTTPException(
                    status_code=400,
                    detail="No paid transaction found to refund against. Check that the order has a completed payment transaction.",
                )
            refund_payload["refund"]["transactions"] = [
                {"parent_id": parent_id, "amount": data.custom_amount, "kind": "refund", "gateway": "manual"}
            ]
        else:
            # ── Line-item refund (full or partial by items) ───────────────────
            # Use /calculate to (1) validate and cap quantities, (2) get suggested transactions.
            calc = await shopify_post(f"/orders/{order_id}/refunds/calculate.json", refund_payload, **creds)
            calc_refund = calc.get("refund", {})

            # Replace our requested line-item quantities with Shopify's validated ones.
            # This prevents "cannot refund more items than were purchased" when quantities
            # exceed what is still refundable (e.g. prior partial refunds).
            calc_line_items = calc_refund.get("refund_line_items", [])
            if calc_line_items and data.line_items:
                restock_map = {str(int(li.line_item_id)): li.restock for li in data.line_items}
                validated = [
                    {
                        "line_item_id": item["line_item_id"],
                        "quantity": item["quantity"],
                        "restock_type": "return" if restock_map.get(str(item["line_item_id"]), False) else "no_restock",
                        **({"location_id": location_id} if restock_map.get(str(item["line_item_id"]), False) and location_id else {}),
                    }
                    for item in calc_line_items
                    if item.get("quantity", 0) > 0
                ]
                if validated:
                    refund_payload["refund"]["refund_line_items"] = validated

            # Use Shopify's suggested transactions (change kind to "refund")
            transactions = calc_refund.get("transactions", [])
            if transactions:
                for t in transactions:
                    if t.get("kind") == "suggested_refund":
                        t["kind"] = "refund"
                refund_payload["refund"]["transactions"] = transactions

        result = await shopify_post(f"/orders/{order_id}/refunds.json", refund_payload, **creds)
        return result.get("refund", {})
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── MARK AS PAID (transaction) ───
@router.post("/{order_id}/mark-paid")
async def mark_as_paid(order_id: str, merchant_id: Optional[str] = Query(None),
                       agent=Depends(get_current_agent)):
    store_domain, access_token = await get_shopify_creds(merchant_id)
    creds = dict(store_domain=store_domain, access_token=access_token)
    try:
        order_data = await shopify_get(f"/orders/{order_id}.json", **creds)
        order = order_data.get("order", {})

        if order.get("financial_status") == "paid":
            raise HTTPException(status_code=400, detail="Order is already paid")

        amount = order.get("total_price", "0.00")
        currency = order.get("currency", "USD")

        # Check if there's an existing authorization to capture
        txns = await shopify_get(f"/orders/{order_id}/transactions.json", **creds)
        auth_txn = None
        for t in txns.get("transactions", []):
            if t.get("kind") == "authorization" and t.get("status") == "success":
                auth_txn = t
                break

        if auth_txn:
            # Capture the existing authorization
            payload = {"transaction": {
                "kind": "capture", "amount": amount, "currency": currency,
                "parent_id": auth_txn["id"],
            }}
        else:
            # No authorization — use "sale" for manual payment
            payload = {"transaction": {
                "kind": "sale", "amount": amount, "currency": currency,
                "gateway": "manual",
            }}

        result = await shopify_post(f"/orders/{order_id}/transactions.json", payload, **creds)
        return result.get("transaction", {})
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── FULFILLMENT ───
@router.post("/{order_id}/fulfill")
async def fulfill_order(order_id: str, data: FulfillPayload, agent=Depends(get_current_agent)):
    store_domain, access_token = await get_shopify_creds(data.merchant_id)
    creds = dict(store_domain=store_domain, access_token=access_token)
    try:
        # Get the fulfillment order IDs (required by newer Shopify API)
        fo_data = await shopify_get(f"/orders/{order_id}/fulfillment_orders.json", **creds)
        fulfillment_orders = fo_data.get("fulfillment_orders", [])

        if not fulfillment_orders:
            raise HTTPException(status_code=400, detail="No fulfillment orders found")

        line_items_by_fo = []
        for fo in fulfillment_orders:
            if fo.get("status") not in ("open", "in_progress"):
                continue
            fo_line_items = []
            for fli in fo.get("line_items", []):
                if data.line_item_ids:
                    if str(fli.get("line_item_id")) in data.line_item_ids:
                        fo_line_items.append({"id": fli["id"], "quantity": fli["fulfillable_quantity"]})
                else:
                    if fli.get("fulfillable_quantity", 0) > 0:
                        fo_line_items.append({"id": fli["id"], "quantity": fli["fulfillable_quantity"]})
            if fo_line_items:
                line_items_by_fo.append({
                    "fulfillment_order_id": fo["id"],
                    "fulfillment_order_line_items": fo_line_items,
                })

        if not line_items_by_fo:
            raise HTTPException(status_code=400, detail="No fulfillable items found")

        payload = {
            "fulfillment": {
                "line_items_by_fulfillment_order": line_items_by_fo,
                "notify_customer": data.notify,
            }
        }
        if data.tracking_number:
            payload["fulfillment"]["tracking_info"] = {
                "number": data.tracking_number,
                "url": data.tracking_url or "",
                "company": data.tracking_company or "",
            }

        result = await shopify_post("/fulfillments.json", payload, **creds)
        return result.get("fulfillment", {})
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/fulfillments/{fulfillment_id}/cancel")
async def cancel_fulfillment(fulfillment_id: str, agent=Depends(get_current_agent)):
    try:
        result = await shopify_post(f"/fulfillments/{fulfillment_id}/cancel.json", {})
        return result.get("fulfillment", {})
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ═══════════════════════════════════════════════════════
#  DRAFT ORDERS — LIST / GET / CREATE / UPDATE / DELETE / COMPLETE / INVOICE
# ═══════════════════════════════════════════════════════

@router.get("/drafts/list")
async def list_draft_orders(limit: int = Query(50, ge=1, le=250), agent=Depends(get_current_agent)):
    try:
        data = await shopify_get("/draft_orders.json", {"limit": limit})
        return {"drafts": [_format_draft(d) for d in data.get("draft_orders", [])]}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/drafts/{draft_id}")
async def get_draft_order(draft_id: str, agent=Depends(get_current_agent)):
    try:
        data = await shopify_get(f"/draft_orders/{draft_id}.json")
        return _format_draft(data.get("draft_order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/drafts")
async def create_draft_order(data: OrderCreatePayload, agent=Depends(get_current_agent)):
    payload = _build_draft_payload(data)
    try:
        result = await shopify_post("/draft_orders.json", payload)
        return _format_draft(result.get("draft_order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/drafts/{draft_id}")
async def update_draft_order(draft_id: str, data: OrderCreatePayload, agent=Depends(get_current_agent)):
    payload = _build_draft_payload(data)
    try:
        result = await shopify_put(f"/draft_orders/{draft_id}.json", payload)
        return _format_draft(result.get("draft_order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/drafts/{draft_id}")
async def delete_draft_order(draft_id: str, agent=Depends(get_current_agent)):
    try:
        await shopify_delete(f"/draft_orders/{draft_id}.json")
        return {"status": "deleted"}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/drafts/{draft_id}/complete")
async def complete_draft_order(draft_id: str, agent=Depends(get_current_agent)):
    try:
        result = await shopify_put(f"/draft_orders/{draft_id}/complete.json", {})
        draft = result.get("draft_order", {})
        order_id = draft.get("order_id")
        if order_id:
            order_data = await shopify_get(f"/orders/{order_id}.json")
            return {"draft": _format_draft(draft), "order": _format_order(order_data.get("order", {}))}
        return {"draft": _format_draft(draft)}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/drafts/{draft_id}/send-invoice")
async def send_draft_invoice(draft_id: str, data: SendInvoicePayload, agent=Depends(get_current_agent)):
    try:
        payload = {"draft_order_invoice": {}}
        if data.to:
            payload["draft_order_invoice"]["to"] = data.to
        if data.subject:
            payload["draft_order_invoice"]["subject"] = data.subject
        if data.custom_message:
            payload["draft_order_invoice"]["custom_message"] = data.custom_message
        result = await shopify_post(f"/draft_orders/{draft_id}/send_invoice.json", payload)
        return result.get("draft_order_invoice", {})
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ═══════════════════════════════════════════════════════
#  DRAFT ORDER — INLINE EDIT (single PUT call)
# ═══════════════════════════════════════════════════════

class DraftEditPayload(BaseModel):
    line_items: List[LineItemPayload] = []
    note: Optional[str] = None
    tags: Optional[str] = None
    shipping_address: Optional[dict] = None
    discount: Optional[dict] = None  # {"type":"percentage"|"fixed_amount","value":"10","description":"..."}


@router.put("/drafts/{draft_id}/edit")
async def edit_draft_order(draft_id: str, data: DraftEditPayload, agent=Depends(get_current_agent)):
    """Full edit of a draft order — replaces line items, updates note/tags/shipping/discount."""
    try:
        items = []
        for li in data.line_items:
            item = {"quantity": li.quantity}
            if li.variant_id:
                item["variant_id"] = int(li.variant_id)
                # When variant_id is set, Shopify uses the variant's price.
                # Only send custom price if it differs from variant default.
                if li.price:
                    item["price"] = li.price
            else:
                # Custom/manual item — must have title + price
                item["title"] = li.title or "Custom item"
                item["price"] = li.price
            items.append(item)

        draft_body = {"line_items": items}
        if data.note is not None:
            draft_body["note"] = data.note
        if data.tags is not None:
            draft_body["tags"] = data.tags
        if data.shipping_address:
            draft_body["shipping_address"] = data.shipping_address
        if data.discount:
            draft_body["applied_discount"] = {
                "value_type": data.discount.get("type", "percentage"),
                "value": data.discount.get("value", "0"),
                "description": data.discount.get("description", "Discount"),
            }
        elif data.discount is None:
            # Explicitly remove discount if not provided
            pass

        print(f"Draft edit payload for {draft_id}: {draft_body}")
        result = await shopify_put(f"/draft_orders/{draft_id}.json", {"draft_order": draft_body})
        return _format_draft(result.get("draft_order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ═══════════════════════════════════════════════════════
#  REGULAR ORDER — EDIT SESSION (begin / modify / commit / discard)
# ═══════════════════════════════════════════════════════

class OrderEditCommitPayload(BaseModel):
    note: Optional[str] = None
    tags: Optional[str] = None
    line_items: List[LineItemPayload] = []
    customer_id: Optional[str] = None


@router.post("/{order_id}/edit/commit")
async def commit_order_edit(order_id: str, data: OrderEditCommitPayload, agent=Depends(get_current_agent)):
    """Commit edits to a regular order.
    Note/tags: updated directly via PUT /orders/{id}.json
    Line items: Shopify REST doesn't support editing line items on confirmed orders.
    So we: 1) create a draft with the new items, 2) complete the draft into a new order,
    3) cancel the old order. The frontend must confirm this with the user.
    """
    try:
        # Always update note/tags first
        order_payload = {}
        if data.note is not None:
            order_payload["note"] = data.note
        if data.tags is not None:
            order_payload["tags"] = data.tags
        if order_payload:
            await shopify_put(f"/orders/{order_id}.json", {"order": order_payload})

        # If line items were sent, do the draft-swap
        if data.line_items:
            # Get original order to find customer
            orig_data = await shopify_get(f"/orders/{order_id}.json")
            orig = orig_data.get("order", {})
            cust_id = data.customer_id or str((orig.get("customer") or {}).get("id", ""))

            if not cust_id:
                raise HTTPException(status_code=400, detail="No customer on this order — cannot edit line items")

            # Build new line items
            items = []
            for li in data.line_items:
                item = {"quantity": li.quantity}
                if li.variant_id:
                    item["variant_id"] = int(li.variant_id)
                else:
                    item["title"] = li.title or "Item"
                    item["price"] = li.price
                items.append(item)

            # Create a draft order with new items
            draft_payload = {
                "draft_order": {
                    "customer": {"id": int(cust_id)},
                    "line_items": items,
                    "use_customer_default_address": True,
                }
            }
            if data.note is not None:
                draft_payload["draft_order"]["note"] = data.note
            if data.tags is not None:
                draft_payload["draft_order"]["tags"] = data.tags

            # If order is paid, we must refund before cancelling
            financial = orig.get("financial_status", "")
            if financial == "paid":
                try:
                    # Calculate full refund
                    calc_payload = {"refund": {"refund_line_items": [
                        {"line_item_id": li["id"], "quantity": li["quantity"], "restock_type": "return"}
                        for li in orig.get("line_items", [])
                    ]}}
                    calc = await shopify_post(f"/orders/{order_id}/refunds/calculate.json", calc_payload)
                    calc_txns = calc.get("refund", {}).get("transactions", [])
                    calc_payload["refund"]["transactions"] = calc_txns
                    await shopify_post(f"/orders/{order_id}/refunds.json", calc_payload)
                except Exception as refund_err:
                    print(f"Warning: refund before edit failed: {refund_err}")

            print(f"Order edit: creating replacement draft for order {order_id}")
            draft_result = await shopify_post("/draft_orders.json", draft_payload)
            draft = draft_result.get("draft_order", {})
            draft_id = draft.get("id")

            # Complete the draft into a new order
            complete_result = await shopify_put(f"/draft_orders/{draft_id}/complete.json", {})
            new_order_id = complete_result.get("draft_order", {}).get("order_id")

            # Cancel the old order (restock items)
            try:
                await shopify_post(f"/orders/{order_id}/cancel.json", {"reason": "other", "restock": True})
            except Exception:
                pass  # Old order may already be cancelled/refunded

            if new_order_id:
                new_order = await shopify_get(f"/orders/{new_order_id}.json")
                return {
                    **_format_order(new_order.get("order", {})),
                    "replaced_order_id": order_id,
                    "message": f"Order #{orig.get('order_number')} was replaced with a new order.",
                }

        # No line item changes — just return updated order
        result = await shopify_get(f"/orders/{order_id}.json")
        return _format_order(result.get("order", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
