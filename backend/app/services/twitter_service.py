import base64
import hashlib
import hmac
import time
import urllib.parse
import uuid

import httpx
from app.config import settings
from app.database import get_db

TWITTER_API_BASE = "https://api.twitter.com"


async def get_twitter_config(merchant_id: str = None) -> dict:
    """Get Twitter config — merchant-specific first, then fall back to global .env."""
    if merchant_id:
        db = get_db()
        merchant = await db.merchants.find_one({"id": merchant_id, "is_active": True})
        if merchant and merchant.get("twitter_api_key"):
            return {
                "api_key": merchant["twitter_api_key"],
                "api_secret": merchant["twitter_api_secret"],
                "access_token": merchant["twitter_access_token"],
                "access_token_secret": merchant["twitter_access_token_secret"],
                "bearer_token": merchant.get("twitter_bearer_token", ""),
                "env_name": merchant.get("twitter_env_name", "production"),
            }
    return {
        "api_key": settings.twitter_api_key,
        "api_secret": settings.twitter_api_secret,
        "access_token": settings.twitter_access_token,
        "access_token_secret": settings.twitter_access_token_secret,
        "bearer_token": settings.twitter_bearer_token,
        "env_name": settings.twitter_env_name or "production",
    }


def verify_crc(crc_token: str, consumer_secret: str) -> str:
    """Generate the response_token for Twitter's CRC (Challenge-Response Check)."""
    mac = hmac.new(
        consumer_secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    )
    return "sha256=" + base64.b64encode(mac.digest()).decode("utf-8")


def _pct(value: str) -> str:
    """Percent-encode a string per RFC 3986 (for OAuth 1.0a)."""
    return urllib.parse.quote(str(value), safe="")


def _build_oauth1_header(method: str, url: str, extra_params: dict, config: dict) -> str:
    """Build OAuth 1.0a Authorization header using HMAC-SHA1 (Twitter spec)."""
    oauth_params = {
        "oauth_consumer_key": config["api_key"],
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": config["access_token"],
        "oauth_version": "1.0",
    }

    all_params = {**extra_params, **oauth_params}
    sorted_param_str = "&".join(
        f"{_pct(k)}={_pct(v)}"
        for k, v in sorted(all_params.items())
    )

    base_string = "&".join([
        method.upper(),
        _pct(url),
        _pct(sorted_param_str),
    ])

    signing_key = f"{_pct(config['api_secret'])}&{_pct(config['access_token_secret'])}"

    import hashlib as _hl
    signature = base64.b64encode(
        hmac.new(
            signing_key.encode("utf-8"),
            base_string.encode("utf-8"),
            _hl.sha1,
        ).digest()
    ).decode("utf-8")

    oauth_params["oauth_signature"] = signature

    auth_parts = ", ".join(
        f'{_pct(k)}="{_pct(v)}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {auth_parts}"


async def send_dm(recipient_id: str, text: str, config: dict) -> dict:
    """Send a Direct Message to a Twitter user via API v2 (OAuth 1.0a user context)."""
    if not config.get("api_key") or not config.get("access_token"):
        print("Twitter not configured — skipping DM send")
        return {"error": "not_configured"}

    url = f"{TWITTER_API_BASE}/2/dm_conversations/with/{recipient_id}/messages"
    payload = {"text": text}

    auth_header = _build_oauth1_header("POST", url, {}, config)

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
            print(f"Twitter DM sent to {recipient_id}: {data}")
            return data
    except Exception as e:
        print(f"Twitter DM send failed: {e}")
        return {"error": str(e)}


async def reply_to_tweet(tweet_id: str, text: str, config: dict) -> dict:
    """Reply to a tweet via Twitter API v2 (OAuth 1.0a user context)."""
    if not config.get("api_key") or not config.get("access_token"):
        print("Twitter not configured — skipping tweet reply")
        return {"error": "not_configured"}

    url = f"{TWITTER_API_BASE}/2/tweets"
    payload = {
        "text": text[:280],
        "reply": {"in_reply_to_tweet_id": tweet_id},
    }

    auth_header = _build_oauth1_header("POST", url, {}, config)

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
            print(f"Twitter reply sent to tweet {tweet_id}: {data}")
            return data
    except Exception as e:
        print(f"Twitter reply failed: {e}")
        return {"error": str(e)}


async def register_webhook(webhook_url: str, merchant_id: str = None) -> dict:
    """Register webhook URL with Twitter Account Activity API v1.1."""
    config = await get_twitter_config(merchant_id)
    config["merchant_id"] = merchant_id  # Pass to DB update

    if not all([config.get(k) for k in ["api_key", "api_secret", "access_token", "access_token_secret"]]):
        return {"error": "Twitter User Context credentials (4 keys) required for webhook registration"}

    env_name = config.get("env_name", "production")
    url = f"{TWITTER_API_BASE}/1.1/account_activity/all/{env_name}/webhooks.json"
    params = {"url": webhook_url}

    auth_header = _build_oauth1_header("POST", url, params, config)

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url,
                params=params,
                headers={"Authorization": auth_header},
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()

            webhook_id = data[0].get("id") if isinstance(data, list) and data else None
            if webhook_id and merchant_id:
                db = get_db()
                await db.merchants.update_one(
                    {"id": merchant_id},
                    {"$set": {"twitter_webhook_id": webhook_id}}
                )

            return {
                "status": "success",
                "webhook_id": webhook_id,
                "url": webhook_url,
                "env_name": env_name,
                "next_steps": "1. Verify in Twitter Developer Portal 2. Subscribe to DM events"
            }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": str(e)}

