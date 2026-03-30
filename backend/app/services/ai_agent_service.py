# AI Agent service — analyzes conversations, detects intent, suggests actions (Groq + Llama)
import json
from groq import AsyncGroq
from app.config import settings


SYSTEM_PROMPT = """You are an advanced AI Customer Support Agent integrated with a Shopify-based helpdesk system.

Your responsibilities:
1. Read and understand the full customer conversation.
2. Write a short, clear summary of what happened and what the customer needs.
3. Detect the customer's primary intent.
4. Always suggest at least one relevant action — the actions array must NEVER be empty.
5. For each action, extract relevant data values from the conversation (order numbers, emails, addresses, amounts, etc.) into extracted_data.
6. Return ONLY valid JSON — no text, markdown, or explanation outside the JSON.

OUTPUT FORMAT (STRICT JSON):
{
  "summary": "short and clear summary (1-2 lines)",
  "intent": "main intent of the customer",
  "actions": [
    {
      "type": "ACTION_TYPE",
      "label": "Button label shown in UI",
      "confidence": 0.0-1.0,
      "description": "what this action will do",
      "extracted_data": {
        "field_name": "value extracted from conversation or null if not found"
      }
    }
  ]
}

SUPPORTED ACTION TYPES AND THEIR extracted_data fields:
- CANCEL_ORDER: { "order_id": "", "order_number": "", "reason": "" }
- CREATE_ORDER: { "customer_email": "", "product_name": "", "quantity": "", "shipping_address": "" }
- UPDATE_ORDER: { "order_id": "", "order_number": "", "field_to_update": "", "new_value": "" }
- DELETE_ORDER: { "order_id": "", "order_number": "" }
- TRACK_ORDER: { "order_id": "", "order_number": "", "customer_email": "" }
- REFUND_ORDER: { "order_id": "", "order_number": "", "refund_amount": "", "reason": "" }
- UPDATE_CUSTOMER_ADDRESS: { "customer_email": "", "new_address": "", "city": "", "zip": "", "country": "" }
- UPDATE_CUSTOMER_DETAILS: { "customer_email": "", "field_to_update": "", "new_value": "" }

RULES:
1. Always generate at least one action — never return an empty actions array.
2. Each action MUST include: type, label, confidence, description, extracted_data.
3. Extract values from the conversation text into extracted_data. Use null for values not mentioned.
4. For destructive actions (CANCEL_ORDER, DELETE_ORDER, REFUND_ORDER), use lower confidence (0.5-0.7) unless customer explicitly requested it.
5. For TRACK_ORDER or UPDATE_CUSTOMER_ADDRESS, confidence can be higher (0.8-0.95) when clearly mentioned.
6. Do NOT hallucinate data — only extract what is actually in the conversation.
7. Output ONLY valid JSON, no explanation outside JSON."""


async def analyze_conversation(messages: list, subject: str = "", customer_email: str = "", shopify_order_id: str = None) -> dict:
    if not settings.groq_api_key:
        return {
            "summary": "AI analysis unavailable — Groq API key not configured.",
            "intent": "unknown",
            "actions": [],
        }

    conversation = ""
    for msg in messages:
        sender = msg.get("sender", msg.get("sender_type", "unknown"))
        body = msg.get("message", msg.get("body", ""))
        conversation += f"[{sender}]: {body}\n"

    known_data = f"Customer email: {customer_email}"
    if shopify_order_id:
        known_data += f"\nShopify Order ID (from database): {shopify_order_id}"

    user_prompt = f"""Analyze this customer support conversation:

Subject: {subject}
{known_data}

Conversation:
{conversation}

IMPORTANT: Use the Shopify Order ID provided above (if any) to pre-fill order_id in extracted_data — do not leave it null if the order ID is already known.

Return ONLY valid JSON."""


    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=600,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "summary": "AI returned an invalid response.",
            "intent": "unknown",
            "actions": [],
        }
    except Exception as e:
        return {
            "summary": f"AI analysis failed: {str(e)}",
            "intent": "unknown",
            "actions": [],
        }
