# Instagram AI Sales Agent — auto-replies to Instagram DMs with intent detection,
# product recommendations, and Shopify order management.
# Email is REQUIRED before any Shopify operation.

import json
import re
from datetime import datetime
from groq import AsyncGroq
from app.config import settings
from app.database import get_db
from app.services.shopify_client import shopify_get, shopify_post, shopify_put, ShopifyAPIError


# ───────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT
# ───────────────────────────────────────────────────────────────────────────────

INSTAGRAM_AGENT_SYSTEM_PROMPT = """You are an AI-powered E-commerce Support & Sales Agent on Instagram.

You are integrated with Instagram Messaging API and Shopify Admin API.

## CRITICAL RULE: EMAIL IS MANDATORY
- Email is REQUIRED for ANY Shopify operation: create order, cancel order, update order, fetch order, customer lookup.
- If email is NOT provided, set requires_email=true and ask for it politely.
- Always validate email format: must contain @ and a domain.

## INSTAGRAM TONE
- Messages must be short, friendly, and slightly casual (Instagram DM style).
- Use light emojis where appropriate (not excessive).
- If user came from a comment: start with "Hey! Saw your comment on our post 👀 How can I help?"

## INTENT DETECTION
Detect the customer's primary intent:
- product_inquiry: asking about products, prices, availability
- purchase_intent: wants to buy something
- create_order: confirmed purchase with product + email
- cancel_order: wants to cancel an existing order
- order_status: wants to track/check order status
- support: general support question
- ask_email: email not yet provided, must ask for it

## CUSTOMER IDENTIFICATION
- Before ANY Shopify action, email is required.
- If email not in conversation history, set requires_email=true.
- If email found, set email field and proceed.

## SHOPIFY ACTIONS
Set actions array to instruct the backend on what Shopify operations to perform.
Only set actions when email is confirmed AND user has clearly requested the action.

Supported action types:
- search_products: search for products (payload: {"query": "product name"})
- get_customer: find customer by email (payload: {"email": "..."})
- get_orders: get customer orders (payload: {"email": "..."})
- create_order: create a new order (payload: {"email": "...", "product_name": "...", "variant_id": "...", "quantity": 1})
- cancel_order: cancel an order (payload: {"email": "...", "order_id": "...", "order_number": "..."})
- get_order_status: get order tracking/status (payload: {"email": "...", "order_id": "...", "order_number": "..."})

## PRODUCT RECOMMENDATIONS
When user asks about products:
- Set action type "search_products" with the query.
- The backend will fetch real products and inject them.
- Mention you're checking availability.

## RESPONSE FORMAT (STRICT JSON)
{
  "summary": "1-2 line summary of what the customer needs",
  "intent": "product_inquiry | purchase_intent | create_order | cancel_order | order_status | support | ask_email",
  "message": "Instagram-style conversational reply to send to the customer",
  "actions": [
    {
      "type": "search_products | get_customer | get_orders | create_order | cancel_order | get_order_status",
      "payload": {}
    }
  ],
  "requires_email": true or false,
  "email": "extracted email address or empty string",
  "confidence": 0.0 to 1.0
}

## CANCEL ORDERS
- When a customer wants to cancel, set action type "cancel_order" immediately.
- Do NOT ask "should I cancel?" or confirm with the customer yourself.
- The system handles the retention offer and confirmation automatically.

## RULES
- Output ONLY valid JSON. No text outside the JSON.
- message field must be the exact Instagram reply to send.
- If email is missing and Shopify action is needed, set intent="ask_email", requires_email=true, actions=[].
- Never invent order IDs or product details — only use what the customer provided.
- Keep messages under 200 characters when possible (Instagram DM style).
- actions array CAN be empty if no Shopify operation is needed yet."""


# ───────────────────────────────────────────────────────────────────────────────
#  EMAIL EXTRACTION & VALIDATION
# ───────────────────────────────────────────────────────────────────────────────

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extract_email(text: str) -> str | None:
    """Extract the first valid email address from a block of text."""
    match = EMAIL_REGEX.search(text)
    return match.group(0).lower() if match else None


