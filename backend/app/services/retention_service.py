# Cancel retention service — intercepts cancel requests with gift card offers.
# Used by all channels (WhatsApp, Instagram, Email) before proceeding with cancellation.
#
# Flow:
#   1. Customer says "cancel" → bot creates a REAL gift card, sends it with retention message
#   2. Customer says OK / keep → retention successful, order stays
#   3. Customer says YES / cancel → bot asks "Are you sure?"
#   4. Customer confirms again → order cancelled via Shopify API
import re
from datetime import datetime
from app.database import get_db
from app.services.activity_service import log_activity


# ── Configurable retention offer constants ───────────────────────────────────
RETENTION_CONFIG = {
    "gift_card_amount": 500,        # in smallest currency unit (e.g. 500 = $5.00 or Rs.500)
    "max_retention_attempts": 1,    # only 1 attempt per cancel request
    "currency": "INR",
}

# ── Cancel intent detection keywords ────────────────────────────────────────
CANCEL_KEYWORDS = [
    "cancel", "cancel order", "cancel my order", "want to cancel",
    "cancellation", "cancel karo", "order cancel", "cancel kar do",
    "cancel krdo", "cancel kardo", "cancel kr do",
]


def detect_cancel_intent(message: str) -> bool:
    """Detect if the message contains a cancel intent."""
    text = message.lower().strip()
    return any(keyword in text for keyword in CANCEL_KEYWORDS)


async def check_retention_attempted(ticket_id: str) -> bool:
    """Check if a retention offer was already made for this ticket."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        return False
    return ticket.get("retention_offered", False)


async def check_awaiting_cancel_confirm(ticket_id: str) -> bool:
    """Check if we're waiting for the customer's second 'are you sure?' confirmation."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        return False
    return ticket.get("awaiting_cancel_confirm", False)


async def create_or_update_cancel_ticket(
    customer_email: str,
    order_id: str,
    channel: str,
    ticket_id: str = None,
) -> dict:
    """Mark an existing ticket as cancel_requested, or create one if needed."""
    db = get_db()

    if ticket_id:
        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": {
                "ticket_type": "cancel_requested",
                "cancel_requested_order_id": order_id,
                "updated_at": datetime.utcnow(),
            }},
        )
        ticket = await db.tickets.find_one({"id": ticket_id})
        if ticket:
            ticket["_id"] = str(ticket["_id"])
        return ticket or {}

    # Find existing open ticket for this customer
    existing = await db.tickets.find_one({
        "customer_email": customer_email,
        "status": {"$in": ["open", "pending"]},
    })
    if existing:
        await db.tickets.update_one(
            {"id": existing["id"]},
            {"$set": {
                "ticket_type": "cancel_requested",
                "cancel_requested_order_id": order_id,
                "updated_at": datetime.utcnow(),
            }},
        )
        existing["_id"] = str(existing["_id"])
        return existing

    return {}


async def create_retention_gift_card(customer_email: str, channel: str, ticket_id: str) -> dict | None:
    """Create a REAL Shopify gift card immediately and assign it to the customer.
    Returns the assignment dict with the full code, or None on failure."""
    try:
        from app.services.gift_card_service import create_shopify_gift_card, assign_gift_card

        amount = RETENTION_CONFIG["gift_card_amount"]
        currency = RETENTION_CONFIG["currency"]

        # Create a real Shopify gift card (returns full code)
        new_card = await create_shopify_gift_card(
            initial_value=str(amount),
            currency=currency,
            note=f"Retention offer for {customer_email}",
        )
        if not new_card or not new_card.get("code"):
            print(f"[Retention] Failed to create Shopify gift card for {customer_email}")
            return None

        # Store the assignment in DB
        from app.models.gift_card import GiftCardAssignment
        db = get_db()
        customer = await db.customers.find_one({"email": customer_email})
        customer_id = customer.get("id") if customer else None

        assignment = GiftCardAssignment(
            shopify_gift_card_id=new_card["id"],
            code=new_card["code"],
            balance=new_card.get("balance", str(amount)),
            currency=currency,
            customer_email=customer_email,
            customer_id=customer_id,
            channel=channel,
            assigned_by="bot",
            ticket_id=ticket_id,
            type="retention",
        )
        doc = assignment.model_dump()
        await db.gift_cards.insert_one(doc)

        # Mark as notified since we're sending the code in the retention message
        await db.gift_cards.update_one(
            {"id": assignment.id},
            {"$set": {"notified": True, "notified_at": datetime.utcnow()}},
        )

        await log_activity(
            entity_type="gift_card",
            entity_id=assignment.id,
            event="gift_card.retention_assigned",
            actor_type="system",
            description=f"Retention gift card assigned to {customer_email} — code: {new_card['code']}",
            customer_email=customer_email,
        )

        print(f"[Retention] Gift card created for {customer_email}: {new_card['code']}")
        return doc

    except Exception as e:
        print(f"[Retention] Gift card creation error: {e}")
        return None


