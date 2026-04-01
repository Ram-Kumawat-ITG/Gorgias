# WhatsApp AI Sales Agent — processes inbound WhatsApp messages, detects Shopify intent,
# executes Shopify operations, and sends conversational replies back to the customer.
import json
from groq import AsyncGroq
from app.config import settings
from app.services.shopify_client import shopify_get, shopify_post, shopify_put, ShopifyAPIError

SYSTEM_PROMPT = """You are Ram, a friendly and knowledgeable sales and support assistant for our online store on WhatsApp.

You talk like a real human — warm, helpful, natural. Never sound robotic or corporate.
Use casual but professional language. Use emojis occasionally to keep it friendly (not every message).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR PERSONALITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Warm, friendly, and enthusiastic about helping
- Ask ONE question at a time — never bombard the customer
- Remember everything said earlier in the conversation — never re-ask for info already given
- Do NOT greet the customer again mid-conversation — they have already been welcomed
- If you don't know something, be honest about it
- Never say "I am an AI" — just be Ram, the helpful store assistant

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT-AWARE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- If the customer already provided their email earlier → use it, don't ask again
- If an order number was mentioned earlier → remember it for follow-up actions
- If order details were just shown → the customer can request cancel/refund/replacement without re-entering info
- After an email correction → immediately retry the order lookup without asking again
- If user types a number like "1042" or "#1042" after asking about orders → that is the order number

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORDER LOOKUP GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- User gives order number ("1042" / "#1042") → set order_number = "1042", action = fetch_order
- User gives email → set email, action = fetch_order
- User gives both → set both (most accurate)
- User gives neither → action = ask_order_number (preferred) or ask_email
- Order not found with given email → suggest checking the email or providing the order number

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INFORMATION TO COLLECT (NATURALLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For NEW ORDERS:
  - Product name → ask "What product are you looking for?"
  - Quantity → ask "How many would you like?"
  - Variant → ask "Any preference on size / color / model?"
  - Email → ask naturally after product is confirmed

For ORDER TRACKING / CANCEL / REFUND / REPLACEMENT:
  - Order number → "Could you share your order number? It looks like #1042"
  - Or email → "What email did you use for the order?"
  - If multiple orders → "You have 2 orders — which one? Your latest #1042 or #1038?"

For INVENTORY / PRODUCT INQUIRY:
  - Ask what product they want to know about
  - Check availability and tell them stock status warmly
  - If low stock: "Heads up — only 3 left in stock! Want me to grab one? 😊"
  - If out of stock: "Ah, that one just sold out 😔 Want me to suggest something similar?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUPPORTED ACTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- create_order: Place a new order for the customer
- cancel_order: Cancel an existing order (always confirm first)
- request_refund: Customer wants a refund for their order
- request_replacement: Customer wants a replacement or exchange
- fetch_order: Look up order status, items, tracking
- check_inventory: Check if a product is in stock
- fetch_customer: Look up customer account details
- create_customer: Register a new customer
- ask_email: Need the email — ask naturally
- ask_order_number: Need the order number — ask naturally
- ask_product: Need product info — ask what they want
- ask_confirmation: Confirm before a destructive action
- none: Keep conversation going, no Shopify action needed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESTRUCTIVE ACTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Always confirm before cancel:
  "Just to confirm — you want to cancel Order #1042? This can't be undone. Reply *YES* to proceed."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Keep messages SHORT — WhatsApp, not email
- One idea per message
- Use line breaks for readability
- Use *bold* for key info (order numbers, totals)
- Never use dashes as bullet points
- Never say "extracted_data" or "action type" or any technical terms
- If something fails: "Hmm, something went wrong on our end. Let me try again..."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — STRICT JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY this JSON — no text outside it, no markdown:

{
  "action": "create_order | cancel_order | request_refund | request_replacement | fetch_order | check_inventory | fetch_customer | create_customer | ask_email | ask_order_number | ask_product | ask_confirmation | none",
  "email": "customer email if known from conversation, else null",
  "order_id": "shopify internal order id if known from a previous lookup, else null",
  "order_number": "order number like 1042 if user mentioned it (digits only, no # prefix), else null",
  "products": [{"name": "product name", "quantity": 1}],
  "inventory_query": "product name to check stock for, or null",
  "message": "The actual WhatsApp message to send — written naturally, as Ram"
}

RULES:
- "message" is ALWAYS the exact text sent to the customer
- If email not known and action requires it → action = "ask_email"
- If order number not known and action requires it → action = "ask_order_number"
- Never leave "message" empty
- Output ONLY valid JSON, nothing else"""


