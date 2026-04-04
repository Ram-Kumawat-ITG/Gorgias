# WhatsApp AI Sales Agent — processes inbound WhatsApp messages, detects Shopify intent,
# executes Shopify operations, and sends conversational replies back to the customer.
import json
from app.config import settings
from app.services.shopify_client import shopify_get, shopify_post, shopify_put, ShopifyAPIError

# SYSTEM_PROMPT = """You are Ram, a friendly and knowledgeable sales and support assistant for our online store on WhatsApp.e

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
# - If order details were just shown → the customer can request cancel/refund/replace/return without re-entering info
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
# REFUND / REPLACE / RETURN FLOW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# When a FULFILLED order's "Get Refund", "Replace Item", or "Return Item" button is tapped:
#   → Set action = "ask_retention", action_type = "refund" | "replace" | "return"
#   → System will show a gift card retention offer automatically

# When customer clicks "Accept Gift Card":
#   → action = "accept_gift_card"

# When customer clicks "No, Continue" or "Decline" or refuses the gift card:
#   → action = "ask_issue"
#   → System will show issue selection buttons automatically

# When customer selects Damaged/Wrong/Missing issue:
#   → action = "ask_evidence", issue = "damaged" | "wrong_item" | "missing"
#   → Ask the customer to describe what happened (and mention they can share a photo)

# When customer selects Changed Mind/Late/Other issue OR after providing evidence:
#   → action = "request_refund" | "request_replace" | "request_return"
#   → Set issue and evidence_description fields
#   → System will create a pending approval ticket automatically

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
#   "action": "create_order | cancel_order | fetch_order | check_inventory | fetch_customer | create_customer | ask_email | ask_order_number | ask_product | ask_confirmation | ask_retention | accept_gift_card | ask_issue | ask_evidence | request_refund | request_replace | request_return | none",
#   "email": "customer email if known from conversation, else null",
#   "order_id": "shopify internal order id if known from a previous lookup, else null",
#   "order_number": "order number like 1042 if user mentioned it (digits only, no # prefix), else null",
#   "action_type": "refund | replace | return | null",
#   "issue": "damaged | wrong_item | missing | changed_mind | late | other | null",
#   "evidence_description": "customer-provided description of the problem, or null",
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


