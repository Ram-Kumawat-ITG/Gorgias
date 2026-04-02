# Multi-provider LLM client — tries each provider/model in order and falls back
# automatically on rate-limit errors so the app never gets stuck on one quota.
#
# Fallback order:
#   1. Groq  — llama-3.3-70b-versatile  (best quality, hits limit first)
#   2. Groq  — llama-3.1-8b-instant     (separate quota pool, very fast)
#   3. Groq  — mixtral-8x7b-32768       (another independent quota pool)
#   4. Groq  — gemma2-9b-it             (Google model on Groq infra)
#   5. OpenAI — gpt-4o-mini             (cheap, high quality fallback)
#   6. OpenAI — gpt-3.5-turbo           (last resort)

import httpx
from app.config import settings

# (provider, model_id) pairs — tried left-to-right on rate-limit / quota errors
_PROVIDER_CHAIN = [
    ("groq",   "llama-3.3-70b-versatile"),
    ("groq",   "llama-3.1-8b-instant"),
    ("groq",   "mixtral-8x7b-32768"),
    ("groq",   "gemma2-9b-it"),
    ("openai", "gpt-4o-mini"),
    ("openai", "gpt-3.5-turbo"),
]


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True for any rate-limit / quota-exceeded error across providers."""
    name = type(exc).__name__.lower()
    msg  = str(exc).lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True
    if any(k in msg for k in ("rate limit", "rate_limit", "quota", "429",
                               "tokens per", "requests per", "too many")):
        return True
    # httpx / raw HTTP 429
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return True
    return False


async def chat_complete(
    messages: list,
    max_tokens: int = 600,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    """
    Send a chat completion request, automatically falling back through the
    provider chain whenever a rate-limit or quota error is encountered.

    Returns the raw assistant message content as a string.
    Raises RuntimeError if every provider in the chain fails.
    """
    last_error: Exception | None = None

    for provider, model in _PROVIDER_CHAIN:
        # Skip providers whose API key is not configured
        if provider == "groq"   and not settings.groq_api_key:
            continue
        if provider == "openai" and not settings.openai_api_key:
            continue

        try:
            if provider == "groq":
                from groq import AsyncGroq
                client = AsyncGroq(api_key=settings.groq_api_key)
                kwargs: dict = dict(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = await client.chat.completions.create(**kwargs)

            elif provider == "openai":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                kwargs = dict(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = await client.chat.completions.create(**kwargs)

            else:
                continue

            content = response.choices[0].message.content or ""
            print(f"[LLM] Used {provider}/{model}")
            return content.strip()

        except Exception as exc:
            if _is_rate_limit_error(exc):
                print(f"[LLM] Rate limit on {provider}/{model} — trying next provider")
                last_error = exc
                continue
            # Non-rate-limit errors (auth, network, bad request) also try next
            print(f"[LLM] Error on {provider}/{model}: {exc} — trying next provider")
            last_error = exc
            continue

    raise RuntimeError(
        f"[LLM] All providers exhausted. Last error: {last_error}"
    )