# ── Conversation history ──────────────────────────────────────────────────────

async def _get_conversation_history(ticket_id: str) -> list:
    """Fetch all non-internal messages for a ticket, ordered by creation time."""
    from app.database import get_db
    db = get_db()
    cursor = db.messages.find(
        {"ticket_id": ticket_id, "is_internal_note": {"$ne": True}},
        sort=[("created_at", 1)],
    )
    return [doc async for doc in cursor]


# ── Shopify helpers ───────────────────────────────────────────────────────────

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
    """Check stock for a product and return a pipe-delimited status string."""
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
        unmanaged = [v for v in variants if v.get("inventory_management") != "shopify"]
        if unmanaged and total_stock == 0:
            return f"available|unlimited|{title}"
        if total_stock == 0:
            return f"out_of_stock|0|{title}"
        return f"in_stock|{total_stock}|{title}"
    except ShopifyAPIError:
        return f"error|0|{product_name}"


async def _get_order(order_id: str) -> dict | None:
    """Fetch a Shopify order by internal numeric ID."""
    try:
        result = await shopify_get(f"/orders/{order_id}.json")
        return result.get("order")
    except ShopifyAPIError:
        return None


async def _fetch_order_by_number(order_number: str, email: str = "") -> tuple[dict | None, str]:
    """Look up a Shopify order by order number (e.g. '1042'), optionally cross-validating
    against the customer email.

    Returns (order_dict, error_message). On success error_message is "".
    """
    # Shopify stores order_number as integer; the `name` field is "#1042"
    clean_number = str(order_number).lstrip("#").strip()
    if not clean_number.isdigit():
        return None, f"'{order_number}' doesn't look like a valid order number."

    try:
        result = await shopify_get(
            "/orders.json",
            params={"name": f"#{clean_number}", "status": "any", "limit": 1},
        )
        orders = result.get("orders", [])
        if not orders:
            return None, f"I couldn't find Order *#{clean_number}*. Could you double-check the number? 🙏"

        order = orders[0]

        # Cross-validate email when provided
        if email:
            order_email = (order.get("email") or order.get("contact_email") or "").lower()
            if order_email and email.lower() not in order_email and order_email not in email.lower():
                return None, (
                    f"I found Order *#{clean_number}*, but it doesn't seem to match *{email}*. 🤔\n"
                    f"Could you double-check your email or the order number?"
                )

        return order, ""
    except ShopifyAPIError:
        return None, "I had trouble looking that up. Could you try again in a moment? 🙏"


async def _get_product_image_url(product_id) -> str:
    """Return the first image URL for a Shopify product, or empty string if unavailable."""
    if not product_id:
        return ""
    try:
        result = await shopify_get(
            f"/products/{product_id}.json",
            params={"fields": "id,images"},
        )
        images = result.get("product", {}).get("images", [])
        return images[0].get("src", "") if images else ""
    except ShopifyAPIError:
        return ""


