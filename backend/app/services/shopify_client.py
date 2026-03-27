# Shopify REST Admin API client — all Shopify API calls go through here
# Includes automatic retry on 429 rate limits with exponential backoff
import asyncio
import httpx
from app.config import settings

SHOPIFY_BASE_URL = f"https://{settings.shopify_store_domain}/admin/api/2024-01"
HEADERS = {
    "X-Shopify-Access-Token": settings.shopify_access_token,
    "Content-Type": "application/json",
}
MAX_RETRIES = 3


class ShopifyAPIError(Exception):
    def __init__(self, status_code: int, errors: dict, message: str = ""):
        self.status_code = status_code
        self.errors = errors
        self.message = message or str(errors)
        super().__init__(self.message)


def _parse_shopify_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        errors = body.get("errors", body.get("error", ""))
        if isinstance(errors, dict):
            parts = []
            for field, msgs in errors.items():
                if isinstance(msgs, list):
                    parts.append(f"{field}: {', '.join(msgs)}")
                else:
                    parts.append(f"{field}: {msgs}")
            return "; ".join(parts)
        return str(errors)
    except Exception:
        return response.text


async def _request_with_retry(method: str, endpoint: str, **kwargs):
    """Execute an HTTP request with automatic retry on 429 (rate limit)."""
    url = f"{SHOPIFY_BASE_URL}{endpoint}"
    for attempt in range(MAX_RETRIES + 1):
        async with httpx.AsyncClient() as client:
            r = await getattr(client, method)(url, headers=HEADERS, timeout=30.0, **kwargs)

        if r.status_code == 429:
            retry_after = float(r.headers.get("Retry-After", 2.0))
            wait = max(retry_after, 1.0 * (attempt + 1))
            print(f"Shopify 429 rate limit on {method.upper()} {endpoint}, retrying in {wait}s (attempt {attempt + 1})")
            await asyncio.sleep(wait)
            continue

        if r.status_code >= 400:
            detail = _parse_shopify_error(r)
            print(f"Shopify {method.upper()} {endpoint} failed ({r.status_code}): {detail}")
            raise ShopifyAPIError(r.status_code, {}, detail)

        # DELETE returns 200 with empty body
        if r.status_code == 200 and not r.text.strip():
            return {}
        try:
            return r.json()
        except Exception:
            return {}

    raise ShopifyAPIError(429, {}, "Rate limit exceeded after retries")


async def shopify_get(endpoint: str, params: dict = None):
    return await _request_with_retry("get", endpoint, params=params or {})


async def shopify_post(endpoint: str, data: dict):
    return await _request_with_retry("post", endpoint, json=data)


async def shopify_put(endpoint: str, data: dict):
    return await _request_with_retry("put", endpoint, json=data)


async def shopify_delete(endpoint: str):
    return await _request_with_retry("delete", endpoint)
