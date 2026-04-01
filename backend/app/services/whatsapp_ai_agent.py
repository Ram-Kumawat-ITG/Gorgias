# WhatsApp AI Sales Agent — processes inbound WhatsApp messages, detects Shopify intent,
# executes Shopify operations, and sends conversational replies back to the customer.
import json
from groq import AsyncGroq
from app.config import settings
from app.services.shopify_client import shopify_get, shopify_post, ShopifyAPIError

SYSTEM_PROMPT = """You are Aria, a friendly and knowledgeable sales assistant for our online store on WhatsApp.

You talk like a real human salesperson — warm, helpful, natural. Never sound robotic or corporate.
Use casual but professional language. Use emojis occasionally to keep it friendly (not every message).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR PERSONALITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Warm, friendly, and enthusiastic about helping
- Ask ONE question at a time — never bombard the customer
- Remember everything said earlier in the conversation
- Compliment good choices ("Great pick! That one sells out fast 🔥")
- If you don't know something, be honest about it
- Never say "I am an AI" — just be Aria, the helpful store assistant

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONVERSATION FLOW (FOLLOW THIS ORDER)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1 — GREET AND UNDERSTAND
  When a customer first messages you, greet them warmly and ask what they are looking for.
  Example: "Hey! 👋 Welcome! I'm Aria, your personal shopping assistant. What can I help you with today?"

STEP 2 — COLLECT PRODUCT / INTENT
  Understand what they want. Ask about:
  - Product name or type
  - Quantity (how many)
  - Any variant (size, color, model)
  - Their budget if relevant
  Guide them like a real salesperson would. Suggest alternatives if needed.

STEP 3 — COLLECT EMAIL (naturally, not robotically)
  Once you know what they want, ask for their email in a natural way.
  Example: "Perfect! To get your order sorted, could I grab your email address? 😊"
  OR: "Almost there! What email should I use for your order?"
  NEVER say "Email is mandatory" or "You must provide email" — just ask naturally.

STEP 4 — CONFIRM AND EXECUTE
  Summarize what you are about to do and confirm with the customer.
  Example: "So I'll place an order for 2x iPhone 15 to your email john@example.com — does that look right? ✅"

STEP 5 — COMPLETE ACTION AND CLOSE
  Execute the action, confirm it worked, and offer further help.
  Example: "Done! 🎉 Your order #1042 has been placed. You'll get a confirmation shortly. Anything else I can help with?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INFORMATION TO COLLECT (NATURALLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For ORDERS:
  - Product name → ask "What product are you looking for?"
  - Quantity → ask "How many would you like?"
  - Variant → ask "Any preference on size / color / model?"
  - Email → ask naturally after product is confirmed
  - Shipping address → ask if needed for the order

For ORDER TRACKING / CANCEL:
  - Email first → then look up their orders
  - If multiple orders, ask which one: "You have 2 orders — which one? Your latest #1042 or #1038?"

For INVENTORY / PRODUCT INQUIRY:
  - Ask what product they want to know about
  - Check availability and tell them stock status warmly
  - If low stock: "Heads up — only 3 left in stock! Want me to grab one for you? 😊"
  - If out of stock: "Ah, that one just sold out 😔 But I can let you know when it's back, or suggest something similar!"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUPPORTED ACTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- create_order: Place a new order for the customer
- cancel_order: Cancel an existing order (ask for confirmation first)
- fetch_order: Look up order status / tracking
- check_inventory: Check if a product is in stock and how many are available
- fetch_customer: Look up customer account details
- create_customer: Register a new customer
- ask_email: You need the email — ask for it naturally
- ask_product: You need product info — ask what they want
- ask_confirmation: Confirm before doing something destructive
- none: Keep the conversation going, no action needed yet

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESTRUCTIVE ACTIONS (cancel / delete)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Always confirm first:
  "Just to confirm — you want to cancel Order #1042 (iPhone 15 x2)? This can't be undone. Type YES to proceed."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Keep messages SHORT — WhatsApp, not email
- One idea per message
- Use line breaks for readability
- Never use bullet points with dashes — use natural sentences
- Never say "extracted_data" or "action type" or any technical terms
- If something fails, apologize naturally: "Hmm, something went wrong on our end. Let me try again..."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — STRICT JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY this JSON — no text outside it, no markdown:

{
  "action": "create_order | cancel_order | fetch_order | check_inventory | fetch_customer | create_customer | ask_email | ask_product | ask_confirmation | none",
  "email": "customer email if known, else null",
  "order_id": "shopify order id if known, else null",
  "products": [{"name": "product name", "quantity": 1}],
  "inventory_query": "product name to check stock for, or null",
  "message": "The actual WhatsApp message to send — written like a human salesperson, warm and natural"
}

RULES:
- "message" is ALWAYS the exact text sent to the customer — write it naturally, as Aria
- If email is not yet known and action requires it → action = "ask_email", ask naturally in message
- If product is not yet known → action = "ask_product", ask in message
- Never leave "message" empty
- Output ONLY valid JSON, nothing else"""


