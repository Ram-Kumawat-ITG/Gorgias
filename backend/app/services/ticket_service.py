# Ticket service — handles ticket creation from email, WhatsApp, and Instagram
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.models.ticket import TicketInDB
from app.models.message import MessageInDB
from app.services.shopify_sync import fetch_and_sync_customer
from app.services.activity_service import log_activity


# Keyword-based ticket type classification
TICKET_TYPE_KEYWORDS = {
    "refund": [
        # English
        "refund", "money back", "reimburse", "reimbursement", "charge back", "chargeback", "credit back",
        # Hindi/Urdu
        "refund chahiye", "paisa wapas", "paise wapas", "wapas chahiye", "paisa return", "paise return",
        "reimbursement chahiye", "paise nahi aaye", "paisa nahi mila", "refund karo", "paisa do",
    ],
    "return": [
        # English
        "return", "exchange", "send back", "return policy", "return label", "swap",
        # Hindi/Urdu
        "wapas karna", "wapas bhejo", "product wapas", "item wapas", "exchange karna",
        "badalna hai", "replace karo", "replacement chahiye", "wapas lelo",
    ],
    "shipping": [
        # English
        "shipping", "delivery", "tracking", "shipped", "courier", "dispatch", "transit", "lost package", "not delivered",
        # Hindi/Urdu
        "delivery nahi hui", "order nahi aaya", "tracking number", "courier", "kab aayega",
        "deliver nahi", "shipment", "parcel", "packet", "maal nahi aaya", "saman nahi aaya",
        "abhi tak nahi aaya", "kaha hai mera order",
    ],
    "order_status": [
        # English
        "order status", "where is my order", "order update", "when will i receive", "estimated delivery", "order number",
        # Hindi/Urdu
        "order ka status", "mera order kahan hai", "order update", "order check", "order number",
        "kab milega", "order ki detail", "status batao", "order liya tha",
    ],
    "billing": [
        # English
        "billing", "invoice", "payment", "charged", "double charged", "overcharged", "receipt", "subscription",
        # Hindi/Urdu
        "payment", "bill", "invoice", "paisa kata", "charge hua", "zyada charge", "double charge",
        "receipt chahiye", "payment nahi hui", "payment fail", "subscription",
    ],
    "product_inquiry": [
        # English
        "product", "size", "color", "availability", "in stock", "out of stock", "specification", "compatible",
        # Hindi/Urdu
        "product ke bare mein", "size kya hai", "color", "available hai", "stock mein hai",
        "stock nahi", "specification", "details chahiye", "kaisa hai", "quality kaisi hai",
    ],
    "technical": [
        # English
        "bug", "error", "not working", "broken", "crash", "login", "password", "account", "technical",
        # Hindi/Urdu
        "kaam nahi kar raha", "problem aa rahi hai", "error aa raha hai", "login nahi ho raha",
        "password bhul gaya", "account band", "app crash", "nahi chal raha", "issue aa raha",
    ],
}


async def _get_admin_agent_id() -> str | None:
    """Return the ID of the first active admin, falling back to any active agent."""
    db = get_db()
    try:
        agent = await db.agents.find_one({"is_active": True, "role": "admin"})
        if not agent:
            agent = await db.agents.find_one({"is_active": True})
        return agent["id"] if agent else None
    except Exception:
        return None


async def _fetch_latest_order_snapshot(customer_email: str) -> dict:
    """Return the most recent order snapshot for a real customer email.
    Returns empty dict for placeholder emails (whatsapp/instagram) or if not found."""
    if not customer_email or customer_email.endswith(".placeholder"):
        return {}
    db = get_db()
    try:
        snapshot = await db.order_snapshots.find_one(
            {"email": customer_email},
            sort=[("created_at", -1)],
        )
        return snapshot or {}
    except Exception:
        return {}