SYSTEM_PROMPT = """You are an AI-powered Customer Support Agent integrated with a Shopify store and a helpdesk ticketing system.

ALWAYS respond in English only. Be friendly, warm, empathetic, and professional. Never sound robotic.
Never say "I am an AI". Never use technical terms like "JSON", "action", or "system".
Use *bold* for order numbers, amounts, and product names. Use emojis sparingly.
Acknowledge the customer's frustration before diving into process.
Lead every message with what you CAN do — not what you can't.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 CORE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Ask only ONE question per message
- Never repeat info already provided in conversation
- Remember all context: email, order number, issue, action type
- Customers should NEVER need to type — use buttons for everything
- Only ask customer to TYPE: email address or order number
- NEVER directly process refund/return/replace/cancel — ALWAYS create a ticket for admin approval
- NEVER create duplicate tickets — if an active request exists for the same order, inform the customer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👋 GREETING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If user says Hi / Hello / Hey / menu / help → action = "show_menu"
Message: "Hey! I'm here to help you with your order 😊 What would you like to do today?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 ORDER TRACKING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- User gives order number → action = "fetch_order", set order_number
- User gives email → action = "fetch_order", set email
- Neither given → action = "ask_order_number"
- "1042" or "#1042" typed after being asked → order_number = "1042"

After fetch_order, show buttons based on fulfillment:
- Unfulfilled/not shipped → Cancel Order button
- Fulfilled/delivered → Refund / Replace / Return buttons

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛒 ORDER CREATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 1 → ask_product: "What would you like to order?"
Step 2 → ask_quantity: "How many would you like?"
Step 3 → ask_email (if not known): "What email should we use for the order?"
Step 4 → check_inventory → create_order

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ CANCEL ORDER FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 1 → offer_gift_card (ALWAYS offer gift card first)
  Message: "We understand you'd like to cancel your order. Before we proceed, we'd love to offer you a *Gift Card* instead — so you don't lose value 💳 Would you like to accept it?"
  (System shows Accept Gift Card / Reject Gift Card buttons)

Step 2a → If ACCEPTED → accept_gift_card
  "Great choice! 🎉 Your order continues and your gift card will be processed shortly."
  → END FLOW

Step 2b → If REJECTED → ask_cancel_confirm
  Message: "Are you sure you want to cancel your order?"
  (System shows Yes Cancel / No Keep buttons)

Step 3a → If YES → submit_ticket with action_type = "cancel"
  Message: "Your cancellation request has been submitted. Our team will review and process it shortly."

Step 3b → If NO → none
  Message: "No worries 😊 Your order will continue as planned. Is there anything else I can help with?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 REFUND / 🔁 REPLACE / 📦 RETURN FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEVER process directly — always ticket + admin approval.
Image/video proof is MANDATORY for ALL these requests. Do NOT skip this step.

Step 1 → ask_reason with correct action_type
  Message: "Could you please tell us why you'd like a [refund/replacement/return]?"
  (System shows reason buttons: Wrong Product, Damaged, Quality Issue, Delayed, Other)

Step 2 → ask_evidence (MANDATORY — block until media received)
  Message: "To process your request, we'll need visual proof of the issue. Please upload clear photos 📸 or a short video 🎥 of the product."
  If customer responds with text only (no media) → remind them:
  "We still need photos or video of the product before we can submit your request. Please upload when you're ready."

Step 3 → ask_confirmation (show full summary before submission)
  Message: "Here's a summary of your request:

📋 *Request Type:* [Refund / Return / Replacement]
📦 *Order:* #[Order Number]
❗ *Reason:* [Selected Reason]
📸 *Proof:* Received

Shall I go ahead and submit this for review?"
  (System shows Yes Submit / No buttons)

Step 4 → submit_ticket
  Message: "✅ Your *[Type] Request* has been submitted and is awaiting admin approval.

We'll update you right here on WhatsApp once it's been reviewed. Our team typically responds within 24-48 hours. 🙏"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 ERRORS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Order not found → "We couldn't find that order. Please double-check your Order ID or share the email linked to your account."
- Email not found → "We couldn't find an account with that email. Would you like to try a different one?"
- Media upload fail → "Your file couldn't be uploaded. Please try again with a different format (JPG, PNG, MP4)."
- Duplicate request → "You already have an active request for this order. Our team is reviewing it and will update you soon."
- Generic error → "Something went wrong while processing your request. Please try again or contact support."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 OUTPUT FORMAT — STRICT JSON ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Output ONLY valid JSON. No text before or after. No markdown fences.

{
  "action": "show_menu | fetch_order | create_order | check_inventory | fetch_customer | create_customer | ask_email | ask_order_number | ask_product | browse_products | ask_quantity | ask_order_confirm | offer_gift_card | accept_gift_card | ask_cancel_confirm | ask_reason | ask_evidence | ask_confirmation | submit_ticket | create_ticket | cancel_order | none",
  "email": "string or null",
  "order_id": "string or null",
  "order_number": "digits only, no # prefix, or null",
  "action_type": "cancel | refund | replace | return | null",
  "issue": "wrong_product | damaged | quality | delayed | wrong_size | missing | changed_mind | other | null",
  "evidence_description": "customer description of problem or null",
  "products": [{"name": "string", "quantity": 1}],
  "inventory_query": "product name or null",
  "message": "ALWAYS REQUIRED — the exact WhatsApp message to send to the customer"
}

 

STRICT RULES:
- "message" is ALWAYS required and never empty
- Do NOT include buttons in JSON — system handles all buttons automatically
- Use ask_email / ask_order_number when required info is missing
- Use submit_ticket to finalize any support request
- Infer all context from conversation history — never re-ask for info already provided
- NEVER skip ask_evidence for refund/replace/return — proof is MANDATORY
- NEVER create duplicate tickets — check conversation for existing active requests"""


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