def is_placeholder_email(email: str) -> bool:
    """Return True if the email is an auto-generated placeholder (not a real user email)."""
    return email.endswith("@instagram.placeholder") or email.endswith("@whatsapp.placeholder")


# ───────────────────────────────────────────────────────────────────────────────
#  SHOPIFY HELPERS (used by the agent executor)
# ───────────────────────────────────────────────────────────────────────────────

async def _shopify_search_products(query: str, limit: int = 5) -> list:
    """Search Shopify products by title keyword."""
    try:
        params = {"limit": limit}
        if query:
            params["title"] = query
        data = await shopify_get("/products.json", params)
        results = []
        for p in data.get("products", []):
            images = p.get("images") or []
            img = images[0].get("src") if images else None
            for v in p.get("variants", []):
                if not v.get("available", True) and v.get("inventory_quantity", 1) <= 0:
                    continue
                results.append({
                    "name": p["title"] + (f" – {v['title']}" if v.get("title") != "Default Title" else ""),
                    "price": v.get("price", "0.00"),
                    "image": img,
                    "variant_id": str(v["id"]),
                    "available": True,
                })
        return results[:limit]
    except ShopifyAPIError:
        return []


async def _shopify_get_or_create_customer(email: str) -> dict | None:
    """Find or create a Shopify customer by email. Returns customer dict or None."""
    try:
        data = await shopify_get("/customers/search.json", {"query": f"email:{email}", "limit": 1})
        customers = data.get("customers", [])
        if customers:
            return customers[0]
        # Create new customer
        result = await shopify_post("/customers.json", {
            "customer": {"email": email, "verified_email": True}
        })
        return result.get("customer")
    except ShopifyAPIError:
        return None


async def _shopify_get_orders(email: str) -> list:
    """Fetch the most recent Shopify orders for a customer email."""
    try:
        data = await shopify_get("/customers/search.json", {"query": f"email:{email}", "limit": 1})
        customers = data.get("customers", [])
        if not customers:
            return []
        customer_id = customers[0]["id"]
        orders_data = await shopify_get(f"/customers/{customer_id}/orders.json", {"status": "any", "limit": 5})
        orders = []
        for o in orders_data.get("orders", []):
            ff = o.get("fulfillments") or []
            tracking = ff[0].get("tracking_number") if ff else None
            orders.append({
                "id": str(o["id"]),
                "name": o.get("name", ""),
                "order_number": o.get("order_number"),
                "financial_status": o.get("financial_status"),
                "fulfillment_status": o.get("fulfillment_status"),
                "total_price": o.get("total_price"),
                "currency": o.get("currency"),
                "tracking_number": tracking,
                "created_at": o.get("created_at"),
                "cancelled_at": o.get("cancelled_at"),
            })
        return orders
    except ShopifyAPIError:
        return []


async def _shopify_cancel_order(order_id: str) -> dict:
    """Cancel a Shopify order by ID."""
    try:
        result = await shopify_post(f"/orders/{order_id}/cancel.json", {
            "reason": "customer", "restock": True, "email": False
        })
        return {"success": True, "order": result.get("order", {})}
    except ShopifyAPIError as e:
        return {"success": False, "error": e.message}


async def _shopify_create_order(email: str, variant_id: str, quantity: int = 1) -> dict:
    """Create a Shopify order via draft order flow."""
    try:
        customer = await _shopify_get_or_create_customer(email)
        if not customer:
            return {"success": False, "error": "Could not find or create customer"}

        customer_id = customer["id"]
        draft_payload = {
            "draft_order": {
                "customer": {"id": customer_id},
                "line_items": [{"variant_id": int(variant_id), "quantity": quantity}],
                "use_customer_default_address": True,
            }
        }
        draft_result = await shopify_post("/draft_orders.json", draft_payload)
        draft = draft_result.get("draft_order", {})
        complete = await shopify_put(
            f"/draft_orders/{draft['id']}/complete.json",
            {"payment_pending": True},
        )
        order_id = complete.get("draft_order", {}).get("order_id")
        if order_id:
            order_data = await shopify_get(f"/orders/{order_id}.json")
            o = order_data.get("order", {})
            return {
                "success": True,
                "order_name": o.get("name", ""),
                "order_number": o.get("order_number"),
                "total_price": o.get("total_price"),
                "currency": o.get("currency"),
            }
        return {"success": True, "draft_id": str(draft.get("id", ""))}
    except ShopifyAPIError as e:
        return {"success": False, "error": e.message}