def classify_ticket_type(subject: str, body: str = "") -> str:
    """Classify ticket type based on keywords in subject and body."""
    text = f"{subject} {body}".lower()
    # Check each type's keywords, first match wins (ordered by specificity)
    for ticket_type, keywords in TICKET_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return ticket_type
    return "general"


async def apply_sla_policy(ticket_doc: dict) -> dict:
    """Assign an SLA policy to a ticket based on its priority and channel.

    Lookup order:
    1. Policy matching both priority AND channel (applies_to_channels contains the ticket channel).
    2. Fallback: any active policy matching priority only (backwards compatibility).

    Sets sla_due_at, sla_warning_at, first_response_due_at, and initial SLA statuses.
    """
    db = get_db()
    channel = ticket_doc.get("channel", "email")
    priority = ticket_doc["priority"]

    # 1. Try channel-specific match first
    policy = await db.sla_policies.find_one(
        {"priority": priority, "is_active": True, "applies_to_channels": channel}
    )
    # 2. Fallback to any active policy for this priority
    if not policy:
        policy = await db.sla_policies.find_one(
            {"priority": priority, "is_active": True}
        )

    if policy:
        now = datetime.now(timezone.utc)
        resolution_hours = policy["resolution_hours"]
        warning_hours = policy.get("warning_hours") or (resolution_hours * 0.75)
        first_response_hours = policy.get("first_response_hours")

        ticket_doc["sla_policy_id"] = policy["id"]
        ticket_doc["sla_due_at"] = now + timedelta(hours=resolution_hours)
        ticket_doc["sla_warning_at"] = now + timedelta(hours=warning_hours)
        ticket_doc["sla_status"] = "ok"

        if first_response_hours:
            ticket_doc["first_response_due_at"] = now + timedelta(hours=first_response_hours)
            ticket_doc["first_response_sla_status"] = "pending"

    return ticket_doc