def _format_order_details(order: dict) -> str:
    """Build a WhatsApp-formatted order detail string (kept under 1 000 chars)."""
    order_num = order.get("order_number", "")
    currency  = order.get("currency", "")
    line_items = order.get("line_items", [])

    # Build items block
    items_lines = []
    for li in line_items:
        title   = li.get("title", "")
        variant = li.get("variant_title") or ""
        qty     = li.get("quantity", 1)
        price   = float(li.get("price", 0))
        subtotal = price * qty

        line = f"• *{title}*"
        if variant and variant.lower() != "default title":
            line += f" ({variant})"
        line += f" × {qty}  —  {currency} {subtotal:.2f}"
        items_lines.append(line)

    items_text = "\n".join(items_lines) or "N/A"

    # Payment & fulfillment status
    payment     = (order.get("financial_status") or "pending").replace("_", " ").title()
    fulfillment = (order.get("fulfillment_status") or "not shipped").replace("_", " ").title()
    total       = order.get("total_price", "0.00")

    # Tracking
    fulfillments  = order.get("fulfillments") or []
    tracking_line = ""
    if fulfillments:
        last_ff = fulfillments[-1]
        tracking_num = last_ff.get("tracking_number")
        tracking_url = last_ff.get("tracking_url")
        if tracking_num:
            tracking_line = f"\n📍 Tracking: *{tracking_num}*"
            if tracking_url:
                tracking_line += f"\n🔗 {tracking_url}"

    msg = (
        f"📦 Order *#{order_num}*\n\n"
        f"🛍 *Items:*\n{items_text}\n\n"
        f"💳 Payment: *{payment}*\n"
        f"🚚 Shipping: *{fulfillment}*"
        f"{tracking_line}\n"
        f"💰 Total: *{currency} {total}*"
    )
    return msg


async def _cancel_order(order_id: str) -> bool:
    """Cancel a Shopify order."""
    try:
        await shopify_post(f"/orders/{order_id}/cancel.json", {})
        return True
    except ShopifyAPIError:
        return False


async def _add_order_note(order_id: str, note: str, tag: str = "") -> bool:
    """Append a note (and optional tag) to a Shopify order without overwriting existing data."""
    try:
        update_data: dict = {"order": {"id": order_id, "note": note}}
        if tag:
            # Fetch current tags first to avoid overwriting them
            current = await shopify_get(
                f"/orders/{order_id}.json", params={"fields": "tags"}
            )
            current_tags = current.get("order", {}).get("tags", "")
            new_tags = (current_tags + f", {tag}").strip(", ") if current_tags else tag
            update_data["order"]["tags"] = new_tags
        await shopify_put(f"/orders/{order_id}.json", update_data)
        return True
    except ShopifyAPIError:
        return False


# ── Action executor ───────────────────────────────────────────────────────────

