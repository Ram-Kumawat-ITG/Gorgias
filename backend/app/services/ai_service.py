# AI service — generates GPT-4 reply suggestions using ticket + order context
from openai import AsyncOpenAI
from app.config import settings
from app.database import get_db


async def generate_reply_suggestion(ticket_id: str) -> str:
    if not settings.openai_api_key:
        return "AI suggestions are unavailable — OpenAI API key not configured."

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

    system_prompt = (
        "You are a friendly, professional customer support agent. "
        "Write a helpful reply to the customer based on the conversation and order context below. "
        "Rules: Keep your reply under 150 words. Never fabricate order details — only reference "
        "information provided in the order context. Be empathetic and solution-oriented."
    )

    user_prompt = f"""Ticket subject: {ticket.get('subject', '')}
Customer: {ticket.get('customer_email', '')}

Conversation history:
{conversation}

Order context:
{order_context if order_context else 'No orders found.'}

Write a professional reply to the customer:"""

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=400,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI suggestion unavailable: {str(e)}"