def _format_gift_card_code(code: str) -> str:
    """Format code with spaces: WPYBKMB7T7RM6MRD → WPYB KMB7 T7RM 6MRD"""
    if not code:
        return code
    clean = code.replace(" ", "")
    return " ".join(clean[i:i+4] for i in range(0, len(clean), 4))


def get_retention_offer_message(channel: str, gift_card_code: str, gift_card_balance: str, currency: str) -> str:
    """Return the retention offer message WITH the gift card details.
    The gift card is already assigned — customer keeps it regardless of decision."""
    formatted_code = _format_gift_card_code(gift_card_code)

    if channel == "whatsapp":
        return (
            f"We'd hate to see you go! 🎁\n\n"
            f"Here's a special Gift Card for you:\n"
            f"🔑 Code: *{formatted_code}*\n"
            f"💰 Balance: {currency} {gift_card_balance}\n\n"
            f"Please consider using it before cancelling your order.\n\n"
            f"Would you like to keep your order?\n"
            f"Reply *OK* to keep your order or *CANCEL* to proceed with cancellation."
        )
    elif channel == "instagram":
        return (
            f"We'd hate to see you go! 🎁\n\n"
            f"Here's a special Gift Card for you:\n"
            f"Code: {formatted_code}\n"
            f"Balance: {currency} {gift_card_balance}\n\n"
            f"Please consider using it before cancelling your order.\n\n"
            f"Reply OK to keep your order or CANCEL to proceed with cancellation."
        )
    else:  # email
        return (
            f"We'd hate to see you go!\n\n"
            f"Here's a special Gift Card for you:\n"
            f"Code: {formatted_code}\n"
            f"Balance: {currency} {gift_card_balance}\n\n"
            f"Please consider using it before cancelling your order.\n\n"
            f"Would you like to keep your order?\n"
            f"Please reply OK to keep your order or CANCEL to proceed with cancellation."
        )


async def mark_retention_offered(ticket_id: str) -> None:
    """Mark that a retention offer has been made on this ticket."""
    db = get_db()
    await db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "retention_offered": True,
            "retention_offered_at": datetime.utcnow(),
        }},
    )


def detect_retention_response(message: str) -> str | None:
    """Detect if the customer wants to cancel (YES/CANCEL) or keep the order (OK/NO).
    Returns 'yes_cancel', 'no_keep', or None if unclear."""
    text = message.lower().strip()

    # OK / keep patterns — customer wants to keep the order
    no_keep_patterns = [
        r"\bok\b", r"\bokay\b", r"\bkeep\b", r"\bdon'?t cancel\b",
        r"\bno\b", r"\bnah\b", r"\bnope\b", r"\bnahi\b",
        r"\bmat\b", r"\bna\b",
    ]
    # CANCEL / yes patterns — customer still wants to cancel
    yes_cancel_patterns = [
        r"\bcancel\b", r"\byes\b", r"\byeah\b", r"\byep\b", r"\bsure\b",
        r"\bha\b", r"\bhaan\b", r"\bji\b",
        r"\bjust cancel\b", r"\bcancel (it|hi|karo)\b",
        r"\bproceed\b",
    ]

    for pattern in no_keep_patterns:
        if re.search(pattern, text):
            return "no_keep"
    for pattern in yes_cancel_patterns:
        if re.search(pattern, text):
            return "yes_cancel"
    return None


