# Email AI Agent — autonomous auto-reply for inbound emails.
# Detects order queries, handles cancel flow, and sends conversational replies.
import json
from datetime import datetime, timezone
from groq import AsyncGroq
from app.config import settings
from app.database import get_db
from app.services.order_service import (
    lookup_order_by_number,
    lookup_order_by_email,
    lookup_order_by_id,
    cancel_order,
    format_order_details_text,
    get_order_status_with_ticket_context,
)

EMAIL_AGENT_SYSTEM_PROMPT = """You are a friendly and professional customer support agent replying via email.

You represent our online store's support team. Be warm, empathetic, and solution-oriented.
Keep replies concise but thorough — this is email, not chat, so slightly more detail is fine.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR PERSONALITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Professional yet friendly — like a helpful colleague
- Empathetic and solution-oriented
- Never robotic or overly formal
- If you don't know something, say so honestly
- Never claim to be AI — you're the support team

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT-AWARE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- The customer's email is already known (they emailed us)
- If an order number was mentioned → remember it for follow-up
- After showing order details → customer can request cancel without re-entering info

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUPPORTED ACTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- fetch_order: Look up order status, items, tracking
- cancel_order: Cancel an existing order (always confirm first)
- check_inventory: Check if a product is in stock
- ask_order_number: Need the order number — ask politely
- ask_confirmation: Confirm before a destructive action
- none: General reply, no Shopify action needed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CANCEL ORDERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When a customer wants to cancel an order:
  - Do NOT ask "should I cancel?" or confirm with the customer yourself
  - Set action = "cancel_order" immediately
  - The system will handle the retention offer and confirmation automatically

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Keep replies under 200 words
- Use proper sentences (this is email, not WhatsApp)
- No markdown formatting (plain text email)
- Be helpful and sign off naturally
- If something fails: "I'm having trouble accessing that information right now. Let me look into this and get back to you shortly."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — STRICT JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY this JSON — no text outside it:

{
  "action": "fetch_order | cancel_order | check_inventory | ask_order_number | ask_confirmation | none",
  "order_id": "shopify internal order id if known, else null",
  "order_number": "order number like 1042 (digits only), else null",
  "message": "The email reply to send to the customer"
}

RULES:
- "message" is ALWAYS the exact text sent to the customer
- Never leave "message" empty
- Output ONLY valid JSON, nothing else"""


async def _get_conversation_history(ticket_id: str) -> list:
    """Fetch recent messages for a ticket."""
    db = get_db()
    cursor = db.messages.find(
        {"ticket_id": ticket_id, "is_internal_note": {"$ne": True}},
        sort=[("created_at", 1)],
    ).limit(10)
    return [doc async for doc in cursor]


async def _check_inventory(product_name: str) -> str:
    """Check stock for a product."""
    from app.services.shopify_client import shopify_get, ShopifyAPIError
    try:
        result = await shopify_get("/products.json", params={"title": product_name, "limit": 5})
        products = result.get("products", [])
        if not products:
            return f"out_of_stock|0|{product_name}"
        product = products[0]
        title = product.get("title", product_name)
        variants = product.get("variants", [])
        total_stock = sum(
            int(v.get("inventory_quantity") or 0)
            for v in variants
            if v.get("inventory_management") == "shopify"
        )
        if total_stock == 0:
            return f"out_of_stock|0|{title}"
        return f"in_stock|{total_stock}|{title}"
    except ShopifyAPIError:
        return f"error|0|{product_name}"