# ───────────────────────────────────────────────────────────────────────────────
#  ACTION EXECUTOR
# ───────────────────────────────────────────────────────────────────────────────

async def _execute_actions(actions: list, email: str) -> dict:
    """Execute Shopify actions returned by the LLM and return structured context."""
    context = {}
    for action in actions:
        action_type = action.get("type", "")
        payload = action.get("payload", {})

        if action_type == "search_products":
            query = payload.get("query", "")
            products = await _shopify_search_products(query)
            context["products"] = products

        elif action_type in ("get_customer", "get_orders"):
            action_email = payload.get("email", "") or email
            if action_email:
                orders = await _shopify_get_orders(action_email)
                context["orders"] = orders

        elif action_type == "get_order_status":
            action_email = payload.get("email", "") or email
            order_id = payload.get("order_id", "")
            if action_email:
                orders = await _shopify_get_orders(action_email)
                if order_id:
                    orders = [o for o in orders if o["id"] == str(order_id) or str(o.get("order_number", "")) == str(order_id)]
                context["orders"] = orders

        elif action_type == "cancel_order":
            order_id = payload.get("order_id", "")
            action_email = payload.get("email", "") or email
            # Use retention flow instead of direct cancel
            context["cancel_result"] = {
                "success": False,
                "retention": True,
                "order_id": order_id,
                "email": action_email,
            }

        elif action_type == "create_order":
            action_email = payload.get("email", "") or email
            variant_id = payload.get("variant_id", "")
            quantity = int(payload.get("quantity", 1))
            if action_email and variant_id:
                result = await _shopify_create_order(action_email, variant_id, quantity)
                context["create_result"] = result
            else:
                context["create_result"] = {"success": False, "error": "Missing email or variant_id"}

    return context


# ───────────────────────────────────────────────────────────────────────────────
#  CONTEXT BUILDER — formats Shopify data into a human-readable string
# ───────────────────────────────────────────────────────────────────────────────

def _build_shopify_context_text(context: dict) -> str:
    """Convert executed Shopify action results into a text block for the LLM follow-up."""
    parts = []

    products = context.get("products", [])
    if products:
        parts.append("Available products from Shopify:")
        for p in products:
            parts.append(f"  - {p['name']} | Price: {p['price']} | variant_id: {p['variant_id']}")

    orders = context.get("orders", [])
    if orders:
        parts.append("Customer orders:")
        for o in orders:
            status = o.get("fulfillment_status") or "unfulfilled"
            tracking = f" | Tracking: {o['tracking_number']}" if o.get("tracking_number") else ""
            cancelled = " [CANCELLED]" if o.get("cancelled_at") else ""
            parts.append(
                f"  - Order {o['name']} (#{o['order_number']}) | "
                f"Payment: {o['financial_status']} | Fulfillment: {status}{tracking}{cancelled}"
            )
    elif "orders" in context:
        parts.append("No orders found for this customer.")

    cancel = context.get("cancel_result", {})
    if cancel:
        if cancel.get("success"):
            parts.append("Order cancellation: SUCCESS")
        else:
            parts.append(f"Order cancellation: FAILED — {cancel.get('error', 'unknown error')}")

    create = context.get("create_result", {})
    if create:
        if create.get("success"):
            parts.append(
                f"Order created: {create.get('order_name', '')} | "
                f"Total: {create.get('total_price', '')} {create.get('currency', '')}"
            )
        else:
            parts.append(f"Order creation failed: {create.get('error', 'unknown error')}")

    return "\n".join(parts) if parts else ""


# ───────────────────────────────────────────────────────────────────────────────
#  GROQ LLM CALLER
# ───────────────────────────────────────────────────────────────────────────────

