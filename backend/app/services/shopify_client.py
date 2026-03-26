# Shopify REST Admin API client — all Shopify API calls go through here
import httpx
from app.config import settings

SHOPIFY_BASE_URL = f"https://{settings.shopify_store_domain}/admin/api/2024-01"
HEADERS = {
    "X-Shopify-Access-Token": settings.shopify_access_token,
    "Content-Type": "application/json",
}


async def shopify_get(endpoint: str, params: dict = None):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SHOPIFY_BASE_URL}{endpoint}",
            headers=HEADERS,
            params=params or {},
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()


async def shopify_post(endpoint: str, data: dict):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SHOPIFY_BASE_URL}{endpoint}",
            headers=HEADERS,
            json=data,
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()


async def shopify_put(endpoint: str, data: dict):
    async with httpx.AsyncClient() as client:
        r = await client.put(
            f"{SHOPIFY_BASE_URL}{endpoint}",
            headers=HEADERS,
            json=data,
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()
