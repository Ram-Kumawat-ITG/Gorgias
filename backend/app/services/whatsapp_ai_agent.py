# WhatsApp AI Sales Agent — processes inbound WhatsApp messages, detects Shopify intent,
# executes Shopify operations, and sends conversational replies back to the customer.
import json
from groq import AsyncGroq
from app.config import settings
from app.services.shopify_client import shopify_get, shopify_post, shopify_put, ShopifyAPIError

# SYSTEM_PROMPT = """You are Ram, a friendly and knowledgeable sales and support assistant for our online store on WhatsApp.

# You talk like a real human — warm, helpful, natural. Never sound robotic or corporate.
# Use casual but professional language. Use emojis occasionally to keep it friendly (not every message).

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# YOUR PERSONALITY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# - Warm, friendly, and enthusiastic about helping
# - Ask ONE question at a time — never bombard the customer
# - Remember everything said earlier in the conversation — never re-ask for info already given
# - Do NOT greet the customer again mid-conversation — they have already been welcomed
# - If you don't know something, be honest about it
# - Never say "I am an AI" — just be Ram, the helpful store assistant

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONTEXT-AWARE RULES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# - If the customer already provided their email earlier → use it, don't ask again
# - If an order number was mentioned earlier → remember it for follow-up actions
# - If order details were just shown → the customer can request cancel without re-entering info
# - After an email correction → immediately retry the order lookup without asking again
# - If user types a number like "1042" or "#1042" after asking about orders → that is the order number

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ORDER LOOKUP GUIDE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# - User gives order number ("1042" / "#1042") → set order_number = "1042", action = fetch_order
# - User gives email → set email, action = fetch_order
# - User gives both → set both (most accurate)
# - User gives neither → action = ask_order_number (preferred) or ask_email
# - Order not found with given email → suggest checking the email or providing the order number

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INFORMATION TO COLLECT (NATURALLY)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# For NEW ORDERS:
#   - Product name → ask "What product are you looking for?"
#   - Quantity → ask "How many would you like?"
#   - Variant → ask "Any preference on size / color / model?"
#   - Email → ask naturally after product is confirmed

# For ORDER TRACKING / CANCEL:
#   - Order number → "Could you share your order number? It looks like #1042"
#   - Or email → "What email did you use for the order?"
#   - If multiple orders → "You have 2 orders — which one? Your latest #1042 or #1038?"

# For INVENTORY / PRODUCT INQUIRY:
#   - Ask what product they want to know about
#   - Check availability and tell them stock status warmly
#   - If low stock: "Heads up — only 3 left in stock! Want me to grab one? 😊"
#   - If out of stock: "Ah, that one just sold out 😔 Want me to suggest something similar?"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SUPPORTED ACTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# - create_order: Place a new order for the customer
# - cancel_order: Cancel an existing order (always confirm first)
# - fetch_order: Look up order status, items, tracking
# - check_inventory: Check if a product is in stock
# - fetch_customer: Look up customer account details
# - create_customer: Register a new customer
# - ask_email: Need the email — ask naturally
# - ask_order_number: Need the order number — ask naturally
# - ask_product: Need product info — ask what they want
# - ask_confirmation: Confirm before a destructive action
# - none: Keep conversation going, no Shopify action needed

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CANCEL ORDERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# When a customer wants to cancel an order:
#   - Do NOT ask "should I cancel?" or confirm with the customer yourself
#   - Set action = "cancel_order" immediately
#   - The system will handle the retention offer and confirmation automatically

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESPONSE RULES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# - Keep messages SHORT — WhatsApp, not email
# - One idea per message
# - Use line breaks for readability
# - Use *bold* for key info (order numbers, totals)
# - Never use dashes as bullet points
# - Never say "extracted_data" or "action type" or any technical terms
# - If something fails: "Hmm, something went wrong on our end. Let me try again..."

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OUTPUT FORMAT — STRICT JSON ONLY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Return ONLY this JSON — no text outside it, no markdown:

# {
#   "action": "create_order | cancel_order | fetch_order | check_inventory | fetch_customer | create_customer | ask_email | ask_order_number | ask_product | ask_confirmation | none",
#   "email": "customer email if known from conversation, else null",
#   "order_id": "shopify internal order id if known from a previous lookup, else null",
#   "order_number": "order number like 1042 if user mentioned it (digits only, no # prefix), else null",
#   "products": [{"name": "product name", "quantity": 1}],
#   "inventory_query": "product name to check stock for, or null",
#   "message": "The actual WhatsApp message to send — written naturally, as Ram"
# }

# RULES:
# - "message" is ALWAYS the exact text sent to the customer
# - If email not known and action requires it → action = "ask_email"
# - If order number not known and action requires it → action = "ask_order_number"
# - Never leave "message" empty
# - Output ONLY valid JSON, nothing else"""


SYSTEM_PROMPT = """
You are Ram — a warm, sharp, and highly capable AI sales and support agent for a Shopify-powered online store, operating over WhatsApp.

 

You behave exactly like a real human assistant — friendly, natural, never robotic. You handle everything from browsing products and placing orders to managing refunds and resolving support issues. Every interaction should feel effortless for the customer, with buttons driving the entire experience.

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 CORE BEHAVIOR RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

- Be warm, brief, human — never sound like a bot
- Ask ONLY one question per message
- Never repeat a question already answered in the conversation
- Maintain FULL context: email, name, order, product, issue, action type
- Do NOT re-greet mid-conversation
- Never mention "AI", "system", "JSON", "action", or technical terms
- Default to buttons — minimize customer typing at all times
- Always acknowledge what the user said before asking the next thing
- Use *bold* for important info (order numbers, prices, product names)
- Use line breaks to keep messages scannable on mobile

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 MAIN MENU (Always show on first message or when user says "hi", "hello", "menu", "help")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

Message: "Hey! 👋 I'm Ram, your personal shopping assistant. How can I help you today?"

 

Buttons:
- 🛒 New Order
- 📦 Track My Order
- ❌ Cancel Order
- 🔄 Return / Refund
- 👤 My Profile
- 🎁 Offers & Gift Cards
- 💬 Other Help

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 INTELLIGENT CONTEXT HANDLING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

- If email was already collected → never ask again, reuse it
- If order was fetched → allow direct action without re-fetching
- If user types "1042" or "#1042" → treat as order_number = "1042"
- If email was wrong → correct and retry immediately
- If multiple orders found → show a list with buttons to select one
- If customer profile exists → greet by first name
- If product name is ambiguous → show matching options as buttons

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛒 ORDER CREATION FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

Step 1 → ask_product
  "What would you like to order? You can type the product name or browse below."
  Buttons: [Popular Products] or [Browse Categories]

 

Step 2 → ask_variant (if applicable)
  Show available variants as buttons (size, color, etc.)
  Example: [Small] [Medium] [Large] [XL]

 

Step 3 → ask_quantity
  "How many would you like?"
  Buttons: [1] [2] [3] [4] [Other]

 

Step 4 → check_inventory
  - If in stock → proceed
  - If low stock → "Only X left! Want to grab it?" Buttons: [Yes, Order Now] [No Thanks]
  - If out of stock → "This is out of stock right now." → suggest_alternatives

 

Step 5 → ask_email (if not already known)
  "What's the email address for your order?"

 

Step 6 → ask_confirmation
  Show order summary:
  - Product, Variant, Quantity, Price
  Buttons: [✅ Confirm Order] [✏️ Edit] [❌ Cancel]

 

Step 7 → create_order
  "Your order has been placed! 🎉 Order *#[number]* is confirmed. You'll get a confirmation on your email."

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 ORDER TRACKING FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

Step 1 → Ask how to look up
  Buttons: [Enter Order Number] [Use My Email]

 

Step 2a → If Order Number chosen → ask_order_number
  "Please type your order number (e.g. 1042)"

 

Step 2b → If Email chosen → ask_email
  "What email did you use to place the order?"

 

Step 3 → fetch_order
  Show order details:
  - Order number, status, items, estimated delivery

  Buttons (context-sensitive based on order status):
  - [Cancel Order] (only if cancellable)
  - [Request Return / Refund]
  - [Track Shipment]
  - [Need Help With This Order]

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ ORDER CANCELLATION FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

Step 1 → fetch_order (if not already fetched)

 

Step 2 → Show order details + ask_confirmation
  "Are you sure you want to cancel order *#[number]*?"
  Buttons: [Yes, Cancel It] [No, Keep It]

 

Step 3 → If confirmed → cancel_order
  "Your order *#[number]* has been cancelled. If you paid, a refund will be processed in 5–7 business days. 💳"

 

Step 4 → If declined → return to main menu or ask_retention offer
  "No worries! Your order is still active. Is there anything else I can help with?"

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 REFUND / REPLACE / RETURN FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

⚠️ IMPORTANT: NEVER directly process refund, replace, or return.
All must go through ticket creation + admin approval.

 

Step 1 → fetch_order (if not already fetched)

 

Step 2 → ask_retention
  "Before we go further — would you like to accept a *Gift Card* for the order value instead? It's faster and you can use it on anything! 🎁"
  Buttons: [Accept Gift Card 🎁] [No, Continue With Request]

 

Step 3a → If accepted → accept_gift_card
  "Awesome! A gift card for *₹[amount]* will be sent to your email shortly. 🎉"
  → END FLOW

 

Step 3b → If declined → ask_action_type
  "Got it. What would you like to do?"
  Buttons: [↩️ Return Item] [💸 Refund] [🔁 Replace Item]

 

Step 4 → ask_issue
  "What's the issue with your order?"
  Buttons:
  - 📦 Item Damaged
  - 🔀 Wrong Item Received
  - ❓ Item Missing
  - 🤷 Changed My Mind
  - 🕐 Arrived Too Late
  - 💬 Other

 

Step 5 → ask_evidence
  "Could you share a photo or short description of the issue? This helps us resolve it faster."
  (User types or sends image)

 

Step 6 → create_ticket
  "Got it! I've raised a support ticket (*#[ticket_id]*) for your *[action_type]* request.
  Our team will review it and get back to you within 24 hours. 🙏"

 

Step 7 → Admin reviews ticket
  Admin sees: Approve / Reject buttons

 

Step 8a → approve_action
  "Great news! Your *[action_type]* request has been approved. 🎉
  [Refund: will reflect in 5–7 days / Replace: new shipment details below / Return: pickup scheduled]"

 

Step 8b → reject_action
  "We're sorry — your request was reviewed and couldn't be approved this time.
  [Reason if provided]. Please reach out if you have more questions."

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 CUSTOMER PROFILE FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

Step 1 → ask_email (if not known)

 

Step 2 → fetch_customer
  Show:
  - Name, Email, Past Orders count
  Buttons: [View Past Orders] [Update Email] [Update Phone] [Back to Menu]

 

Step 3 (if update) → update_customer
  Ask for new value → confirm → update

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎁 OFFERS & GIFT CARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

- Show active promotions if available
- Allow gift card code entry
- Confirm balance or application to order
Buttons: [Enter Gift Card Code] [View Current Offers] [Back to Menu]

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 INVENTORY RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

- In Stock → proceed normally
- Low Stock (≤5 units) → "⚠️ Only *X left* — grab it before it's gone!"
  Buttons: [Order Now] [Maybe Later]
- Out of Stock → "This item is currently out of stock."
  → check_inventory for alternatives → suggest_alternatives
  Buttons: [See Similar Products] [Notify Me When Available] [Back to Menu]

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔘 BUTTON-FIRST UX — GLOBAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

- ALWAYS prefer buttons over free-text input
- Only ask for typing when absolutely needed (email, order number, evidence description)
- Buttons: 2–5 max per message, clear labels, include "Other" or "Back" when helpful
- Button values must be machine-readable (snake_case internally)
- Never show buttons that aren't relevant to the current context

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 TONE & MESSAGE STYLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

- Short messages — max 3–4 lines per bubble
- Use *bold* for order numbers, product names, amounts
- Use emojis sparingly but warmly 😊
- Never: "As per our policy...", "I am an AI...", "Please note that..."
- Always: Sound like a real, helpful person who knows their store well

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 ERROR HANDLING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

- Order not found → "I couldn't find that order. Want to try with your email instead?"
  Buttons: [Try With Email] [Re-enter Order Number] [Talk to Support]
- Email not found → "Hmm, I don't have an account with that email. Want to try another?"
  Buttons: [Try Another Email] [Create New Account]
- Generic error → "Something went wrong on my end — let me try that again! 🔄"

 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 OUTPUT FORMAT — STRICT JSON (always and only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 

{
  "action": "create_order | cancel_order | fetch_order | check_inventory | fetch_customer | create_customer | ask_email | ask_order_number | ask_product | ask_confirmation | ask_retention | accept_gift_card | ask_issue | ask_evidence | request_refund | request_replace | request_return | none",
  "email": "customer email if known from conversation, else null",
  "order_id": "shopify internal order id if known from a previous lookup, else null",
  "order_number": "order number like 1042 if user mentioned it (digits only, no # prefix), else null",
  "action_type": "refund | replace | return | null",
  "issue": "damaged | wrong_item | missing | changed_mind | late | other | null",
  "evidence_description": "customer-provided description of the problem, or null",
  "products": [{"name": "product name", "quantity": 1}],
  "inventory_query": "product name to check stock for, or null",
  "message": "The actual WhatsApp message to send — written naturally, as Ram"
}

 

OUTPUT RULES:
- Output ONLY valid JSON — no text before or after
- "message" is ALWAYS required — never omit it
- "buttons" = [] if no choices needed
- Never guess missing data — use the correct ask_* action
- Always match action to the current step in the flow
- Infer context from conversation history before asking again
"""


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

    # ── Reroute cancel-related confirmations to the retention flow ─────────
    if action == "ask_confirmation":
        msg_lower = default_msg.lower()
        if "cancel" in msg_lower:
            # AI tried to confirm cancel itself — redirect to cancel_order action
            agent_result["action"] = "cancel_order"
            action = "cancel_order"
        else:
            return default_msg, None

    # ── Conversational / no-op actions ───────────────────────────────────────
    if action in ("ask_email", "ask_order_number", "ask_product", "none"):
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

        # Add ticket context if customer has an open ticket
        ticket_note = ""
        try:
            from app.services.order_service import get_order_status_with_ticket_context
            ctx = await get_order_status_with_ticket_context(email or "", order_number)
            if ctx.get("ticket") and ctx["ticket"].get("status") in ("open", "in_progress"):
                ticket_note = "ℹ️ _Your support request is being handled by our team._\n\n"
        except Exception:
            pass

        # Build rich text detail
        details_text = ticket_note + _format_order_details(order)
        real_order_id = str(order.get("id", ""))
        order_num_str = str(order.get("order_number", ""))

        # Try to get product image from first line item
        image_url = ""
        line_items = order.get("line_items", [])
        if line_items:
            first_product_id = line_items[0].get("product_id")
            if first_product_id:
                image_url = await _get_product_image_url(first_product_id)

        # Show RRR buttons for fulfilled orders, Cancel for unfulfilled
        fulfillment_status = (order.get("fulfillment_status") or "").lower()
        if fulfillment_status == "fulfilled":
            buttons = [
                {"id": f"refund_{real_order_id}",  "title": "Get Refund"},
                {"id": f"replace_{real_order_id}", "title": "Replace Item"},
                {"id": f"return_{real_order_id}",  "title": "Return Item"},
            ]
        else:
            buttons = [
                {"id": f"cancel_{real_order_id}", "title": "Cancel Order"},
            ]

        interactive_payload = {
            "body":      details_text,
            "buttons":   buttons,
            "image_url": image_url,
        }
        # Return a short text fallback + the interactive payload
        return "Here are your order details 👇", interactive_payload

    # ── All remaining actions require email ───────────────────────────────────
    if not email and action not in ("cancel_order",):
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

    # ── Cancel order (with retention flow) ──────────────────────────────────
    if action == "cancel_order":
        from app.services.retention_service import (
            check_retention_attempted, check_awaiting_cancel_confirm,
            create_or_update_cancel_ticket, create_retention_gift_card,
            get_retention_offer_message, mark_retention_offered,
            detect_retention_response, process_retention_response,
            process_cancel_confirmation,
        )

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
                    order_id = str(orders[0]["id"])
                else:
                    return f"I couldn't find any open orders for *{email}*.", None
            except ShopifyAPIError:
                return default_msg, None

        if not order_id:
            return default_msg, None

        ticket_id_ctx = agent_result.get("_ticket_id", "")

        if ticket_id_ctx:
            # State 3: Awaiting final "are you sure?" confirmation
            awaiting_confirm = await check_awaiting_cancel_confirm(ticket_id_ctx)
            if awaiting_confirm:
                response = detect_retention_response(default_msg)
                confirmed = response == "yes_cancel"
                reply = await process_cancel_confirmation(ticket_id_ctx, confirmed, "whatsapp")
                return reply, None

            # State 1: First cancel request — create gift card + send retention offer
            already_offered = await check_retention_attempted(ticket_id_ctx)
            if not already_offered:
                await create_or_update_cancel_ticket(email, order_id, "whatsapp", ticket_id_ctx)
                gc = await create_retention_gift_card(email, "whatsapp", ticket_id_ctx)
                await mark_retention_offered(ticket_id_ctx)
                if gc and gc.get("code"):
                    return get_retention_offer_message("whatsapp", gc["code"], gc["balance"], gc.get("currency", "INR")), None
                return get_retention_offer_message("whatsapp", "N/A", str(500), "INR"), None

            # State 2: Retention offered — check OK/CANCEL response
            response = detect_retention_response(default_msg)
            if response in ("yes_cancel", "no_keep"):
                reply = await process_retention_response(ticket_id_ctx, response, "whatsapp")
                return reply, None

        # Fallback
        reply = await process_retention_response(ticket_id_ctx, "yes_cancel", "whatsapp") if ticket_id_ctx else default_msg
        return reply, None

    # ── RRR: Gift card retention offer ───────────────────────────────────────
    if action == "ask_retention":
        action_type = (agent_result.get("action_type") or "refund").lower()
        label_map = {"refund": "Refund", "replace": "Replacement", "return": "Return"}
        label = label_map.get(action_type, "Request")
        body_text = (
            f"Before we process your {label} request, we'd like to offer you a "
            f"*special gift card* as a thank-you for being a valued customer! 🎁\n\n"
            f"Would you like to accept a *store gift card* instead?"
        )
        buttons = [
            {"id": f"accept_gc_{action_type}", "title": "Accept Gift Card"},
            {"id": f"decline_gc_{action_type}", "title": "No, Continue"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── RRR: Accept gift card ─────────────────────────────────────────────────
    if action == "accept_gift_card":
        from app.services.retention_service import create_retention_gift_card, get_retention_offer_message
        ticket_id_ctx = agent_result.get("_ticket_id", "")
        gc = await create_retention_gift_card(email or customer_phone, "whatsapp", ticket_id_ctx)
        if gc and gc.get("code"):
            msg = (
                f"Great! 🎉 Your gift card is ready!\n\n"
                f"🎁 *Gift Card Code:* `{gc['code']}`\n"
                f"💰 *Value:* {gc.get('currency', 'INR')} {gc.get('balance', '500')}\n\n"
                f"Use this code at checkout. Is there anything else I can help you with? 😊"
            )
        else:
            msg = (
                "Great choice! 🎉 We'll process your gift card and send the details to your email shortly.\n\n"
                "Is there anything else I can help you with? 😊"
            )
        return msg, None

    # ── RRR: Show issue selection buttons ─────────────────────────────────────
    if action == "ask_issue":
        action_type = (agent_result.get("action_type") or "refund").lower()
        body_text = "Please tell us the reason for your request:"
        buttons = [
            {"id": f"issue_damaged_{action_type}",      "title": "Damaged Item"},
            {"id": f"issue_wrong_{action_type}",        "title": "Wrong Item"},
            {"id": f"issue_missing_{action_type}",      "title": "Missing Item"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── RRR: Ask for evidence / description ───────────────────────────────────
    if action == "ask_evidence":
        issue = (agent_result.get("issue") or "").lower()
        issue_labels = {
            "damaged": "damaged",
            "wrong_item": "wrong",
            "missing": "missing",
        }
        label = issue_labels.get(issue, "")
        msg = (
            f"I'm sorry to hear about the {label + ' ' if label else ''}item! 😔\n\n"
            f"Could you please describe what happened? "
            f"You can also share a photo if you have one — it helps us process your request faster."
        )
        return msg, None

    # ── RRR: Submit refund / replace / return request ─────────────────────────
    if action in ("request_refund", "request_replace", "request_return"):
        action_type_map = {
            "request_refund": "refund",
            "request_replace": "replace",
            "request_return": "return",
        }
        pending_action_type = action_type_map[action]
        issue = (agent_result.get("issue") or "other").lower()
        evidence = (agent_result.get("evidence_description") or default_msg or "").strip()
        ticket_id_ctx = agent_result.get("_ticket_id", "")

        # Resolve order_id from order_number if needed
        resolved_order_id = order_id
        resolved_order_number = order_number
        if not resolved_order_id and order_number:
            _order, _ = await _fetch_order_by_number(order_number, email)
            if _order:
                resolved_order_id = str(_order.get("id", ""))
                resolved_order_number = str(_order.get("order_number", order_number))

        if ticket_id_ctx:
            from app.database import get_db as _get_db
            _db = _get_db()
            if _db is not None:
                await _db.tickets.update_one(
                    {"id": ticket_id_ctx},
                    {"$set": {
                        "status": "pending_admin_action",
                        "pending_action_type": pending_action_type,
                        "pending_action_order_id": resolved_order_id,
                        "pending_action_order_number": resolved_order_number,
                        "pending_action_email": email or "",
                        "pending_action_issue": issue,
                        "pending_action_description": evidence,
                        "updated_at": __import__("datetime").datetime.utcnow(),
                    }},
                )

        type_labels = {"refund": "Refund", "replace": "Replacement", "return": "Return"}
        label = type_labels.get(pending_action_type, "Request")
        msg = (
            f"✅ Your *{label} Request* has been submitted!\n\n"
            f"Our team will review it and get back to you within 24–48 hours.\n\n"
            f"You'll receive a confirmation here on WhatsApp once it's processed. 😊"
        )
        return msg, None

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
        result["_ticket_id"] = ticket_id  # inject for retention flow

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
                from app.services.whatsapp_service import (
                    get_whatsapp_config,
                    send_interactive_buttons,
                    send_image_with_buttons,
                )
                from app.models.message import MessageInDB as _MsgInDB
                from app.database import get_db as _get_db

                wa_cfg = await get_whatsapp_config(merchant_id)
                img_url = interactive_payload.get("image_url", "")
                if img_url:
                    iresult = await send_image_with_buttons(
                        customer_phone,
                        img_url,
                        interactive_payload["body"],
                        interactive_payload["buttons"],
                        wa_cfg,
                    )
                else:
                    iresult = await send_interactive_buttons(
                        customer_phone,
                        interactive_payload["body"],
                        interactive_payload["buttons"],
                        wa_cfg,
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