async def _call_groq(conversation_text: str, extra_context: str = "") -> dict:
    """Call Groq LLM with the Instagram agent system prompt. Returns parsed JSON dict."""
    if not settings.groq_api_key:
        return {
            "summary": "AI unavailable",
            "intent": "support",
            "message": "Hey! Give me a moment — I'm having a tech issue. Please try again shortly 🙏",
            "actions": [],
            "requires_email": False,
            "email": "",
            "confidence": 0.5,
        }

    user_content = f"Instagram conversation:\n{conversation_text}"
    if extra_context:
        user_content += f"\n\nShopify data retrieved:\n{extra_context}"
        user_content += "\n\nUsing the Shopify data above, write the final Instagram reply."

    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": INSTAGRAM_AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=600,
            temperature=0.4,
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
            "summary": "LLM returned invalid JSON",
            "intent": "support",
            "message": "Hey! I had a small glitch — could you repeat that? 😊",
            "actions": [],
            "requires_email": False,
            "email": "",
            "confidence": 0.3,
        }
    except Exception as e:
        return {
            "summary": f"LLM error: {str(e)}",
            "intent": "support",
            "message": "Sorry, I'm experiencing a technical issue right now. Please try again in a moment 🙏",
            "actions": [],
            "requires_email": False,
            "email": "",
            "confidence": 0.0,
        }


# ───────────────────────────────────────────────────────────────────────────────
#  MAIN AGENT ENTRY POINT
# ───────────────────────────────────────────────────────────────────────────────