async def _execute_action(
    agent_result: dict,
    customer_name: str = "",
    customer_phone: str = "",
) -> tuple[str, dict | None]:
    """Execute the Shopify action from the AI result.

    Returns (text_reply, interactive_payload_or_None).

    When interactive_payload is not None the caller should send it as a
    WhatsApp interactive button message via send_interactive_buttons().
    interactive_payload keys:
        body (str)         — order detail text for the button message body
        buttons (list)     — [{"id": ..., "title": ...}, ...]
        image_url (str)    — optional product image URL for the header
    """
    action      = agent_result.get("action", "none")
    email       = (agent_result.get("email") or "").strip()
    order_id    = (agent_result.get("order_id") or "").strip()
    order_number= (agent_result.get("order_number") or "").strip().lstrip("#")
    default_msg = agent_result.get("message", "Hmm, something went wrong on my end. Let me try again shortly!")

    # ── Conversational / no-op actions ───────────────────────────────────────
    if action in ("ask_email", "ask_order_number", "ask_product", "ask_confirmation", "none"):
        return default_msg, None

    # ── Inventory check (no email required) ──────────────────────────────────
    if action == "check_inventory":
        query = agent_result.get("inventory_query") or ""
        if not query:
            products_list = agent_result.get("products") or []
            query = products_list[0].get("name", "") if products_list else ""
        if not query:
            return default_msg, None

        status_raw = await _check_inventory(query)
        status, qty, title = status_raw.split("|", 2)

        if status == "in_stock":
            qty_int = int(qty)
            if qty_int <= 3:
                return (
                    f"Great news — *{title}* is available! 🙌\n"
                    f"Heads up though, only *{qty_int} left* in stock. Want me to grab one before it sells out? 😊"
                ), None
            return (
                f"Yes, *{title}* is in stock! ✅\n"
                f"We have *{qty_int} units* ready to ship. Want to place an order?"
            ), None
        if status == "available":
            return (
                f"*{title}* is available and ready to ship! 🚀\n"
                f"How many would you like?"
            ), None
        if status == "out_of_stock":
            return (
                f"Ah, *{title}* is out of stock right now 😔\n"
                f"Would you like me to suggest something similar, or let you know when it's back?"
            ), None
        return f"I wasn't able to check stock for *{query}* right now. Could you double-check the product name? 🙏", None

    # ── Fetch order — rich display with interactive buttons ───────────────────
    if action == "fetch_order":
        order = None
        err   = ""

        # Priority 1: lookup by order number (most reliable)
        if order_number:
            order, err = await _fetch_order_by_number(order_number, email)

        # Priority 2: lookup by Shopify internal order_id (from prior fetch)
        if not order and order_id:
            order = await _get_order(order_id)
            if not order:
                err = f"I couldn't find the order. Could you share the order number? 🙏"

        # Priority 3: lookup latest order by email
        if not order and email:
            try:
                result = await shopify_get(
                    "/orders.json",
                    params={"email": email, "limit": 1, "status": "any"},
                )
                orders = result.get("orders", [])
                if orders:
                    order = orders[0]
                else:
                    err = f"I couldn't find any orders for *{email}*. Is that the right email? 🤔"
            except ShopifyAPIError:
                err = default_msg

        if not order:
            return err or default_msg, None

        # Build rich text detail
        details_text = _format_order_details(order)
        real_order_id = str(order.get("id", ""))
        order_num_str = str(order.get("order_number", ""))

        # Try to get product image from first line item
        image_url = ""
        line_items = order.get("line_items", [])
        if line_items:
            first_product_id = line_items[0].get("product_id")
            if first_product_id:
                image_url = await _get_product_image_url(first_product_id)

        # Interactive buttons: Cancel / Refund / Replacement
        buttons = [
            {"id": f"cancel_{real_order_id}",  "title": "Cancel Order"},
            {"id": f"refund_{real_order_id}",   "title": "Request Refund"},
            {"id": f"replace_{real_order_id}",  "title": "Replacement"},
        ]

        interactive_payload = {
            "body":      details_text,
            "buttons":   buttons,
            "image_url": image_url,
        }
        # Return a short text fallback + the interactive payload
        return f"Here are your order details 👇", interactive_payload

    # ── All remaining actions require email ───────────────────────────────────
    if not email and action not in ("cancel_order", "request_refund", "request_replacement"):
        return default_msg, None

    # ── Fetch customer ────────────────────────────────────────────────────────
    if action == "fetch_customer":
        customer = await _find_customer(email)
        if customer:
            name   = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            orders = customer.get("orders_count", 0)
            spent  = customer.get("total_spent", "0.00")
            return (
                f"Found your account! 😊\n"
                f"Name: {name or 'N/A'}\n"
                f"Email: {email}\n"
                f"Total Orders: {orders}\n"
                f"Total Spent: ${spent}\n\n"
                f"What can I help you with today?"
            ), None
        return (
            f"Hmm, I couldn't find an account with *{email}*.\n"
            f"Would you like me to create one so we can get started? 😊"
        ), None

    # ── Create customer ───────────────────────────────────────────────────────
    if action == "create_customer":
        existing = await _find_customer(email)
        if existing:
            name = f"{existing.get('first_name', '')} {existing.get('last_name', '')}".strip()
            return (
                f"Welcome back{', ' + name if name else ''}! 👋\n"
                f"I found your account. What would you like to do today?"
            ), None
        customer = await _create_customer(email, customer_name, customer_phone)
        if customer:
            return (
                f"You're all set! 🎉 I've created your account with *{email}*.\n"
                f"Now, what would you like to order?"
            ), None
        return "Hmm, something went wrong creating your account. Could you try again in a moment? 🙏", None

    # ── Cancel order ──────────────────────────────────────────────────────────
    if action == "cancel_order":
        # Resolve order_id from order_number if needed
        if not order_id and order_number:
            order, err = await _fetch_order_by_number(order_number, email)
            if order:
                order_id = str(order.get("id", ""))
            else:
                return err or default_msg, None

        if not order_id and email:
            try:
                result = await shopify_get(
                    "/orders.json",
                    params={"email": email, "limit": 1, "status": "open"},
                )
                orders = result.get("orders", [])
                if orders:
                    order_id  = str(orders[0]["id"])
                    order_num = orders[0].get("order_number")
                    return (
                        f"I found your latest open order *#{order_num}*.\n"
                        f"Are you sure you want to cancel it? Just reply *YES* to confirm 🙏"
                    ), None
                return f"I couldn't find any open orders for *{email}*.", None
            except ShopifyAPIError:
                return default_msg, None

        if not order_id:
            return default_msg, None

        success = await _cancel_order(order_id)
        if success:
            return (
                f"Done! Your order has been cancelled. 😔\n"
                f"If you change your mind or want to place a new order, I'm right here! 😊"
            ), None
        return "Hmm, I wasn't able to cancel that order. It might already be shipped. Want me to look into it? 🤔", None

    # ── Request refund ────────────────────────────────────────────────────────
    if action == "request_refund":
        # Resolve order_id
        if not order_id and order_number:
            order, err = await _fetch_order_by_number(order_number, email)
            if order:
                order_id  = str(order.get("id", ""))
                order_num = order.get("order_number", "")
            else:
                return err or default_msg, None
        elif not order_id and email:
            try:
                result = await shopify_get(
                    "/orders.json",
                    params={"email": email, "limit": 1, "status": "any"},
                )
                orders = result.get("orders", [])
                if orders:
                    order_id  = str(orders[0]["id"])
                    order_num = orders[0].get("order_number", "")
                else:
                    return f"I couldn't find any orders for *{email}*. Is that the right email? 🤔", None
            except ShopifyAPIError:
                return default_msg, None

        if not order_id:
            return default_msg, None

        from datetime import datetime
        note = f"Customer requested refund via WhatsApp on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
        await _add_order_note(order_id, note, tag="refund-requested")
        return (
            f"Got it! I've flagged your refund request for Order *#{order_num if 'order_num' in dir() else order_number}*. 🙏\n\n"
            f"Our team will review it and get back to you within 24–48 hours.\n"
            f"Is there anything else I can help with?"
        ), None

    # ── Request replacement ───────────────────────────────────────────────────
    if action == "request_replacement":
        if not order_id and order_number:
            order, err = await _fetch_order_by_number(order_number, email)
            if order:
                order_id  = str(order.get("id", ""))
                order_num = order.get("order_number", "")
            else:
                return err or default_msg, None
        elif not order_id and email:
            try:
                result = await shopify_get(
                    "/orders.json",
                    params={"email": email, "limit": 1, "status": "any"},
                )
                orders = result.get("orders", [])
                if orders:
                    order_id  = str(orders[0]["id"])
                    order_num = orders[0].get("order_number", "")
                else:
                    return f"I couldn't find any orders for *{email}*. Is that the right email? 🤔", None
            except ShopifyAPIError:
                return default_msg, None

        if not order_id:
            return default_msg, None

        from datetime import datetime
        note = f"Customer requested replacement via WhatsApp on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
        await _add_order_note(order_id, note, tag="replacement-requested")
        return (
            f"Done! I've logged your replacement request for Order *#{order_num if 'order_num' in dir() else order_number}*. ✅\n\n"
            f"Our team will arrange a replacement and reach out shortly.\n"
            f"Anything else I can help with?"
        ), None

    # ── Create order ──────────────────────────────────────────────────────────
    if action == "create_order":
        if not email:
            return default_msg, None
        products = agent_result.get("products") or []
        if not products:
            return default_msg, None

        customer = await _find_customer(email)
        if not customer:
            customer = await _create_customer(email, customer_name, customer_phone)
        if not customer:
            return "I had trouble looking up your account. Could you double-check your email? 🙏", None

        line_items = []
        missing    = []
        for p in products:
            product = await _find_product(p.get("name", ""))
            if product and product.get("variants"):
                variant = product["variants"][0]
                stock   = int(variant.get("inventory_quantity") or 0)
                qty     = int(p.get("quantity") or 1)
                if variant.get("inventory_management") == "shopify" and stock < qty:
                    if stock == 0:
                        missing.append(f"{p.get('name')} (out of stock)")
                        continue
                    qty = stock
                line_items.append({"variant_id": variant["id"], "quantity": qty})
            else:
                missing.append(p.get("name", "unknown"))

        if missing and not line_items:
            return (
                f"Sorry, I couldn't find *{', '.join(missing)}* in our store right now 😔\n"
                f"Could you check the product name or describe what you're looking for?"
            ), None

        try:
            result = await shopify_post("/orders.json", {
                "order": {
                    "customer": {"id": customer["id"]},
                    "line_items": line_items,
                    "financial_status": "pending",
                }
            })
            order     = result.get("order", {})
            order_num = order.get("order_number")
            total     = f"{order.get('total_price')} {order.get('currency')}"
            oos_note  = (
                f"\n\n⚠️ *{', '.join(missing)}* couldn't be added (out of stock)."
                if missing else ""
            )
            return (
                f"Your order is placed! 🎉\n\n"
                f"Order *#{order_num}*\n"
                f"Total: *{total}*\n"
                f"You'll get a confirmation on *{email}* shortly.{oos_note}\n\n"
                f"Anything else I can help with? 😊"
            ), None
        except ShopifyAPIError as e:
            print(f"Shopify create_order error: {e}")
            return "Hmm, something went wrong placing the order. Could you resend your request? 🙏", None

    # ── Fallback ──────────────────────────────────────────────────────────────
    return default_msg, None


