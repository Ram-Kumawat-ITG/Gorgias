# merchant_shopify.py — resolve per-merchant Shopify credentials from DB
# Every Shopify API call should use this instead of reading directly from .env.
#
# Usage:
#   store_domain, access_token = await get_shopify_creds(merchant_id="abc123")
#   data = await shopify_get("/orders.json", {}, store_domain=store_domain, access_token=access_token)
#
# When merchant_id is absent (or the merchant record has no token), both values
# return as None — the Shopify client then falls back to the .env defaults,
# which is correct for single-store / dev deployments.

from app.database import get_db


async def get_shopify_creds(
    merchant_id: str = None,
    store_domain: str = None,
) -> tuple[str | None, str | None]:
    """Return (store_domain, access_token) for a merchant from the DB.

    Lookup priority:
      1. merchant_id  → db.merchants.find_one({"id": merchant_id})
      2. store_domain → db.merchants.find_one({"shopify_store_domain": store_domain})
      3. Neither provided → (None, None)  → caller uses .env defaults

    Returns (None, None) if the merchant is not found or has no token stored,
    so callers never need to guard against missing values.
    """
    if not merchant_id and not store_domain:
        return None, None

    db = get_db()
    merchant = None

    if merchant_id:
        merchant = await db.merchants.find_one({"id": merchant_id})
    if not merchant and store_domain:
        merchant = await db.merchants.find_one({"shopify_store_domain": store_domain})

    if not merchant:
        return None, None

    token = merchant.get("shopify_access_token") or ""
    domain = merchant.get("shopify_store_domain") or ""

    # Only return per-merchant creds when BOTH are present and non-empty
    if token and domain:
        return domain, token

    return None, None