async def _execute_action(agent_result: dict, customer_email: str) -> str:
    """Execute the action from the AI result and return reply text."""
    action = agent_result.get("action", "none")
    order_id = (agent_result.get("order_id") or "").strip()
    order_number = (agent_result.get("order_number") or "").strip().lstrip("#")
    default_msg = agent_result.get("message", "Thank you for reaching out. Let me look into this for you.")

    # Reroute cancel-related confirmations to the retention flow
    if action == "ask_confirmation":
        if "cancel" in default_msg.lower():
            agent_result["action"] = "cancel_order"
            action = "cancel_order"
        else:
            return default_msg

    if action in ("ask_order_number", "none"):
        return default_msg

    if action == "check_inventory":
        query = agent_result.get("inventory_query") or ""
        if not query:
            return default_msg
        status_raw = await _check_inventory(query)
        status, qty, title = status_raw.split("|", 2)
        if status == "in_stock":
            return f"Great news! {title} is currently in stock ({qty} available). Would you like to place an order?"
        if status == "out_of_stock":
            return f"Unfortunately, {title} is currently out of stock. Would you like me to suggest alternatives or notify you when it's back?"
        return f"I wasn't able to check stock for {query} right now. Let me look into this and get back to you."

    if action == "fetch_order":
        order = None
        err = ""

        if order_number:
            order, err = await lookup_order_by_number(order_number, customer_email)
        if not order and order_id:
            order = await lookup_order_by_id(order_id)
            if not order:
                err = "I couldn't find that order. Could you share the order number?"
        if not order and customer_email:
            orders = await lookup_order_by_email(customer_email, limit=1)
            if orders:
                order = orders[0]
            else:
                err = f"I couldn't find any orders for {customer_email}."

        if not order:
            return err or default_msg

        details = format_order_details_text(order)
        return f"Here are your order details:\n\n{details}\n\nIf you'd like to cancel this order, just let me know."

    if action == "cancel_order":
        # Retention flow — intercept cancel request
        from app.services.retention_service import (
            check_retention_attempted, check_awaiting_cancel_confirm,
            create_or_update_cancel_ticket, create_retention_gift_card,
            get_retention_offer_message, mark_retention_offered,
            detect_retention_response, process_retention_response,
            process_cancel_confirmation,
        )

        if not order_id and order_number:
            order, err = await lookup_order_by_number(order_number, customer_email)
            if order:
                order_id = str(order.get("id", ""))
            else:
                return err or default_msg
        if not order_id and customer_email:
            orders = await lookup_order_by_email(customer_email, limit=1)
            if orders:
                order_id = str(orders[0]["id"])
            else:
                return f"I couldn't find any open orders for {customer_email}."
        if not order_id:
            return default_msg

        ticket_id_ctx = agent_result.get("_ticket_id", "")
        if ticket_id_ctx:
            # State 3: Awaiting final "are you sure?" confirmation
            awaiting_confirm = await check_awaiting_cancel_confirm(ticket_id_ctx)
            if awaiting_confirm:
                response = detect_retention_response(default_msg)
                confirmed = response == "yes_cancel"
                return await process_cancel_confirmation(ticket_id_ctx, confirmed, "email")

            # State 1: First cancel — create gift card + send retention offer
            already_offered = await check_retention_attempted(ticket_id_ctx)
            if not already_offered:
                await create_or_update_cancel_ticket(customer_email, order_id, "email", ticket_id_ctx)
                gc = await create_retention_gift_card(customer_email, "email", ticket_id_ctx)
                await mark_retention_offered(ticket_id_ctx)
                if gc and gc.get("code"):
                    return get_retention_offer_message("email", gc["code"], gc["balance"], gc.get("currency", "INR"))
                return get_retention_offer_message("email", "N/A", str(500), "INR")

            # State 2: Retention offered — check OK/CANCEL response
            response = detect_retention_response(default_msg)
            if response in ("yes_cancel", "no_keep"):
                return await process_retention_response(ticket_id_ctx, response, "email")

        # Fallback
        if ticket_id_ctx:
            return await process_retention_response(ticket_id_ctx, "yes_cancel", "email")
        return default_msg

    return default_msg


async def process_email_message(
    ticket_id: str,
    customer_email: str,
    current_message: str,
) -> str | None:
    """Run the AI agent on an inbound email message.
    Returns the reply text or None if AI is unavailable."""
    if not settings.groq_api_key:
        print("Email AI Agent: GROQ_API_KEY is not set — auto-reply disabled")
        return None

    history = await _get_conversation_history(ticket_id)

    chat_messages = [{"role": "system", "content": EMAIL_AGENT_SYSTEM_PROMPT}]

    # Add context about customer email
    chat_messages.append({
        "role": "system",
        "content": f"Customer email: {customer_email}",
    })

    for msg in history:
        role = "user" if msg.get("sender_type") == "customer" else "assistant"
        body = (msg.get("body") or "").strip()
        if body:
            chat_messages.append({"role": role, "content": body})

    # Ensure conversation ends on a user turn
    if not chat_messages or chat_messages[-1].get("role") != "user":
        chat_messages.append({"role": "user", "content": current_message})

    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=chat_messages,
            max_tokens=600,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rstrip("`").strip()

        result = json.loads(raw)
        result["_ticket_id"] = ticket_id  # inject for retention flow
        reply = await _execute_action(result, customer_email)

        # Persist the AI reply as a message in the ticket
        from app.models.message import MessageInDB
        db = get_db()
        ai_msg = MessageInDB(
            ticket_id=ticket_id,
            body=reply,
            sender_type="ai",
            channel="email",
            ai_generated=True,
        )
        await db.messages.insert_one(ai_msg.model_dump())

        # Stamp first_response_at if this is the first agent/AI reply
        now = datetime.now(timezone.utc)
        ticket_doc = await db.tickets.find_one({"id": ticket_id})
        if ticket_doc and not ticket_doc.get("first_response_at"):
            await db.tickets.update_one(
                {"id": ticket_id},
                {"$set": {
                    "first_response_at": now,
                    "first_response_sla_status": "met",
                    "updated_at": now,
                }},
            )

        return reply

    except json.JSONDecodeError:
        if raw and len(raw) < 1000:
            return raw
        return None
    except Exception as e:
        print(f"Email AI Agent error: {e}")
        return None