async def _get_conversation_history(ticket_id: str) -> list:
    """Fetch all non-internal messages for a ticket, ordered by creation time."""
    from app.database import get_db
    db = get_db()
    cursor = db.messages.find(
        {"ticket_id": ticket_id, "is_internal_note": {"$ne": True}},
        sort=[("created_at", 1)],
    )
    return [doc async for doc in cursor]


async def _find_customer(email: str) -> dict | None:
    """Search Shopify for a customer by email."""
    try:
        result = await shopify_get("/customers/search.json", params={"query": f"email:{email}", "limit": 1})
        customers = result.get("customers", [])
        return customers[0] if customers else None
    except ShopifyAPIError:
        return None


async def _create_customer(email: str, name: str = "", phone: str = "") -> dict | None:
    """Create a new Shopify customer."""
    parts = name.split(" ", 1) if name else []
    data: dict = {
        "customer": {
            "email": email,
            "first_name": parts[0] if parts else "",
            "last_name": parts[1] if len(parts) > 1 else "",
        }
    }
    if phone:
        data["customer"]["phone"] = phone
    try:
        result = await shopify_post("/customers.json", data)
        return result.get("customer")
    except ShopifyAPIError:
        return None


async def _find_product(name: str) -> dict | None:
    """Search Shopify for a product by title."""
    try:
        result = await shopify_get("/products.json", params={"title": name, "limit": 1})
        products = result.get("products", [])
        return products[0] if products else None
    except ShopifyAPIError:
        return None


async def _check_inventory(product_name: str) -> str:
    """Check stock for a product and return a human-friendly status string."""
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
        # If inventory_management is not set, treat as always available
        unmanaged = [v for v in variants if v.get("inventory_management") != "shopify"]
        if unmanaged and total_stock == 0:
            return f"available|unlimited|{title}"

        if total_stock == 0:
            return f"out_of_stock|0|{title}"
        return f"in_stock|{total_stock}|{title}"
    except ShopifyAPIError:
        return f"error|0|{product_name}"


async def _get_order(order_id: str) -> dict | None:
    """Fetch a Shopify order by ID."""
    try:
        result = await shopify_get(f"/orders/{order_id}.json")
        return result.get("order")
    except ShopifyAPIError:
        return None


async def _cancel_order(order_id: str) -> bool:
    """Cancel a Shopify order."""
    try:
        await shopify_post(f"/orders/{order_id}/cancel.json", {})
        return True
    except ShopifyAPIError:
        return False


