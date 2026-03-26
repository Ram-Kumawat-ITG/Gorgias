# Shopify HMAC verification middleware — validates webhook authenticity
import hashlib
import hmac
import base64
from fastapi import Request, HTTPException
from app.config import settings


async def verify_shopify_hmac(request: Request) -> bytes:
    body = await request.body()
    shopify_hmac = request.headers.get("X-Shopify-Hmac-Sha256", "")
    if not shopify_hmac:
        raise HTTPException(status_code=401, detail="Missing HMAC header")
    secret = settings.shopify_api_secret.encode("utf-8")
    computed = hmac.new(secret, body, hashlib.sha256).digest()
    computed_b64 = base64.b64encode(computed).decode("utf-8")
    if not hmac.compare_digest(computed_b64, shopify_hmac):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    return body