async def create_ticket_from_email(customer_email: str, subject: str, body: str, merchant_id: str = None) -> dict:
    db = get_db()
    customer = await fetch_and_sync_customer(customer_email)

    existing = await db.tickets.find_one(
        {"customer_email": customer_email, "status": {"$in": ["open", "pending"]}}
    )

    if existing:
        msg = MessageInDB(
            ticket_id=existing["id"],
            body=body,
            sender_type="customer",
        )
        await db.messages.insert_one(msg.model_dump())
        await db.tickets.update_one(
            {"id": existing["id"]}, {"$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        await log_activity(
            entity_type="message",
            entity_id=msg.id,
            event="message.received",
            actor_type="customer",
            description=f"Customer replied to ticket: {existing['subject']}",
            customer_email=customer_email,
        )
        try:
            from app.services.automation_engine import evaluate_automations
            await evaluate_automations("message.received", existing, msg.model_dump())
        except Exception:
            pass
        existing["_id"] = str(existing["_id"])
        return existing

    order_snapshot = await _fetch_latest_order_snapshot(customer_email)
    admin_id = await _get_admin_agent_id()
    ticket = TicketInDB(
        subject=subject,
        customer_email=customer_email,
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or None,
        shopify_customer_id=customer.get("shopify_customer_id"),
        merchant_id=merchant_id,
        channel="email",
        ticket_type=classify_ticket_type(subject, body),
        assignee_id=admin_id,
        shopify_order_id=order_snapshot.get("shopify_order_id") or None,
        shopify_order_number=str(order_snapshot["order_number"]) if order_snapshot.get("order_number") else None,
    )
    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    msg = MessageInDB(
        ticket_id=ticket.id,
        body=body,
        sender_type="customer",
    )
    await db.messages.insert_one(msg.model_dump())

    await log_activity(
        entity_type="ticket",
        entity_id=ticket.id,
        event="ticket.created",
        actor_type="customer",
        description=f"Ticket created via email: {subject}",
        customer_email=customer_email,
    )

    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("ticket.created", ticket_doc)
    except Exception:
        pass

    ticket_doc.pop("_id", None)
    return ticket_doc


async def create_ticket_from_whatsapp(
    phone: str,
    customer_name: str,
    message_body: str,
    wa_message_id: str = None,
    media_url: str = "",
    media_type: str = "",
    media_id: str = "",
    merchant_id: str = None,
) -> dict:
    """Create a new ticket or append to existing one from a WhatsApp message."""
    db = get_db()

    # Find or create customer by phone number
    customer = await db.customers.find_one({"phone": phone})
    if not customer:
        # Also check by placeholder email in case phone field wasn't set
        placeholder_email = f"{phone}@whatsapp.placeholder"
        customer = await db.customers.find_one({"email": placeholder_email})
    if not customer:
        from app.models.customer import CustomerInDB
        placeholder_email = f"{phone}@whatsapp.placeholder"
        customer = CustomerInDB(
            email=placeholder_email,
            phone=phone,
            first_name=customer_name or phone,
        ).model_dump()
        try:
            await db.customers.insert_one(customer)
        except Exception:
            # Duplicate email — fetch existing
            customer = await db.customers.find_one({"email": placeholder_email})
            if customer and not customer.get("phone"):
                await db.customers.update_one(
                    {"email": placeholder_email}, {"$set": {"phone": phone}}
                )

    customer_email = customer.get("email", f"{phone}@whatsapp.placeholder")

    # Check for existing open WhatsApp ticket from this phone
    existing = await db.tickets.find_one(
        {"whatsapp_phone": phone, "channel": "whatsapp", "status": {"$in": ["open", "pending", "pending_admin_action"]}}
    )

    if existing:
        msg = MessageInDB(
            ticket_id=existing["id"],
            body=message_body,
            sender_type="customer",
            channel="whatsapp",
            whatsapp_message_id=wa_message_id,
            whatsapp_media_id=media_id if media_id else None,
            whatsapp_media_url=media_url if media_url else None,
            whatsapp_media_type=media_type if media_type else None,
        )
        await db.messages.insert_one(msg.model_dump())
        # Re-classify ticket type on every new customer message
        new_type = classify_ticket_type(existing.get("subject", ""), message_body)
        ticket_updates = {
            "updated_at": datetime.now(timezone.utc),
            "whatsapp_last_customer_msg_at": datetime.now(timezone.utc),
        }
        if new_type != "general" and new_type != existing.get("ticket_type"):
            ticket_updates["ticket_type"] = new_type
        await db.tickets.update_one(
            {"id": existing["id"]},
            {"$set": ticket_updates},
        )
        await log_activity(
            entity_type="message",
            entity_id=msg.id,
            event="message.received",
            actor_type="customer",
            description=f"WhatsApp message from {phone}",
            customer_email=customer_email,
        )
        try:
            from app.services.automation_engine import evaluate_automations
            await evaluate_automations("message.received", existing, msg.model_dump())
        except Exception:
            pass
        existing["_id"] = str(existing["_id"])
        return existing

    # Create new ticket
    order_snapshot = await _fetch_latest_order_snapshot(customer_email)
    admin_id = await _get_admin_agent_id()
    ticket = TicketInDB(
        subject=f"WhatsApp: {customer_name or phone}",
        customer_email=customer_email,
        customer_name=customer_name or None,
        merchant_id=merchant_id,
        channel="whatsapp",
        whatsapp_phone=phone,
        whatsapp_last_customer_msg_at=datetime.now(timezone.utc),
        ticket_type=classify_ticket_type(f"WhatsApp: {customer_name or phone}", message_body),
        assignee_id=admin_id,
        shopify_order_id=order_snapshot.get("shopify_order_id") or None,
        shopify_order_number=str(order_snapshot["order_number"]) if order_snapshot.get("order_number") else None,
    )
    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    msg = MessageInDB(
        ticket_id=ticket.id,
        body=message_body,
        sender_type="customer",
        channel="whatsapp",
        whatsapp_message_id=wa_message_id,
        whatsapp_media_url=media_url if media_url else None,
        whatsapp_media_type=media_type if media_type else None,
    )
    await db.messages.insert_one(msg.model_dump())

    await log_activity(
        entity_type="ticket",
        entity_id=ticket.id,
        event="ticket.created",
        actor_type="customer",
        description=f"Ticket created via WhatsApp from {phone}",
        customer_email=customer_email,
    )

    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("ticket.created", ticket_doc)
    except Exception:
        pass

    ticket_doc.pop("_id", None)
    return ticket_doc


async def create_ticket_from_instagram(
    igsid: str,
    message_body: str,
    ig_message_id: str = None,
    media_url: str = "",
    media_type: str = "",
    merchant_id: str = None,
) -> dict:
    """Create a new ticket or append to existing one from an Instagram DM."""
    db = get_db()

    placeholder_email = f"{igsid}@instagram.placeholder"

    customer = await db.customers.find_one({"email": placeholder_email})
    if not customer:
        from app.models.customer import CustomerInDB
        customer = CustomerInDB(
            email=placeholder_email,
            first_name="Instagram User",
        ).model_dump()
        try:
            await db.customers.insert_one(customer)
        except Exception:
            customer = await db.customers.find_one({"email": placeholder_email})

    existing = await db.tickets.find_one(
        {"instagram_user_id": igsid, "channel": "instagram", "status": {"$in": ["open", "pending"]}}
    )

    if existing:
        msg = MessageInDB(
            ticket_id=existing["id"],
            body=message_body,
            sender_type="customer",
            channel="instagram",
            instagram_message_id=ig_message_id,
            instagram_sender_igsid=igsid,
            instagram_media_url=media_url if media_url else None,
            instagram_media_type=media_type if media_type else None,
        )
        await db.messages.insert_one(msg.model_dump())
        await db.tickets.update_one(
            {"id": existing["id"]},
            {"$set": {
                "updated_at": datetime.now(timezone.utc),
                "instagram_last_customer_msg_at": datetime.now(timezone.utc),
            }},
        )
        await log_activity(
            entity_type="message",
            entity_id=msg.id,
            event="message.received",
            actor_type="customer",
            description=f"Instagram DM from {igsid}",
            customer_email=placeholder_email,
        )
        try:
            from app.services.automation_engine import evaluate_automations
            await evaluate_automations("message.received", existing, msg.model_dump())
        except Exception:
            pass
        existing["_id"] = str(existing["_id"])
        return existing

    order_snapshot = await _fetch_latest_order_snapshot(placeholder_email)
    admin_id = await _get_admin_agent_id()
    ticket = TicketInDB(
        subject=f"Instagram DM: {igsid}",
        customer_email=placeholder_email,
        merchant_id=merchant_id,
        channel="instagram",
        instagram_user_id=igsid,
        instagram_last_customer_msg_at=datetime.now(timezone.utc),
        ticket_type=classify_ticket_type(f"Instagram DM: {igsid}", message_body),
        assignee_id=admin_id,
        shopify_order_id=order_snapshot.get("shopify_order_id") or None,
        shopify_order_number=str(order_snapshot["order_number"]) if order_snapshot.get("order_number") else None,
    )
    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    msg = MessageInDB(
        ticket_id=ticket.id,
        body=message_body,
        sender_type="customer",
        channel="instagram",
        instagram_message_id=ig_message_id,
        instagram_sender_igsid=igsid,
        instagram_media_url=media_url if media_url else None,
        instagram_media_type=media_type if media_type else None,
    )
    await db.messages.insert_one(msg.model_dump())

    await log_activity(
        entity_type="ticket",
        entity_id=ticket.id,
        event="ticket.created",
        actor_type="customer",
        description=f"Ticket created via Instagram DM from {igsid}",
        customer_email=placeholder_email,
    )

    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("ticket.created", ticket_doc)
    except Exception:
        pass

    ticket_doc.pop("_id", None)
    return ticket_doc
