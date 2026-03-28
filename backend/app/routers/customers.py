# Customer router — Shopify-first CRUD. All data fetched from Shopify in real time.
from fastapi import APIRouter, Depends, Query, HTTPException
from app.routers.auth import get_current_agent
from app.database import get_db
from app.services.shopify_client import (
    shopify_get, shopify_post, shopify_put, shopify_delete, ShopifyAPIError,
)
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/customers", tags=["Customers"])


class CustomerCreatePayload(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country_code: str = "IN"
    tags: Optional[str] = None
    notes: Optional[str] = None


class CustomerUpdatePayload(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country_code: str = "IN"
    tags: Optional[str] = None
    notes: Optional[str] = None


def _format_customer(sc: dict) -> dict:
    """Normalize a Shopify customer object for the frontend."""
    addr = {}
    addresses = sc.get("addresses") or []
    if addresses:
        addr = addresses[0]
    return {
        "id": str(sc["id"]),
        "email": sc.get("email") or "",
        "first_name": sc.get("first_name") or "",
        "last_name": sc.get("last_name") or "",
        "company": addr.get("company") or "",
        "address": addr.get("address1") or "",
        "city": addr.get("city") or "",
        "state": addr.get("province") or "",
        "zip": addr.get("zip") or "",
        "country_code": addr.get("country_code") or "",
        "total_spent": sc.get("total_spent") or "0.00",
        "orders_count": sc.get("orders_count") or 0,
        "tags": sc.get("tags") or "",
        "notes": sc.get("note") or "",
        "created_at": sc.get("created_at"),
        "updated_at": sc.get("updated_at"),
    }


def _build_shopify_payload(data, include_email: str = None) -> dict:
    """Build Shopify customer payload from our create/update model."""
    payload = {}
    if include_email:
        payload["email"] = include_email
    if data.first_name is not None:
        payload["first_name"] = data.first_name
    if data.last_name is not None:
        payload["last_name"] = data.last_name
    if data.tags is not None:
        payload["tags"] = data.tags
    if data.notes is not None:
        payload["note"] = data.notes
    payload["verified_email"] = True
    payload["send_email_invite"] = False

    # Always send address block with country — Shopify rejects addresses without country
    addr = {}
    if data.address:
        addr["address1"] = data.address
    if data.city:
        addr["city"] = data.city
    if data.state:
        addr["province"] = data.state
    if data.zip:
        addr["zip"] = data.zip
    if data.company:
        addr["company"] = data.company

    raw = (data.country_code or "IN").strip()
    code = _resolve_country_code(raw)
    if addr:
        addr["country_code"] = code
        addr["country"] = COUNTRY_NAMES.get(code, code)
        payload["addresses"] = [addr]

    return payload


# Common country codes → full names (Shopify requires "country" field)
COUNTRY_NAMES = {
    "IN": "India",
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "JP": "Japan",
    "BR": "Brazil",
    "MX": "Mexico",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "SG": "Singapore",
    "AE": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "NZ": "New Zealand",
    "ZA": "South Africa",
    "CN": "China",
    "KR": "South Korea",
}

# Reverse lookup: full name → code (case-insensitive)
_NAME_TO_CODE = {v.lower(): k for k, v in COUNTRY_NAMES.items()}


def _resolve_country_code(raw: str) -> str:
    """Accept either 'US' or 'United States' and always return the 2-letter code."""
    upper = raw.upper()
    if upper in COUNTRY_NAMES:
        return upper  # already a valid code like "US"
    lower = raw.lower()
    if lower in _NAME_TO_CODE:
        return _NAME_TO_CODE[lower]  # "united states" → "US"
    # If 2 chars, assume it's a code Shopify knows even if we don't have it mapped
    if len(raw) == 2:
        return upper
    return "IN"  # fallback


# ─── LIST ───
@router.get("")
async def list_customers(
    search: str = "",
    limit: int = Query(50, ge=1, le=250),
    agent=Depends(get_current_agent),
):
    """Fetch customers from Shopify in real time. No MongoDB persistence."""
    try:
        params = {"limit": limit}
        if search:
            params["query"] = search
            data = await shopify_get("/customers/search.json", params)
        else:
            data = await shopify_get("/customers.json", params)
        customers = [_format_customer(c) for c in data.get("customers", [])]
        return {"customers": customers, "total": len(customers)}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── GET ONE ───
@router.get("/{customer_id}")
async def get_customer(customer_id: str, agent=Depends(get_current_agent)):
    """Fetch a single customer + their orders from Shopify in real time."""
    try:
        cust_data = await shopify_get(f"/customers/{customer_id}.json")
        customer = _format_customer(cust_data.get("customer", {}))

        orders_data = await shopify_get(
            f"/customers/{customer_id}/orders.json",
            {"status": "any", "limit": 50},
        )
        orders = []
        for o in orders_data.get("orders", []):
            ff = o.get("fulfillments") or []
            orders.append({
                "id": str(o["id"]),
                "order_number": o.get("order_number"),
                "email": o.get("email"),
                "financial_status": o.get("financial_status"),
                "fulfillment_status": o.get("fulfillment_status"),
                "total_price": o.get("total_price"),
                "currency": o.get("currency"),
                "tracking_url": ff[0].get("tracking_url") if ff else None,
                "tracking_number": ff[0].get("tracking_number") if ff else None,
                "line_items": [
                    {"title": li.get("title"), "quantity": li.get("quantity"), "price": li.get("price")}
                    for li in o.get("line_items", [])
                ],
                "created_at": o.get("created_at"),
            })

        # Ticket stats from our local DB
        db = get_db()
        email = customer["email"]
        ticket_total = await db.tickets.count_documents({"customer_email": email})
        ticket_open = await db.tickets.count_documents(
            {"customer_email": email, "status": {"$in": ["open", "pending"]}}
        )

        return {
            "customer": customer,
            "orders": orders,
            "ticket_stats": {"total": ticket_total, "open": ticket_open},
        }
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── CREATE ───
@router.post("")
async def create_customer(data: CustomerCreatePayload, agent=Depends(get_current_agent)):
    """Create a customer on Shopify."""
    payload = _build_shopify_payload(data, include_email=data.email)
    try:
        result = await shopify_post("/customers.json", {"customer": payload})
        return _format_customer(result.get("customer", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── UPDATE (email is read-only) ───
@router.patch("/{customer_id}")
async def update_customer(customer_id: str, data: CustomerUpdatePayload, agent=Depends(get_current_agent)):
    """Update a customer on Shopify. Email cannot be changed."""
    payload = _build_shopify_payload(data)
    try:
        # Fetch existing customer to get address ID (Shopify needs it to update, not duplicate)
        if "addresses" in payload:
            existing = await shopify_get(f"/customers/{customer_id}.json")
            existing_addresses = existing.get("customer", {}).get("addresses", [])
            if existing_addresses:
                payload["addresses"][0]["id"] = existing_addresses[0]["id"]

        result = await shopify_put(f"/customers/{customer_id}.json", {"customer": payload})
        return _format_customer(result.get("customer", {}))
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── DELETE ───
@router.delete("/{customer_id}")
async def delete_customer(customer_id: str, agent=Depends(get_current_agent)):
    """Delete a customer from Shopify."""
    try:
        await shopify_delete(f"/customers/{customer_id}.json")
        return {"status": "deleted"}
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