async def process_retention_response(ticket_id: str, response: str, channel: str = "email") -> str:
    """Process the customer's response to the retention offer.
    response: 'no_keep' (customer keeps order) or 'yes_cancel' (customer wants to cancel).
    Returns the reply message to send."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        return "Sorry, I couldn't find your request. Please try again."

    if response == "no_keep":
        # Customer chose to KEEP the order — retention successful
        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": {
                "retention_accepted": True,
                "updated_at": datetime.utcnow(),
                "status": "resolved",
                "resolved_at": datetime.utcnow(),
            }},
        )

        await log_activity(
            entity_type="ticket",
            entity_id=ticket_id,
            event="retention.accepted",
            actor_type="customer",
            description="Customer chose to keep order — retention successful",
            customer_email=ticket.get("customer_email"),
        )

        if channel == "whatsapp":
            return (
                "Great choice! 🎉\n\n"
                "Your order is safe and the Gift Card is yours to use anytime.\n"
                "Thank you for giving us another chance! 😊"
            )
        elif channel == "instagram":
            return (
                "Great choice! 🎉 Your order is safe and the Gift Card is yours to use anytime!"
            )
        else:
            return (
                "Thank you for giving us another chance! "
                "Your order is safe and the Gift Card is yours to use anytime."
            )

    else:
        # Customer said CANCEL — ask "Are you sure?" before proceeding
        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": {
                "retention_accepted": False,
                "awaiting_cancel_confirm": True,
                "updated_at": datetime.utcnow(),
            }},
        )

        await log_activity(
            entity_type="ticket",
            entity_id=ticket_id,
            event="retention.rejected",
            actor_type="customer",
            description="Customer wants to cancel — awaiting final confirmation",
            customer_email=ticket.get("customer_email"),
        )

        if channel == "whatsapp":
            return (
                "Are you sure you want to cancel your order? "
                "This action cannot be undone. 🙏\n\n"
                "Reply *YES* to confirm cancellation or *NO* to keep your order."
            )
        elif channel == "instagram":
            return (
                "Are you sure you want to cancel your order? "
                "This action cannot be undone.\n\n"
                "Reply YES to confirm cancellation or NO to keep your order."
            )
        else:
            return (
                "Are you sure you want to cancel your order? "
                "This action cannot be undone.\n\n"
                "Please reply YES to confirm cancellation or NO to keep your order."
            )


async def process_cancel_confirmation(ticket_id: str, confirmed: bool, channel: str = "email") -> str:
    """Process the customer's final confirmation after 'Are you sure?'.
    confirmed=True → cancel the order via Shopify. confirmed=False → keep order."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        return "Sorry, I couldn't find your request. Please try again."

    # Clear the awaiting state
    await db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {"awaiting_cancel_confirm": False, "updated_at": datetime.utcnow()}},
    )

    if not confirmed:
        # Customer changed their mind — keep the order
        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": {
                "retention_accepted": True,
                "status": "resolved",
                "resolved_at": datetime.utcnow(),
            }},
        )

        await log_activity(
            entity_type="ticket",
            entity_id=ticket_id,
            event="cancel.aborted",
            actor_type="customer",
            description="Customer chose not to cancel after confirmation prompt",
            customer_email=ticket.get("customer_email"),
        )

        if channel == "whatsapp":
            return "Great! Your order has been kept. The Gift Card is yours to use anytime! 🎉"
        elif channel == "instagram":
            return "Great! Your order has been kept. The Gift Card is yours to use anytime! 🎉"
        else:
            return "Great! Your order has been kept. The Gift Card is yours to use anytime."

    # Customer confirmed cancellation — cancel via Shopify
    order_id = ticket.get("cancel_requested_order_id", "")
    cancel_success = False
    if order_id:
        try:
            from app.services.order_service import cancel_order
            cancel_success = await cancel_order(order_id)
        except Exception as e:
            print(f"[Retention] Shopify cancel error: {e}")

    if cancel_success:
        await db.tickets.update_one(
            {"id": ticket_id},
            {"$set": {
                "status": "resolved",
                "resolved_at": datetime.utcnow(),
                "ticket_type": "cancel_requested",
            }},
        )

        await log_activity(
            entity_type="ticket",
            entity_id=ticket_id,
            event="order.cancelled",
            actor_type="system",
            description=f"Order {order_id} cancelled via Shopify after customer confirmation",
            customer_email=ticket.get("customer_email"),
        )

        if channel == "whatsapp":
            return (
                "Your order has been successfully cancelled. ✅\n"
                "The Gift Card we gave you is still yours — feel free to use it anytime! 🎁\n\n"
                "If you need anything else, we're here to help. 🙏"
            )
        elif channel == "instagram":
            return (
                "Your order has been successfully cancelled. ✅ "
                "The Gift Card is still yours to use anytime! 🎁"
            )
        else:
            return (
                "Your order has been successfully cancelled. "
                "The Gift Card we gave you is still yours — feel free to use it anytime. "
                "If you need anything else, we're here to help."
            )
    else:
        # Cancel failed — escalate to admin
        admin_id = None
        try:
            admin = await db.agents.find_one({"is_active": True, "role": "admin"})
            admin_id = admin["id"] if admin else None
        except Exception:
            pass

        update_fields = {"priority": "high", "status": "open", "updated_at": datetime.utcnow()}
        if admin_id:
            update_fields["assignee_id"] = admin_id
        await db.tickets.update_one({"id": ticket_id}, {"$set": update_fields})

        if channel == "whatsapp":
            return (
                "We're having trouble cancelling your order right now. 😔\n"
                "Our team has been notified and will process it shortly. 🙏"
            )
        elif channel == "instagram":
            return (
                "We're having trouble cancelling your order right now. "
                "Our team has been notified and will process it shortly."
            )
        else:
            return (
                "We're having trouble cancelling your order right now. "
                "Our team has been notified and will process it shortly."
            )