async def process_instagram_message(
    igsid: str,
    ticket_id: str,
    message_body: str,
) -> str:
    """
    Main agent function. Given an Instagram sender ID, ticket ID, and latest
    message body, it:
      1. Loads conversation history from the database
      2. Extracts/validates any email address present in the conversation
      3. Calls Groq LLM to detect intent and determine actions
      4. Executes Shopify actions (product search, order management, etc.)
      5. Optionally calls Groq again with Shopify results for a richer reply
      6. Persists the agent reply as a message in the ticket
      7. Updates the ticket's customer_email if a real email was collected
      8. Returns the reply text to be sent via Instagram DM

    Returns the reply text string to send to the customer.
    """
    db = get_db()

    # ── 1. Load conversation history ──────────────────────────────────────────
    raw_messages = await db.messages.find(
        {"ticket_id": ticket_id}
    ).sort("created_at", 1).limit(20).to_list(length=20)

    # ── 2. Get current ticket to check for previously stored real email ───────
    ticket = await db.tickets.find_one({"id": ticket_id})
    current_email = ""
    if ticket:
        stored_email = ticket.get("customer_email", "")
        if not is_placeholder_email(stored_email):
            current_email = stored_email

    # ── 3. Build conversation text for LLM ───────────────────────────────────
    conversation_lines = []
    for m in raw_messages:
        role = "Customer" if m.get("sender_type") == "customer" else "Agent"
        conversation_lines.append(f"[{role}]: {m.get('body', '')}")

    if current_email:
        conversation_lines.insert(0, f"[System]: Customer email on file: {current_email}")

    conversation_text = "\n".join(conversation_lines)

    # ── 4. First LLM call — intent detection + action planning ───────────────
    llm_result = await _call_groq(conversation_text)

    # ── 5. Extract email from LLM response or directly from the message ──────
    detected_email = (llm_result.get("email") or "").strip().lower()
    if not detected_email:
        # Try extracting from the raw message body as fallback
        detected_email = extract_email(message_body) or ""

    # Prefer previously stored real email over newly detected one if both exist
    resolved_email = current_email or detected_email

    # ── 6. Execute Shopify actions if email is available ─────────────────────
    shopify_context = {}
    actions = llm_result.get("actions", [])
    requires_email = llm_result.get("requires_email", False)

    if actions and resolved_email and not requires_email:
        shopify_context = await _execute_actions(actions, resolved_email)

    # ── 6b. Handle retention flow for cancel requests ────────────────────────
    cancel_result = shopify_context.get("cancel_result", {})
    if cancel_result.get("retention"):
        try:
            from app.services.retention_service import (
                check_retention_attempted, check_awaiting_cancel_confirm,
                create_or_update_cancel_ticket, create_retention_gift_card,
                get_retention_offer_message, mark_retention_offered,
                detect_retention_response, process_retention_response,
                process_cancel_confirmation,
            )
            from app.models.message import MessageInDB
            order_id = cancel_result.get("order_id", "")

            # State 3: Awaiting final "are you sure?" confirmation
            awaiting_confirm = await check_awaiting_cancel_confirm(ticket_id)
            if awaiting_confirm:
                response = detect_retention_response(message_body)
                confirmed = response == "yes_cancel"
                reply = await process_cancel_confirmation(ticket_id, confirmed, "instagram")
                agent_msg = MessageInDB(
                    ticket_id=ticket_id, body=reply, sender_type="ai",
                    channel="instagram", instagram_sender_igsid=igsid, ai_generated=True,
                )
                await db.messages.insert_one(agent_msg.model_dump())
                return reply

            # State 1: First cancel — create gift card + send retention offer
            already_offered = await check_retention_attempted(ticket_id)
            if not already_offered:
                await create_or_update_cancel_ticket(resolved_email, order_id, "instagram", ticket_id)
                gc = await create_retention_gift_card(resolved_email, "instagram", ticket_id)
                await mark_retention_offered(ticket_id)
                if gc and gc.get("code"):
                    retention_msg = get_retention_offer_message("instagram", gc["code"], gc["balance"], gc.get("currency", "INR"))
                else:
                    retention_msg = get_retention_offer_message("instagram", "N/A", str(500), "INR")
                agent_msg = MessageInDB(
                    ticket_id=ticket_id, body=retention_msg, sender_type="ai",
                    channel="instagram", instagram_sender_igsid=igsid, ai_generated=True,
                )
                await db.messages.insert_one(agent_msg.model_dump())
                if resolved_email and resolved_email != current_email:
                    await db.tickets.update_one({"id": ticket_id}, {"$set": {"customer_email": resolved_email}})
                return retention_msg

            # State 2: Retention offered — check OK/CANCEL response
            response = detect_retention_response(message_body)
            if response in ("yes_cancel", "no_keep"):
                reply = await process_retention_response(ticket_id, response, "instagram")
                agent_msg = MessageInDB(
                    ticket_id=ticket_id, body=reply, sender_type="ai",
                    channel="instagram", instagram_sender_igsid=igsid, ai_generated=True,
                )
                await db.messages.insert_one(agent_msg.model_dump())
                return reply
        except Exception as e:
            print(f"Instagram retention error: {e}")

    # ── 7. If Shopify data was fetched, call LLM again for final reply ────────
    reply_text = llm_result.get("message", "")

    if shopify_context:
        context_text = _build_shopify_context_text(shopify_context)
        if context_text:
            refined = await _call_groq(conversation_text, extra_context=context_text)
            reply_text = refined.get("message", reply_text)

    if not reply_text:
        reply_text = "Hey! I'm here to help 😊 What can I do for you?"

    # ── 8. Persist the AI reply as a message in the ticket ───────────────────
    from app.models.message import MessageInDB
    agent_msg = MessageInDB(
        ticket_id=ticket_id,
        body=reply_text,
        sender_type="ai",
        channel="instagram",
        instagram_sender_igsid=igsid,
        ai_generated=True,
    )
    await db.messages.insert_one(agent_msg.model_dump())

    # ── 9. Update ticket with real customer email if newly discovered ─────────
    if resolved_email and resolved_email != current_email:
        update_fields: dict = {"customer_email": resolved_email}
        # Try to sync Shopify customer in background (best-effort)
        try:
            shopify_customer = await _shopify_get_or_create_customer(resolved_email)
            if shopify_customer:
                update_fields["shopify_customer_id"] = str(shopify_customer["id"])
                name = (
                    f"{shopify_customer.get('first_name', '')} "
                    f"{shopify_customer.get('last_name', '')}".strip()
                )
                if name:
                    update_fields["customer_name"] = name
        except Exception:
            pass

        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": update_fields},
        )
        # Update our local customer record as well
        await db.customers.update_one(
            {"email": f"{igsid}@instagram.placeholder"},
            {"$set": {"email": resolved_email}},
        )

    return reply_text