async def _execute_action(agent_result: dict, customer_name: str = "", customer_phone: str = "") -> str:
    """Execute the Shopify action from the AI result. Returns the message to send back."""
    action = agent_result.get("action", "none")
    email = agent_result.get("email") or ""
    default_msg = agent_result.get("message", "Hmm, something went wrong on my end. Let me try again shortly!")

    # These actions need no Shopify call — the AI message is the reply
    if action in ("ask_email", "ask_product", "ask_confirmation", "none"):
        return default_msg

    # ── Inventory check — no email required ──────────────────────────────────
    if action == "check_inventory":
        query = agent_result.get("inventory_query") or ""
        products_list = agent_result.get("products") or []
        if not query and products_list:
            query = products_list[0].get("name", "")
        if not query:
            return default_msg

        status_raw = await _check_inventory(query)
        status, qty, title = status_raw.split("|", 2)

        if status == "in_stock":
            qty_int = int(qty)
            if qty_int <= 3:
                return (
                    f"Great news — *{title}* is available! 🙌\n"
                    f"Heads up though, only *{qty_int} left* in stock. Want me to grab one for you before it sells out? 😊"
                )
            return (
                f"Yes, *{title}* is in stock! ✅\n"
                f"We have *{qty_int} units* ready to ship. Want to place an order?"
            )
        elif status == "available":
            return (
                f"*{title}* is available and ready to ship! 🚀\n"
                f"How many would you like?"
            )
        elif status == "out_of_stock":
            return (
                f"Ah, *{title}* is out of stock right now 😔\n"
                f"Would you like me to suggest something similar, or let you know when it's back?"
            )
        else:
            return f"I wasn't able to check the stock for *{query}* right now. Can you double-check the product name? 🙏"

    # ── All actions below require email ──────────────────────────────────────
    if not email:
        return default_msg

    if action == "fetch_customer":
        customer = await _find_customer(email)
        if customer:
            name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            orders = customer.get("orders_count", 0)
            spent = customer.get("total_spent", "0.00")
            return (
                f"Found your account! 😊\n"
                f"Name: {name or 'N/A'}\n"
                f"Email: {email}\n"
                f"Total Orders: {orders}\n"
                f"Total Spent: ${spent}\n\n"
                f"What can I help you with today?"
            )
        return (
            f"Hmm, I couldn't find an account with *{email}*.\n"
            f"Would you like me to create one for you so we can get started? 😊"
        )

    if action == "create_customer":
        existing = await _find_customer(email)
        if existing:
            name = f"{existing.get('first_name', '')} {existing.get('last_name', '')}".strip()
            return (
                f"Welcome back{', ' + name if name else ''}! 👋\n"
                f"I found your account. What would you like to do today?"
            )
        customer = await _create_customer(email, customer_name, customer_phone)
        if customer:
            return (
                f"You're all set! 🎉 I've created your account with *{email}*.\n"
                f"Now, what would you like to order?"
            )
        return "Hmm, something went wrong creating your account. Could you try again in a moment? 🙏"

    if action == "fetch_order":
        order_id = agent_result.get("order_id") or ""
        if not order_id:
            # Try to find the most recent order for this email
            try:
                result = await shopify_get("/orders.json", params={
                    "email": email, "limit": 1, "status": "any"
                })
                orders = result.get("orders", [])
                if orders:
                    order_id = str(orders[0]["id"])
                else:
                    return f"I couldn't find any orders for *{email}*. Is this the right email? 🤔"
            except ShopifyAPIError:
                return default_msg

        order = await _get_order(order_id)
        if order:
            items = ", ".join(
                f"{li.get('name')} x{li.get('quantity')}"
                for li in order.get("line_items", [])
            )
            fulfillment = order.get("fulfillment_status") or "not shipped yet"
            payment = order.get("financial_status", "pending")
            total = f"{order.get('total_price')} {order.get('currency')}"
            ff = (order.get("fulfillments") or [{}])[-1]
            tracking = ff.get("tracking_number")
            tracking_line = f"\nTracking: *{tracking}*" if tracking else ""
            return (
                f"Here's your order info 📦\n\n"
                f"Order *#{order.get('order_number')}*\n"
                f"Items: {items or 'N/A'}\n"
                f"Payment: {payment}\n"
                f"Status: {fulfillment}\n"
                f"Total: {total}"
                f"{tracking_line}\n\n"
                f"Anything else you need? 😊"
            )
        return f"I couldn't find that order. Could you double-check the order number? 🙏"

    if action == "cancel_order":
        order_id = agent_result.get("order_id") or ""
        if not order_id:
            # Look up by email
            try:
                result = await shopify_get("/orders.json", params={
                    "email": email, "limit": 1, "status": "open"
                })
                orders = result.get("orders", [])
                if orders:
                    order_id = str(orders[0]["id"])
                    order_num = orders[0].get("order_number")
                    return (
                        f"I found your latest open order *#{order_num}*.\n"
                        f"Are you sure you want to cancel it? Just reply *YES* to confirm 🙏"
                    )
                return f"I couldn't find any open orders for *{email}*."
            except ShopifyAPIError:
                return default_msg

        success = await _cancel_order(order_id)
        if success:
            return (
                f"Done! Your order has been cancelled. 😔\n"
                f"If you change your mind or want to place a new order, I'm right here! 😊"
            )
        return "Hmm, I wasn't able to cancel that order. It might already be shipped. Want me to look into it? 🤔"

    if action == "create_order":
        products = agent_result.get("products") or []
        if not products:
            return default_msg

        # Find or create customer in Shopify
        customer = await _find_customer(email)
        if not customer:
            customer = await _create_customer(email, customer_name, customer_phone)
        if not customer:
            return "I had trouble looking up your account. Could you double-check your email? 🙏"

        # Resolve product variants from Shopify catalog
        line_items = []
        missing = []
        for p in products:
            product = await _find_product(p.get("name", ""))
            if product and product.get("variants"):
                variant = product["variants"][0]
                stock = int(variant.get("inventory_quantity") or 0)
                qty = int(p.get("quantity") or 1)
                if variant.get("inventory_management") == "shopify" and stock < qty:
                    if stock == 0:
                        missing.append(f"{p.get('name')} (out of stock)")
                        continue
                    # Adjust to available stock
                    qty = stock
                line_items.append({"variant_id": variant["id"], "quantity": qty})
            else:
                missing.append(p.get("name", "unknown"))

        if missing and not line_items:
            return (
                f"Sorry, I couldn't find *{', '.join(missing)}* in our store right now 😔\n"
                f"Could you check the product name or describe what you're looking for?"
            )

        try:
            result = await shopify_post("/orders.json", {
                "order": {
                    "customer": {"id": customer["id"]},
                    "line_items": line_items,
                    "financial_status": "pending",
                }
            })
            order = result.get("order", {})
            order_num = order.get("order_number")
            total = f"{order.get('total_price')} {order.get('currency')}"
            out_of_stock_note = (
                f"\n\n⚠️ Note: *{', '.join(missing)}* couldn't be added (out of stock)."
                if missing else ""
            )
            return (
                f"Your order is placed! 🎉\n\n"
                f"Order *#{order_num}*\n"
                f"Total: *{total}*\n"
                f"You'll get a confirmation on *{email}* shortly.{out_of_stock_note}\n\n"
                f"Is there anything else I can help you with? 😊"
            )
        except ShopifyAPIError as e:
            print(f"Shopify create_order error: {e}")
            return "Hmm, something went wrong placing the order. Let me try again — could you resend your request? 🙏"

    # Fallback — return the AI-generated message as-is
    return default_msg


