# Script to register Shopify webhooks — run once after deploy
# Usage: cd backend && python -m scripts.register_webhooks
import asyncio
from app.services.shopify_client import shopify_post
from app.config import settings

WEBHOOKS = [
    {"topic": "orders/create", "path": "/webhooks/orders/create"},
    {"topic": "orders/fulfilled", "path": "/webhooks/orders/fulfilled"},
    {"topic": "customers/update", "path": "/webhooks/customers/update"},
]

BASE_URL = "https://your-backend-url.com"  # Update with your deployed backend URL


async def main():
    for wh in WEBHOOKS:
        try:
            result = await shopify_post("/webhooks.json", {
                "webhook": {
                    "topic": wh["topic"],
                    "address": f"{BASE_URL}{wh['path']}",
                    "format": "json",
                }
            })
            print(f"Registered: {wh['topic']} -> {result}")
        except Exception as e:
            print(f"Failed to register {wh['topic']}: {e}")


asyncio.run(main())
