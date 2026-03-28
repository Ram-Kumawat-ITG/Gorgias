# AI service — generates reply suggestions using Google Gemini (free) or OpenAI (fallback)
import httpx
from app.config import settings
from app.database import get_db

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


async def generate_reply_suggestion(ticket_id: str) -> str:
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        return "Ticket not found."

    messages = await db.messages.find(
        {"ticket_id": ticket_id}
    ).sort("created_at", -1).limit(10).to_list(10)
    messages.reverse()

    orders = []
    if ticket.get("customer_email"):
        orders = await db.order_snapshots.find(
            {"email": ticket["customer_email"]}
        ).sort("created_at", -1).limit(3).to_list(3)

    conversation = ""
    for msg in messages:
        role = msg.get("sender_type", "unknown")
        conversation += f"\n[{role}]: {msg.get('body', '')}\n"

    order_context = ""
    for o in orders:
        order_context += (
            f"\nOrder #{o.get('order_number')}: "
            f"status={o.get('financial_status')}, "
            f"fulfillment={o.get('fulfillment_status')}, "
            f"total={o.get('total_price')} {o.get('currency', '')}"
        )
        if o.get("tracking_url"):
            order_context += f", tracking: {o['tracking_url']}"
        order_context += "\n"

    prompt = (
        "You are a friendly, professional customer support agent. "
        "Write a helpful reply to the customer based on the conversation and order context below. "
        "Rules: Keep your reply under 150 words. Never fabricate order details — only reference "
        "information provided in the order context. Be empathetic and solution-oriented.\n\n"
        f"Ticket subject: {ticket.get('subject', '')}\n"
        f"Customer: {ticket.get('customer_email', '')}\n\n"
        f"Conversation history:\n{conversation}\n\n"
        f"Order context:\n{order_context if order_context else 'No orders found.'}\n\n"
        "Write a professional reply to the customer:"
    )

    # Try Grok first (free), then Gemini, then OpenAI
    if settings.grok_api_key:
        result = await _call_grok(prompt)
        if result:
            return result

    if settings.gemini_api_key:
        result = await _call_gemini(prompt)
        if result:
            return result

    if settings.openai_api_key:
        result = await _call_openai(prompt)
        if result:
            return result

    return "AI suggestions unavailable — set GROK_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY in .env"


async def _call_grok(prompt: str) -> str:
    """Call xAI Grok API (free tier: $25/month free credits)."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.grok_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.7,
                },
                timeout=30.0,
            )
            if r.status_code != 200:
                print(f"Grok API error ({r.status_code}): {r.text[:200]}")
                return None
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Grok error: {e}")
        return None


async def _call_gemini(prompt: str) -> str:
    """Call Google Gemini API (free tier: 15 RPM, 1500 RPD)."""
    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 400,
                "temperature": 0.7,
            },
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{GEMINI_URL}?key={settings.gemini_api_key}",
                json=payload,
                timeout=30.0,
            )
            if r.status_code != 200:
                print(f"Gemini API error ({r.status_code}): {r.text[:200]}")
                return None
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return None
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


async def _call_openai(prompt: str) -> str:
    """Call OpenAI API (paid)."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI error: {e}")
        return None