async def process_whatsapp_message(
    ticket_id: str,
    phone_number_id: str,
    customer_phone: str,
    current_message: str,
    merchant_id: str = None,
    customer_name: str = "",
) -> str | None:
    """
    Run the AI Sales Agent on an inbound WhatsApp message.
    Returns the reply text to send back to the customer, or None if agent is disabled/fails.
    """
    if not settings.groq_api_key:
        print("WhatsApp AI Agent: GROQ_API_KEY is not set — chatbot disabled")
        return None

    # Build chat messages: system prompt + conversation history
    # History already includes the current message (saved by create_ticket_from_whatsapp before this runs)
    history = await _get_conversation_history(ticket_id)

    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        role = "user" if msg.get("sender_type") == "customer" else "assistant"
        body = (msg.get("body") or "").strip()
        if body:
            chat_messages.append({"role": role, "content": body})

    # Guard: if history is empty or last message isn't from the customer, append current message
    # This prevents duplicate user turns while ensuring the conversation always ends on a user message
    if not chat_messages or chat_messages[-1].get("role") != "user":
        chat_messages.append({"role": "user", "content": current_message})

    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=chat_messages,
            max_tokens=600,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model wraps output
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rstrip("`").strip()

        result = json.loads(raw)

        # Execute Shopify operation; returns user-facing message
        reply = await _execute_action(result, customer_name, customer_phone)

        # If the AI captured a real email this turn, sync it to MongoDB
        result_email = (result.get("email") or "").strip()
        if result_email and "@" in result_email and not result_email.endswith(".placeholder"):
            from app.database import get_db
            db = get_db()
            if db is not None:
                try:
                    placeholder = f"{customer_phone}@whatsapp.placeholder"
                    await db.customers.update_one(
                        {"email": placeholder},
                        {"$set": {"email": result_email}},
                    )
                    await db.tickets.update_one(
                        {"id": ticket_id, "customer_email": placeholder},
                        {"$set": {"customer_email": result_email}},
                    )
                except Exception:
                    pass

        return reply or result.get("message") or None

    except json.JSONDecodeError:
        # Model returned plain text — use it directly if it looks like a proper response
        if raw and len(raw) < 1000:
            return raw
        return None
    except Exception as e:
        print(f"WhatsApp AI Agent error: {e}")
        return None