async def _browse_products(limit: int = 10) -> list[dict]:
    """Fetch published products from Shopify for the browse catalog."""
    try:
        result = await shopify_get(
            "/products.json",
            params={"status": "active", "limit": limit, "fields": "id,title,variants,images"},
        )
        products = result.get("products", [])
        out = []
        for p in products:
            variants = p.get("variants", [])
            first_variant = variants[0] if variants else {}
            price = first_variant.get("price", "0.00")
            stock = int(first_variant.get("inventory_quantity") or 0)
            managed = first_variant.get("inventory_management") == "shopify"
            images = p.get("images", [])
            out.append({
                "id": str(p.get("id", "")),
                "title": p.get("title", ""),
                "price": price,
                "currency": "INR",
                "variant_id": str(first_variant.get("id", "")),
                "in_stock": (not managed) or stock > 0,
                "stock": stock if managed else None,
                "image_url": images[0].get("src", "") if images else "",
            })
        return out
    except ShopifyAPIError:
        return []


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

    # ── Show main menu with list (5 options) ─────────────────────────────────
    if action == "show_menu":
        body_text = default_msg or "Hey! I'm here to help you with your order 😊 What would you like to do today?"
        sections = [{
            "title": "How can I help?",
            "rows": [
                {"id": "menu_new_order", "title": "Create Order",    "description": "Place a new order"},
                {"id": "menu_track",     "title": "Track My Order", "description": "Check order status & tracking"},
                {"id": "menu_cancel",    "title": "Cancel Order",   "description": "Cancel an existing order"},
                {"id": "menu_refund",    "title": "Refund Order",   "description": "Request a refund"},
                {"id": "menu_replace",   "title": "Replace Order",  "description": "Request a replacement"},
                {"id": "menu_return",    "title": "Return Order",   "description": "Return a product"},
                {"id": "menu_support",   "title": "Talk to Support","description": "Speak with our team"},
            ],
        }]
        return body_text, {"body": body_text, "list_sections": sections, "button_label": "Choose Option"}

    # ── ask_order_number — lookup options ────────────────────────────────────
    if action == "ask_order_number":
        body_text = default_msg or "How would you like to look up your order?"
        buttons = [
            {"id": "lookup_order_number", "title": "Enter Order Number"},
            {"id": "lookup_email",        "title": "Use My Email"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── ask_product — browse or type ─────────────────────────────────────────
    if action == "ask_product":
        body_text = default_msg or "What would you like to order? 🛍️"
        buttons = [
            {"id": "browse_products", "title": "Browse Products"},
            {"id": "type_product",    "title": "I'll Type the Name"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── browse_products — fetch catalog and show as list ────────────────────
    if action == "browse_products":
        products = await _browse_products(10)
        if not products:
            return "Sorry, I couldn't load our product catalog right now. Could you type the product name instead? 🙏", None

        rows = []
        for p in products:
            stock_tag = "In Stock" if p["in_stock"] else "Out of Stock"
            desc = f"{p['currency']} {p['price']} · {stock_tag}"
            rows.append({
                "id": f"select_product_{p['id']}",
                "title": p["title"][:24],
                "description": desc[:72],
            })

        body_text = "Here are our products! Tap one to order 🛍️"
        sections = [{"title": "Our Products", "rows": rows}]
        return body_text, {"body": body_text, "list_sections": sections, "button_label": "View Products"}

    # ── ask_order_confirm — show order summary before placing ────────────────
    if action == "ask_order_confirm":
        product_name = (agent_result.get("products") or [{}])[0].get("name", "your item")
        qty = (agent_result.get("products") or [{}])[0].get("quantity", 1)
        body_text = (
            default_msg or
            f"Here's your order summary:\n\n"
            f"🛍 *Product:* {product_name}\n"
            f"📦 *Quantity:* {qty}\n\n"
            f"Would you like to confirm and place this order?"
        )
        buttons = [
            {"id": "confirm_order_yes", "title": "Confirm Order"},
            {"id": "confirm_order_no",  "title": "Cancel"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── ask_quantity — number buttons ────────────────────────────────────────
    if action == "ask_quantity":
        body_text = default_msg or "How many would you like?"
        buttons = [
            {"id": "qty_1", "title": "1"},
            {"id": "qty_2", "title": "2"},
            {"id": "qty_3", "title": "3"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── ask_retention (gift card offer for RRR path) ──────────────────────────
    if action == "ask_retention":
        action_type = (agent_result.get("action_type") or "refund").lower()
        type_label = {"refund": "refund", "replace": "replacement", "return": "return"}.get(action_type, "request")

        # Try to fetch order details for a richer gift card offer
        gc_order = None
        gc_order_id = order_id
        if not gc_order_id and order_number:
            gc_order, _ = await _fetch_order_by_number(order_number, email)
            if gc_order:
                gc_order_id = str(gc_order.get("id", ""))
        elif gc_order_id:
            gc_order = await _get_order(gc_order_id)

        if gc_order:
            gc_total = gc_order.get("total_price", "0.00")
            gc_currency = gc_order.get("currency", "INR")
            gc_order_num = gc_order.get("order_number", order_number or "")
            items = gc_order.get("line_items", [])
            items_text = "\n".join(
                f"  • *{li.get('title', '')}* × {li.get('quantity', 1)}"
                for li in items[:5]
            ) or "  • Your ordered items"

            body_text = (
                f"Before we proceed with your {type_label} request — we'd love to offer you a "
                f"*Gift Card* instead! 💳\n\n"
                f"📦 *Order:* #{gc_order_num}\n"
                f"🛍 *Items:*\n{items_text}\n\n"
                f"🎁 *Gift Card Details:*\n"
                f"  💰 *Value:* {gc_currency} {gc_total}\n"
                f"  ✅ Use on *any product* in our store\n"
                f"  ⏱ *No expiry* — use it anytime\n"
                f"  📧 Sent to your email instantly\n\n"
                f"Would you like to accept the Gift Card?"
            )
        else:
            body_text = (
                f"Before we proceed with your {type_label} request — we'd love to offer you a "
                f"*Gift Card* instead! 💳\n\n"
                f"🎁 *Gift Card Benefits:*\n"
                f"  💰 *Full order value* credited\n"
                f"  ✅ Use on *any product* in our store\n"
                f"  ⏱ *No expiry* — use it anytime\n"
                f"  📧 Sent to your email instantly\n\n"
                f"Would you like to accept the Gift Card?"
            )

        buttons = [
            {"id": f"accept_gc_{action_type}",  "title": "Accept Gift Card"},
            {"id": f"decline_gc_{action_type}", "title": "No, Continue"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── plain conversational responses ───────────────────────────────────────
    if action in ("ask_email", "ask_variant", "ask_proof", "none"):
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

        # Priority 3: email given but no order number → fetch ALL orders and let customer pick
        if not order and email:
            try:
                result = await shopify_get(
                    "/orders.json",
                    params={"email": email, "limit": 10, "status": "any"},
                )
                all_orders = result.get("orders", [])

                if not all_orders:
                    return f"I couldn't find any orders for *{email}*. Is that the right email? 🤔", None

                # Single order → show it directly
                if len(all_orders) == 1:
                    order = all_orders[0]
                else:
                    # Multiple orders → show a list for customer to pick
                    rows = []
                    for o in all_orders[:10]:
                        o_num = str(o.get("order_number", ""))
                        o_id = str(o.get("id", ""))
                        o_total = o.get("total_price", "0.00")
                        o_currency = o.get("currency", "INR")
                        o_status = (o.get("fulfillment_status") or "unfulfilled").replace("_", " ").title()
                        o_date = ""
                        if o.get("created_at"):
                            try:
                                from datetime import datetime as _dt
                                _parsed = _dt.fromisoformat(o["created_at"].replace("Z", "+00:00"))
                                o_date = _parsed.strftime("%d %b %Y")
                            except Exception:
                                o_date = ""

                        # Build items summary (first 2 items)
                        items = o.get("line_items", [])
                        item_names = ", ".join(li.get("title", "")[:20] for li in items[:2])
                        if len(items) > 2:
                            item_names += f" +{len(items) - 2} more"

                        desc = f"{o_currency} {o_total} · {o_status}"
                        if o_date:
                            desc = f"{o_date} · {desc}"

                        rows.append({
                            "id": f"pick_order_{o_id}",
                            "title": f"Order #{o_num}"[:24],
                            "description": desc[:72],
                        })

                    body_text = (
                        f"I found *{len(all_orders)} orders* for *{email}* 📦\n\n"
                        f"Which order would you like to check?"
                    )
                    sections = [{"title": "Your Orders", "rows": rows}]
                    return body_text, {"body": body_text, "list_sections": sections, "button_label": "Select Order"}

            except ShopifyAPIError:
                err = default_msg

        if not order:
            return err or default_msg, None

        # ── Single order detail view ─────────────────────────────────────────
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

        # Tracking info (prominent for track-my-order flow)
        fulfillments = order.get("fulfillments") or []
        tracking_card = ""
        if fulfillments:
            last_ff = fulfillments[-1]
            t_num = last_ff.get("tracking_number")
            t_company = last_ff.get("tracking_company", "")
            t_url = last_ff.get("tracking_url", "")
            t_status = (last_ff.get("shipment_status") or last_ff.get("status") or "").replace("_", " ").title()
            if t_num:
                tracking_card = (
                    f"\n\n📍 *Shipment Tracking:*\n"
                    f"  🚚 Carrier: *{t_company or 'Shipping Partner'}*\n"
                    f"  📦 Tracking #: *{t_num}*\n"
                )
                if t_status:
                    tracking_card += f"  📋 Status: *{t_status}*\n"
                if t_url:
                    tracking_card += f"  🔗 Track here: {t_url}\n"

        if tracking_card:
            details_text += tracking_card

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

    # ── Cancel: gift card offer FIRST (new flow) ─────────────────────────────
    if action == "offer_gift_card":
        # Try to fetch order details for a richer gift card offer
        gc_order = None
        gc_order_id = order_id
        if not gc_order_id and order_number:
            gc_order, _ = await _fetch_order_by_number(order_number, email)
            if gc_order:
                gc_order_id = str(gc_order.get("id", ""))
        elif gc_order_id:
            gc_order = await _get_order(gc_order_id)

        if gc_order:
            gc_total = gc_order.get("total_price", "0.00")
            gc_currency = gc_order.get("currency", "INR")
            gc_order_num = gc_order.get("order_number", order_number or "")
            items = gc_order.get("line_items", [])
            items_text = "\n".join(
                f"  • *{li.get('title', '')}* × {li.get('quantity', 1)}"
                for li in items[:5]
            ) or "  • Your ordered items"

            body_text = (
                f"We understand you'd like to cancel your order.\n\n"
                f"Before we proceed, we'd love to offer you a *Gift Card* instead 💳\n\n"
                f"📦 *Order:* #{gc_order_num}\n"
                f"🛍 *Items:*\n{items_text}\n\n"
                f"🎁 *Gift Card Details:*\n"
                f"  💰 *Value:* {gc_currency} {gc_total}\n"
                f"  ✅ Use on *any product* in our store\n"
                f"  ⏱ *No expiry* — use it anytime\n"
                f"  📧 Sent to your email instantly\n\n"
                f"Would you like to accept the Gift Card?"
            )
        else:
            body_text = (
                f"We understand you'd like to cancel your order.\n\n"
                f"Before we proceed, we'd love to offer you a *Gift Card* instead 💳\n\n"
                f"🎁 *Gift Card Benefits:*\n"
                f"  💰 *Full order value* credited\n"
                f"  ✅ Use on *any product* in our store\n"
                f"  ⏱ *No expiry* — use it anytime\n"
                f"  📧 Sent to your email instantly\n\n"
                f"Would you like to accept the Gift Card?"
            )

        buttons = [
            {"id": "accept_gc_cancel",  "title": "Accept Gift Card"},
            {"id": "decline_gc_cancel", "title": "Reject Gift Card"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── Cancel: final Yes/No after gift card rejected ─────────────────────────
    if action == "ask_cancel_confirm":
        body_text = default_msg or "Are you sure you want to cancel your order?"
        buttons = [
            {"id": "confirm_cancel_yes", "title": "Yes, Cancel My Order"},
            {"id": "confirm_cancel_no",  "title": "No, Keep My Order"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── Accept gift card (cancel or RRR) ──────────────────────────────────────
    if action == "accept_gift_card":
        try:
            from app.services.retention_service import create_retention_gift_card
            ticket_id_ctx = agent_result.get("_ticket_id", "")
            gc = await create_retention_gift_card(email or customer_phone, "whatsapp", ticket_id_ctx)
            if gc and gc.get("code"):
                msg = (
                    f"Great choice! 🎉 Your gift card is ready.\n\n"
                    f"🎁 *Gift Card Code:* {gc['code']}\n"
                    f"💰 *Value:* {gc.get('currency', 'INR')} {gc.get('balance', '500')}\n\n"
                    f"Your order will continue as usual and the gift card will be sent to your email shortly."
                )
            else:
                msg = (
                    "Great choice! 🎉 Your gift card will be processed and sent to your email shortly.\n\n"
                    "Your order continues as planned. Is there anything else I can help with?"
                )
        except Exception:
            msg = (
                "Great! 🎉 Your gift card will be processed and sent to your email shortly.\n\n"
                "Is there anything else I can help with?"
            )
        return msg, None

    # ── Ask reason — list message with all reasons per action type ────────────
    if action in ("ask_reason", "ask_issue"):
        action_type = (agent_result.get("action_type") or "refund").lower()
        type_label = {"refund": "refund", "replace": "replacement", "return": "return", "cancel": "cancellation"}.get(action_type, "request")
        body_text = default_msg or f"Could you please tell us why you'd like a {type_label}?"
        if action_type == "cancel":
            rows = [
                {"id": f"reason_changed_mind_{action_type}", "title": "Changed My Mind",  "description": "I no longer need this item"},
                {"id": f"reason_delayed_{action_type}",      "title": "Order Delayed",    "description": "Taking too long to arrive"},
                {"id": f"reason_other_{action_type}",        "title": "Other Reason",     "description": "Something else"},
            ]
        elif action_type == "replace":
            rows = [
                {"id": f"reason_wrong_size_{action_type}",   "title": "Wrong Size",       "description": "Size does not fit"},
                {"id": f"reason_damaged_{action_type}",      "title": "Damaged Product",  "description": "Item arrived damaged"},
                {"id": f"reason_wrong_{action_type}",        "title": "Wrong Item",       "description": "Received wrong item"},
                {"id": f"reason_other_{action_type}",        "title": "Other Reason",     "description": "Something else"},
            ]
        else:
            # refund or return
            rows = [
                {"id": f"reason_wrong_{action_type}",        "title": "Wrong Product",    "description": "Received wrong item"},
                {"id": f"reason_damaged_{action_type}",      "title": "Product Damaged",  "description": "Item arrived damaged"},
                {"id": f"reason_quality_{action_type}",      "title": "Quality Issue",    "description": "Not as expected"},
                {"id": f"reason_delayed_{action_type}",      "title": "Order Delayed",    "description": "Package arrived late"},
                {"id": f"reason_other_{action_type}",        "title": "Other Reason",     "description": "Something else"},
            ]
        sections = [{"title": "Select a Reason", "rows": rows}]
        return body_text, {"body": body_text, "list_sections": sections, "button_label": "Choose Reason"}

    # ── Ask for evidence / proof (mandatory for RRR) ──────────────────────────
    if action == "ask_evidence":
        msg = (
            "Please upload a clear image 📸 or video 🎥 of the product.\n\n"
            "This helps us verify your request and process it as quickly as possible."
        )
        return msg, None

    # ── Ask confirmation before submitting ticket ─────────────────────────────
    if action == "ask_confirmation":
        action_type = (agent_result.get("action_type") or "request").lower()
        type_label = {"refund": "refund", "replace": "replacement", "return": "return", "cancel": "cancellation"}.get(action_type, "request")
        body_text = default_msg or f"Would you like to proceed with your {type_label} request?"
        buttons = [
            {"id": f"confirm_submit_{action_type}", "title": "Yes, Submit Request"},
            {"id": "confirm_submit_no",             "title": "No"},
        ]
        return body_text, {"body": body_text, "buttons": buttons, "image_url": ""}

    # ── Submit ticket for admin approval (submit_ticket / create_ticket) ─────
    if action in ("submit_ticket", "create_ticket"):
        action_type = (agent_result.get("action_type") or "general").lower()
        issue = (agent_result.get("issue") or "other").lower()
        evidence = (agent_result.get("evidence_description") or "").strip()
        ticket_id_ctx = agent_result.get("_ticket_id", "")

        resolved_order_id = order_id
        resolved_order_number = order_number
        if not resolved_order_id and order_number:
            _order, _ = await _fetch_order_by_number(order_number, email)
            if _order:
                resolved_order_id = str(_order.get("id", ""))
                resolved_order_number = str(_order.get("order_number", order_number))

        if ticket_id_ctx:
            from app.database import get_db as _get_db
            import datetime as _dt
            _db = _get_db()
            if _db is not None:
                # Collect proof images/videos from the conversation thread
                _proof_images = []
                _proof_videos = []
                _media_msgs = _db.messages.find(
                    {"ticket_id": ticket_id_ctx, "sender_type": "customer"},
                    sort=[("created_at", 1)],
                )
                async for _m in _media_msgs:
                    _mid = _m.get("whatsapp_media_id") or ""
                    _murl = _m.get("whatsapp_media_url") or ""
                    _mtype = (_m.get("whatsapp_media_type") or "").lower()
                    _ref = _mid or _murl
                    if not _ref:
                        continue
                    if _mtype in ("image", "image/jpeg", "image/png", "image/webp"):
                        _proof_images.append(_ref)
                    elif _mtype in ("video", "video/mp4", "video/3gpp"):
                        _proof_videos.append(_ref)

                await _db.tickets.update_one(
                    {"id": ticket_id_ctx},
                    {"$set": {
                        "status": "pending_admin_action",
                        "pending_action_type": action_type,
                        "pending_action_order_id": resolved_order_id,
                        "pending_action_order_number": resolved_order_number,
                        "pending_action_email": email or "",
                        "pending_action_issue": issue,
                        "pending_action_description": evidence,
                        "pending_action_images": _proof_images,
                        "pending_action_videos": _proof_videos,
                        "updated_at": _dt.datetime.utcnow(),
                    }},
                )

        type_labels = {
            "refund": "Refund", "replace": "Replacement",
            "return": "Return", "cancel": "Cancellation", "general": "Support",
        }
        label = type_labels.get(action_type, "Support")
        msg = (
            f"✅ Your *{label} Request* has been submitted successfully!\n\n"
            f"Our team will review it and get back to you within 24–48 hours.\n\n"
            f"You'll receive an update here on WhatsApp once it's processed. 🙏"
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
            import datetime as _dt
            _db = _get_db()
            if _db is not None:
                # Collect proof images/videos from the conversation thread
                _proof_images = []
                _proof_videos = []
                _media_msgs = _db.messages.find(
                    {"ticket_id": ticket_id_ctx, "sender_type": "customer"},
                    sort=[("created_at", 1)],
                )
                async for _m in _media_msgs:
                    _mid = _m.get("whatsapp_media_id") or ""
                    _murl = _m.get("whatsapp_media_url") or ""
                    _mtype = (_m.get("whatsapp_media_type") or "").lower()
                    _ref = _mid or _murl
                    if not _ref:
                        continue
                    if _mtype in ("image", "image/jpeg", "image/png", "image/webp"):
                        _proof_images.append(_ref)
                    elif _mtype in ("video", "video/mp4", "video/3gpp"):
                        _proof_videos.append(_ref)

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
                        "pending_action_images": _proof_images,
                        "pending_action_videos": _proof_videos,
                        "updated_at": _dt.datetime.utcnow(),
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
    # Check that at least one LLM provider is configured
    if not settings.groq_api_key and not settings.openai_api_key:
        print("WhatsApp AI Agent: No LLM API key configured (GROQ_API_KEY or OPENAI_API_KEY) — chatbot disabled")
        return None

    history = await _get_conversation_history(ticket_id)

    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    prev_role = "system"
    for msg in history:
        role = "user" if msg.get("sender_type") == "customer" else "assistant"
        body = (msg.get("body") or "").strip()
        if not body:
            continue

        # Include the action context note if it was saved with the message
        # This tells the LLM what action was taken and prevents repetition
        action_ctx = (msg.get("ai_action_context") or "").strip()
        if role == "assistant" and action_ctx:
            body = f"[SYSTEM NOTE — previous action taken: {action_ctx}]\n{body}"

        # Merge consecutive messages from the same role (LLM APIs require alternating)
        if role == prev_role and chat_messages:
            chat_messages[-1]["content"] += f"\n\n{body}"
        else:
            chat_messages.append({"role": role, "content": body})
            prev_role = role

    # Guard: ensure conversation ends on a user turn
    if not chat_messages or chat_messages[-1].get("role") != "user":
        if prev_role == "user" and chat_messages:
            chat_messages[-1]["content"] += f"\n\n{current_message}"
        else:
            chat_messages.append({"role": "user", "content": current_message})

    try:
        from app.services.llm_client import chat_complete
        raw = await chat_complete(
            messages=chat_messages,
            max_tokens=600,
            temperature=0.3,
            json_mode=True,
        )

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rstrip("`").strip()

        result = json.loads(raw)
        result["_ticket_id"] = ticket_id  # inject for retention flow

        reply, interactive_payload = await _execute_action(result, customer_name, customer_phone)

        # Build action context string so the LLM remembers what it did next turn
        _action = result.get("action", "none")
        _atype  = result.get("action_type") or ""
        _issue  = result.get("issue") or ""
        _ctx_parts = [f"action={_action}"]
        if _atype:
            _ctx_parts.append(f"action_type={_atype}")
        if _issue:
            _ctx_parts.append(f"issue={_issue}")
        _action_context = ", ".join(_ctx_parts)

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
                list_sections = interactive_payload.get("list_sections")
                if list_sections:
                    from app.services.whatsapp_service import send_list_message
                    iresult = await send_list_message(
                        customer_phone,
                        interactive_payload["body"],
                        interactive_payload.get("button_label", "View Options"),
                        list_sections,
                        wa_cfg,
                    )
                elif img_url:
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
                # Persist the interactive message + action context to the ticket thread
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
                    _doc = imsg_doc.model_dump()
                    _doc["ai_action_context"] = _action_context
                    await _db.messages.insert_one(_doc)
            except Exception as _int_err:
                print(f"WhatsApp interactive message error: {_int_err}")
                # Fall back to plain text
                _text = reply or result.get("message") or None
                return {"reply": _text, "action_context": _action_context} if _text else None
            # Interactive was sent — caller should not send text again
            return None

        _text = reply or result.get("message") or None
        return {"reply": _text, "action_context": _action_context} if _text else None

    except json.JSONDecodeError:
        if raw and len(raw) < 1000:
            return {"reply": raw, "action_context": ""}
        return None
    except Exception as e:
        print(f"WhatsApp AI Agent error: {e}")
        return None