# ── Main entry point ──────────────────────────────────────────────────────────

async def process_whatsapp_message(
    ticket_id: str,
    phone_number_id: str,
    customer_phone: str,
    current_message: str,
    merchant_id: str = None,
    customer_name: str = "",
) -> str | None:
    """Run the AI Sales Agent on an inbound WhatsApp message.

    Returns the reply text to send back via send_text_message(), or None when:
    - GROQ_API_KEY is not set
    - An interactive button message was sent directly (handled here)
    - Agent fails
    """
    if not settings.groq_api_key:
        print("WhatsApp AI Agent: GROQ_API_KEY is not set — chatbot disabled")
        return None

    history = await _get_conversation_history(ticket_id)

    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        role = "user" if msg.get("sender_type") == "customer" else "assistant"
        body = (msg.get("body") or "").strip()
        if body:
            chat_messages.append({"role": role, "content": body})

    # Guard: ensure conversation ends on a user turn
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

        reply, interactive_payload = await _execute_action(result, customer_name, customer_phone)

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

        # Send interactive button message if the action produced one
        if interactive_payload:
            try:
                from app.services.whatsapp_service import get_whatsapp_config, send_interactive_buttons
                from app.models.message import MessageInDB as _MsgInDB
                from app.database import get_db as _get_db

                wa_cfg = await get_whatsapp_config(merchant_id)
                iresult = await send_interactive_buttons(
                    to_phone=customer_phone,
                    body_text=interactive_payload["body"],
                    buttons=interactive_payload["buttons"],
                    image_url=interactive_payload.get("image_url", ""),
                    footer_text="Tap a button to take action",
                    config=wa_cfg,
                )
                # Persist the interactive message to the ticket thread
                _db = _get_db()
                if _db is not None:
                    imsg_list = iresult.get("messages") or []
                    isent_id  = imsg_list[0].get("id") if imsg_list else None
                    imsg_doc  = _MsgInDB(
                        ticket_id=ticket_id,
                        body=interactive_payload["body"],
                        sender_type="agent",
                        channel="whatsapp",
                        ai_generated=True,
                        whatsapp_message_id=isent_id,
                        whatsapp_status="sent" if isent_id else "failed",
                    )
                    await _db.messages.insert_one(imsg_doc.model_dump())
            except Exception as _int_err:
                print(f"WhatsApp interactive message error: {_int_err}")
                # Fall back to plain text
                return reply or result.get("message") or None
            # Interactive was sent — caller should not send text again
            return None

        return reply or result.get("message") or None

    except json.JSONDecodeError:
        if raw and len(raw) < 1000:
            return raw
        return None
    except Exception as e:
        print(f"WhatsApp AI Agent error: {e}")
        return None
