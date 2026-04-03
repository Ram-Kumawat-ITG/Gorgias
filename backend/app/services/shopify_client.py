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

# Module-level persistent client — reuses TCP connections across all requests
# Closed by the app lifespan shutdown handler via close_shopify_client()
_client: httpx.AsyncClient | None = None


def get_shopify_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


async def close_shopify_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


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


async def _request_with_retry(method: str, endpoint: str, *, store_domain: str = None, access_token: str = None, **kwargs):
    """Execute an HTTP request with automatic retry on 429 (rate limit).

    If *store_domain* and *access_token* are provided they override the
    module-level defaults so the request targets a different Shopify store.
    """
    if store_domain and access_token:
        url = f"https://{store_domain}/admin/api/2024-01{endpoint}"
        headers = {"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"}
    else:
        url = f"{SHOPIFY_BASE_URL}{endpoint}"
        headers = HEADERS
    client = get_shopify_client()
    for attempt in range(MAX_RETRIES + 1):
        r = await getattr(client, method)(url, headers=headers, **kwargs)

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


async def shopify_get(endpoint: str, params: dict = None, *, store_domain: str = None, access_token: str = None):
    return await _request_with_retry("get", endpoint, store_domain=store_domain, access_token=access_token, params=params or {})


async def shopify_post(endpoint: str, data: dict, *, store_domain: str = None, access_token: str = None):
    return await _request_with_retry("post", endpoint, store_domain=store_domain, access_token=access_token, json=data)


async def shopify_put(endpoint: str, data: dict, *, store_domain: str = None, access_token: str = None):
    return await _request_with_retry("put", endpoint, store_domain=store_domain, access_token=access_token, json=data)


async def shopify_delete(endpoint: str, *, store_domain: str = None, access_token: str = None):
    return await _request_with_retry("delete", endpoint, store_domain=store_domain, access_token=access_token)
