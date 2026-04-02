# Shared order service — channel-agnostic order lookup, cancel, and formatting.
# Used by WhatsApp, Instagram, and Email AI agents.
from app.services.shopify_client import shopify_get, shopify_post, ShopifyAPIError
from app.database import get_db


async def lookup_order_by_number(order_number: str, customer_email: str = "") -> tuple[dict | None, str]:
    """Look up a Shopify order by order number (e.g. '1042').
    Optionally cross-validates against customer email.
    Returns (order_dict, error_message). On success error_message is ""."""
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
            return None, f"I couldn't find Order #{clean_number}. Could you double-check the number?"

        order = orders[0]

        if customer_email:
            order_email = (order.get("email") or order.get("contact_email") or "").lower()
            if order_email and customer_email.lower() not in order_email and order_email not in customer_email.lower():
                return None, (
                    f"I found Order #{clean_number}, but it doesn't seem to match {customer_email}. "
                    f"Could you double-check your email or the order number?"
                )

        return order, ""
    except ShopifyAPIError:
        return None, "I had trouble looking that up. Could you try again in a moment?"


async def lookup_order_by_email(email: str, limit: int = 1) -> list:
    """Fetch the most recent Shopify orders for a customer email."""
    try:
        result = await shopify_get(
            "/orders.json",
            params={"email": email, "limit": limit, "status": "any"},
        )
        return result.get("orders", [])
    except ShopifyAPIError:
        return []


async def lookup_order_by_id(order_id: str) -> dict | None:
    """Fetch a Shopify order by internal numeric ID."""
    try:
        result = await shopify_get(f"/orders/{order_id}.json")
        return result.get("order")
    except ShopifyAPIError:
        return None


async def cancel_order(order_id: str) -> bool:
    """Cancel a Shopify order. Returns True on success."""
    try:
        await shopify_post(f"/orders/{order_id}/cancel.json", {})
        return True
    except ShopifyAPIError:
        return False


def format_order_details_text(order: dict) -> str:
    """Format order details as plain text (for Instagram/Email)."""
    order_num = order.get("order_number", "")
    currency = order.get("currency", "")
    line_items = order.get("line_items", [])

    items_lines = []
    for li in line_items:
        title = li.get("title", "")
        variant = li.get("variant_title") or ""
        qty = li.get("quantity", 1)
        price = float(li.get("price", 0))
        subtotal = price * qty
        line = f"- {title}"
        if variant and variant.lower() != "default title":
            line += f" ({variant})"
        line += f" x {qty} — {currency} {subtotal:.2f}"
        items_lines.append(line)

    items_text = "\n".join(items_lines) or "N/A"
    payment = (order.get("financial_status") or "pending").replace("_", " ").title()
    fulfillment = (order.get("fulfillment_status") or "not shipped").replace("_", " ").title()
    total = order.get("total_price", "0.00")

    fulfillments = order.get("fulfillments") or []
    tracking_line = ""
    if fulfillments:
        last_ff = fulfillments[-1]
        tracking_num = last_ff.get("tracking_number")
        tracking_url = last_ff.get("tracking_url")
        if tracking_num:
            tracking_line = f"\nTracking: {tracking_num}"
            if tracking_url:
                tracking_line += f"\nTrack here: {tracking_url}"

    return (
        f"Order #{order_num}\n\n"
        f"Items:\n{items_text}\n\n"
        f"Payment: {payment}\n"
        f"Shipping: {fulfillment}"
        f"{tracking_line}\n"
        f"Total: {currency} {total}"
    )


def format_order_details_whatsapp(order: dict) -> str:
    """Format order details with WhatsApp markdown + emojis."""
    order_num = order.get("order_number", "")
    currency = order.get("currency", "")
    line_items = order.get("line_items", [])

    items_lines = []
    for li in line_items:
        title = li.get("title", "")
        variant = li.get("variant_title") or ""
        qty = li.get("quantity", 1)
        price = float(li.get("price", 0))
        subtotal = price * qty
        line = f"• *{title}*"
        if variant and variant.lower() != "default title":
            line += f" ({variant})"
        line += f" × {qty}  —  {currency} {subtotal:.2f}"
        items_lines.append(line)

    items_text = "\n".join(items_lines) or "N/A"
    payment = (order.get("financial_status") or "pending").replace("_", " ").title()
    fulfillment = (order.get("fulfillment_status") or "not shipped").replace("_", " ").title()
    total = order.get("total_price", "0.00")

    fulfillments = order.get("fulfillments") or []
    tracking_line = ""
    if fulfillments:
        last_ff = fulfillments[-1]
        tracking_num = last_ff.get("tracking_number")
        tracking_url = last_ff.get("tracking_url")
        if tracking_num:
            tracking_line = f"\n📍 Tracking: *{tracking_num}*"
            if tracking_url:
                tracking_line += f"\n🔗 {tracking_url}"

    return (
        f"📦 Order *#{order_num}*\n\n"
        f"🛍 *Items:*\n{items_text}\n\n"
        f"💳 Payment: *{payment}*\n"
        f"🚚 Shipping: *{fulfillment}*"
        f"{tracking_line}\n"
        f"💰 Total: *{currency} {total}*"
    )


async def get_order_status_with_ticket_context(customer_email: str, order_number: str = None) -> dict:
    """Get order status combined with ticket context.
    Returns dict with keys: ticket, order, message."""
    db = get_db()

    # Find existing open/pending ticket for this customer
    ticket = await db.tickets.find_one({
        "customer_email": customer_email,
        "status": {"$in": ["open", "pending", "in_progress"]},
    })

    # Get order data
    order = None
    if order_number:
        order, _ = await lookup_order_by_number(order_number, customer_email)
    if not order and customer_email and not customer_email.endswith(".placeholder"):
        orders = await lookup_order_by_email(customer_email, limit=1)
        order = orders[0] if orders else None

    # Build contextual message
    status_parts = []
    if ticket:
        ticket_status = ticket.get("status", "open")
        if ticket_status in ("open", "in_progress"):
            status_parts.append("Your support request is being handled by our team.")

    if order:
        fulfillment = (order.get("fulfillment_status") or "unfulfilled").replace("_", " ").title()
        payment = (order.get("financial_status") or "pending").replace("_", " ").title()
        order_num = order.get("order_number", "")
        status_parts.append(f"Order #{order_num}: Payment {payment}, Shipping {fulfillment}.")

        fulfillments = order.get("fulfillments") or []
        if fulfillments:
            tracking = fulfillments[-1].get("tracking_url")
            if tracking:
                status_parts.append(f"Track here: {tracking}")
    elif not order and customer_email:
        status_parts.append("I couldn't find any recent orders for your account.")

    message = " ".join(status_parts) if status_parts else "Let me look into that for you."

    return {"ticket": ticket, "order": order, "message": message}
