# Gift card service — fetches gift cards from Shopify, assigns to customers,
# and sends notifications via WhatsApp / Instagram / Email.
from datetime import datetime
from app.database import get_db
from app.models.gift_card import GiftCardAssignment
from app.services.shopify_client import shopify_get, shopify_post, ShopifyAPIError
from app.services.activity_service import log_activity


async def fetch_shopify_gift_cards(status: str = "enabled", limit: int = 50) -> list:
    """Fetch gift cards from Shopify Admin API.
    Status: enabled, disabled, or omit for all.
    Note: Shopify does NOT return the full code after creation — only last_characters."""
    try:
        params = {"limit": limit}
        if status:
            params["status"] = status
        result = await shopify_get("/gift_cards.json", params=params)
        cards = result.get("gift_cards", [])
        formatted = []
        for c in cards:
            last4 = c.get("last_characters", "")
            formatted.append({
                "id": str(c["id"]),
                "code": c.get("code") or f"ending in {last4}" if last4 else "N/A",
                "last_characters": last4,
                "balance": c.get("balance", "0.00"),
                "currency": c.get("currency", "INR"),
                "initial_value": c.get("initial_value", "0.00"),
                "status": "active" if c.get("disabled_at") is None else "disabled",
                "expires_on": c.get("expires_on"),
                "created_at": c.get("created_at"),
                "note": c.get("note", ""),
                "customer_id": str(c["customer_id"]) if c.get("customer_id") else None,
            })
        return formatted
    except ShopifyAPIError as e:
        print(f"Failed to fetch Shopify gift cards: {e}")
        return []


async def get_shopify_gift_card(gift_card_id: str) -> dict | None:
    """Fetch a single gift card from Shopify by ID.
    Note: Shopify only returns last_characters, not the full code (security by design)."""
    try:
        result = await shopify_get(f"/gift_cards/{gift_card_id}.json")
        c = result.get("gift_card", {})
        if not c:
            return None
        last4 = c.get("last_characters", "")
        return {
            "id": str(c["id"]),
            "code": c.get("code") or f"ending in {last4}" if last4 else "N/A",
            "last_characters": last4,
            "balance": c.get("balance", "0.00"),
            "currency": c.get("currency", "INR"),
            "initial_value": c.get("initial_value", "0.00"),
            "status": "active" if c.get("disabled_at") is None else "disabled",
            "expires_on": c.get("expires_on"),
            "created_at": c.get("created_at"),
            "note": c.get("note", ""),
        }
    except ShopifyAPIError as e:
        print(f"Failed to fetch Shopify gift card {gift_card_id}: {e}")
        return None


async def create_shopify_gift_card(initial_value: str, currency: str = "INR", note: str = "") -> dict | None:
    """Create a NEW gift card on Shopify. This is the ONLY time Shopify returns the full code.
    Returns the full gift card dict including the complete code, or None on failure."""
    try:
        payload = {
            "gift_card": {
                "initial_value": str(initial_value),
                "currency": currency,
            }
        }
        if note:
            payload["gift_card"]["note"] = note
        result = await shopify_post("/gift_cards.json", payload)
        gc = result.get("gift_card", {})
        if gc:
            return {
                "id": str(gc["id"]),
                "code": gc.get("code", ""),       # FULL CODE — only available at creation
                "last_characters": gc.get("last_characters", ""),
                "balance": gc.get("balance", initial_value),
                "currency": gc.get("currency", currency),
                "initial_value": gc.get("initial_value", initial_value),
            }
        return None
    except ShopifyAPIError as e:
        print(f"Failed to create Shopify gift card: {e}")
        return None


async def assign_gift_card(
    shopify_gift_card_id: str,
    code: str,
    balance: str,
    currency: str,
    customer_email: str,
    channel: str = "email",
    ticket_id: str = None,
    assigned_by: str = "admin",
    gift_type: str = "manual",
    expires_at: str = None,
    merchant_id: str = None,
) -> dict:
    """Assign a gift card to a customer.
    Creates a NEW Shopify gift card (to get the full code) with the same balance,
    then stores the assignment with the complete code."""
    db = get_db()

    # Look up customer_id
    customer = await db.customers.find_one({"email": customer_email})
    customer_id = customer.get("id") if customer else None

    # Create a NEW Shopify gift card so we get the full code
    # (Shopify never returns the full code after creation — only last_characters)
    new_card = await create_shopify_gift_card(
        initial_value=balance,
        currency=currency,
        note=f"Assigned to {customer_email} via {channel}",
    )

    if new_card and new_card.get("code"):
        full_code = new_card["code"]
        actual_shopify_id = new_card["id"]
        actual_balance = new_card.get("balance", balance)
    else:
        # Fallback: use whatever was passed (will be partial code)
        full_code = code
        actual_shopify_id = shopify_gift_card_id
        actual_balance = balance

    assignment = GiftCardAssignment(
        shopify_gift_card_id=actual_shopify_id,
        code=full_code,
        balance=actual_balance,
        currency=currency,
        customer_email=customer_email,
        customer_id=customer_id,
        channel=channel,
        assigned_by=assigned_by,
        ticket_id=ticket_id,
        type=gift_type,
        expires_at=expires_at,
        merchant_id=merchant_id,
    )
    doc = assignment.model_dump()
    await db.gift_cards.insert_one(doc)

    await log_activity(
        entity_type="gift_card",
        entity_id=assignment.id,
        event="gift_card.assigned",
        actor_type="agent" if assigned_by != "bot" else "system",
        actor_id=assigned_by if assigned_by != "bot" else None,
        description=f"Shopify gift card assigned to {customer_email} via {channel}",
        customer_email=customer_email,
    )

    doc.pop("_id", None)
    return doc


def _format_gift_card_code(code: str) -> str:
    """Format gift card code with spaces every 4 characters (e.g. WPYB KMB7 T7RM 6MRD)."""
    if not code or code == "pending" or code.startswith("ending in"):
        return code
    clean = code.replace(" ", "")
    return " ".join(clean[i:i+4] for i in range(0, len(clean), 4))


def _get_store_info() -> tuple[str, str]:
    """Return (store_name, store_url) from ENV config."""
    from app.config import settings
    domain = settings.shopify_store_domain
    if not domain:
        return ("Store", "")
    store_url = f"https://{domain}" if not domain.startswith("http") else domain
    # Extract readable name: "team-gamma.myshopify.com" → "Team_Gamma"
    store_name = domain.split(".")[0].replace("-", "_")
    store_name = store_name[0].upper() + store_name[1:] if store_name else "Store"
    return (store_name, store_url)


def _build_gift_card_html(code: str, balance: str, currency: str, store_name: str, store_url: str) -> str:
    """Build the HTML email body matching the reference gift card design.
    Uses bulletproof email-safe table-based buttons that work in Gmail, Outlook, etc."""
    formatted_code = _format_gift_card_code(code)

    # Bulletproof email button — the entire colored area is a clickable link
    visit_store_button = ""
    if store_url:
        visit_store_button = f'''<tr><td align="center" style="padding:5px 30px 20px;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr>
        <td align="center" bgcolor="#2ea7d8" style="border-radius:8px;padding:0;">
          <!--[if mso]>
          <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" href="{store_url}" style="height:48px;width:340px;" arcsize="17%" fillcolor="#2ea7d8" stroke="f">
          <v:textbox inset="0,0,0,0"><center style="color:#ffffff;font-size:15px;font-weight:600;font-family:Arial,sans-serif;">Visit online store</center></v:textbox>
          </v:roundrect>
          <![endif]-->
          <!--[if !mso]><!-->
          <a href="{store_url}" target="_blank"
             style="background:#2ea7d8;border-radius:8px;color:#ffffff;display:block;
                    font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:600;
                    line-height:48px;text-align:center;text-decoration:none;width:100%;
                    -webkit-text-size-adjust:none;mso-hide:all;">
            Visit online store
          </a>
          <!--<![endif]-->
        </td>
      </tr>
    </table>
  </td></tr>'''

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f7f7f7;font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f7f7f7;padding:40px 0;">
<tr><td align="center">
<table role="presentation" width="420" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;border-radius:12px;">

  <!-- Price -->
  <tr><td align="center" style="padding:30px 20px 15px;">
    <p style="margin:0;font-size:28px;font-weight:bold;color:#111111;font-family:Arial,Helvetica,sans-serif;">
      ${float(balance):.2f} {currency}
    </p>
  </td></tr>

  <!-- Gift card graphic -->
  <tr><td align="center" style="padding:10px 20px 20px;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td align="center" bgcolor="#f5c542" width="220" height="140"
            style="border-radius:14px;font-size:48px;text-align:center;vertical-align:middle;">
          &#127873;
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- Store name -->
  <tr><td align="center" style="padding:0 20px 8px;">
    <p style="margin:0;font-size:16px;font-weight:bold;color:#333333;font-family:Arial,Helvetica,sans-serif;">
      {store_name}
    </p>
  </td></tr>

  <!-- Code label -->
  <tr><td align="center" style="padding:0 20px 4px;">
    <p style="margin:0;font-size:12px;color:#888888;font-family:Arial,Helvetica,sans-serif;">
      Use the gift card code online
    </p>
  </td></tr>

  <!-- Full gift card code -->
  <tr><td align="center" style="padding:0 20px 20px;">
    <p style="margin:0;font-size:20px;font-weight:bold;font-family:'Courier New',monospace;letter-spacing:2px;color:#111111;">
      {formatted_code}
    </p>
  </td></tr>

  {visit_store_button}

</table>
</td></tr>
</table>
</body>
</html>"""


async def notify_customer(assignment_id: str) -> dict:
    """Send the SAME gift card to the customer on ALL selected channels.
    The channel field can be comma-separated (e.g. 'email,whatsapp,instagram').
    One gift card, shared across channels — not duplicated."""
    db = get_db()
    gc = await db.gift_cards.find_one({"id": assignment_id})
    if not gc:
        return {"error": "Assignment not found"}
    if gc.get("notified"):
        return {"error": "Customer already notified"}

    code = gc.get("code", "")
    balance = gc.get("balance", "0.00")
    currency = gc.get("currency", "INR")
    channel_str = gc.get("channel", "email")
    channels = [c.strip() for c in channel_str.split(",") if c.strip()]
    customer_email = gc.get("customer_email", "")

    store_name, store_url = _get_store_info()
    formatted_code = _format_gift_card_code(code)
    store_line = f"\n🛒 Visit our store: {store_url}" if store_url else ""

    # Text message for WhatsApp / Instagram / ticket thread
    text_message = (
        f"🎁 You've received a Gift Card!\n\n"
        f"💰 ${float(balance):.2f} {currency}\n\n"
        f"🏪 {store_name}\n"
        f"Use the gift card code online\n"
        f"🔑 {formatted_code}"
        f"{store_line}\n\n"
        f"Use this code at checkout to redeem your gift."
    )

    sent_channels = []
    errors = []

    for channel in channels:
        try:
            if channel == "whatsapp":
                phone = None
                # 1. Try from the linked ticket
                if gc.get("ticket_id"):
                    ticket = await db.tickets.find_one({"id": gc["ticket_id"]})
                    phone = ticket.get("whatsapp_phone") if ticket else None
                # 2. Try from the local customer record
                if not phone:
                    customer = await db.customers.find_one({"email": customer_email})
                    phone = customer.get("phone") if customer else None
                # 3. Try from any WhatsApp ticket for this customer
                if not phone:
                    wa_ticket = await db.tickets.find_one({
                        "customer_email": customer_email,
                        "channel": "whatsapp",
                        "whatsapp_phone": {"$ne": None},
                    })
                    phone = wa_ticket.get("whatsapp_phone") if wa_ticket else None
                # 4. Try from Shopify customer data
                if not phone:
                    try:
                        shopify_cust = await shopify_get(
                            "/customers/search.json",
                            params={"query": f"email:{customer_email}", "limit": 1},
                        )
                        customers = shopify_cust.get("customers", [])
                        if customers and customers[0].get("phone"):
                            phone = customers[0]["phone"]
                    except Exception:
                        pass
                if phone:
                    from app.services.whatsapp_service import get_whatsapp_config, send_text_message, send_media_message
                    config = await get_whatsapp_config()
                    # Send store/product image first, then gift card details as text
                    try:
                        products = await shopify_get("/products.json", params={"limit": 1})
                        prods = products.get("products", [])
                        if prods and prods[0].get("images"):
                            image_url = prods[0]["images"][0].get("src", "")
                            if image_url:
                                img_caption = f"🎁 Gift Card — ${float(balance):.2f} {currency}"
                                await send_media_message(phone, "image", image_url, img_caption, config)
                    except Exception as img_err:
                        print(f"[GiftCard] WhatsApp image send failed (non-fatal): {img_err}")
                    # Send full gift card details as text message
                    result = await send_text_message(phone, text_message, config)
                    if result.get("error"):
                        errors.append(f"WhatsApp: {result.get('error')}")
                        print(f"[GiftCard] WhatsApp FAILED for {phone}: {result}")
                    else:
                        sent_channels.append("whatsapp")
                        print(f"[GiftCard] WhatsApp sent to {phone} for {customer_email}")
                else:
                    errors.append(f"WhatsApp: no phone number found for {customer_email}")
                    print(f"[GiftCard] WhatsApp SKIPPED — no phone found for {customer_email}")

            elif channel == "instagram":
                igsid = None
                if gc.get("ticket_id"):
                    ticket = await db.tickets.find_one({"id": gc["ticket_id"]})
                    igsid = ticket.get("instagram_user_id") if ticket else None
                if not igsid:
                    ticket = await db.tickets.find_one({
                        "customer_email": customer_email,
                        "channel": "instagram",
                        "instagram_user_id": {"$ne": None},
                    })
                    igsid = ticket.get("instagram_user_id") if ticket else None
                if igsid:
                    from app.services.instagram_service import get_instagram_config, send_text_message as ig_send
                    config = await get_instagram_config()
                    await ig_send(igsid, text_message, config)
                    sent_channels.append("instagram")
                else:
                    errors.append("Instagram: no user ID found")

            elif channel == "email":
                from app.services.mailgun_service import send_gift_card_email
                ticket_id = gc.get("ticket_id") or ""
                html_body = _build_gift_card_html(code, balance, currency, store_name, store_url)
                await send_gift_card_email(
                    to=customer_email,
                    subject="You've received a Gift Card!",
                    html=html_body,
                    text_fallback=text_message,
                    ticket_id=ticket_id,
                )
                sent_channels.append("email")

        except Exception as e:
            errors.append(f"{channel}: {e}")
            print(f"Gift card notification error ({channel}): {e}")

    # Save the gift card message to the ticket's message thread (once)
    if sent_channels:
        ticket_id = gc.get("ticket_id")
        if ticket_id:
            from app.models.message import MessageInDB
            gift_msg = MessageInDB(
                ticket_id=ticket_id,
                body=text_message,
                sender_type="agent",
                channel=sent_channels[0],
            )
            await db.messages.insert_one(gift_msg.model_dump())
            await db.tickets.update_one(
                {"id": ticket_id},
                {"$set": {"updated_at": datetime.utcnow()}},
            )

        # Mark as notified
        await db.gift_cards.update_one(
            {"id": assignment_id},
            {"$set": {"notified": True, "notified_at": datetime.utcnow()}},
        )

    if not sent_channels:
        return {"error": "; ".join(errors) if errors else "No channels could be reached"}

    result = {"success": True, "channels": sent_channels}
    if errors:
        result["warnings"] = errors
    return result


async def get_assigned_gift_cards(status_filter: str = None, page: int = 1, limit: int = 20) -> dict:
    """Get all gift card assignments from the DB."""
    db = get_db()
    query = {}
    if status_filter == "notified":
        query["notified"] = True
    elif status_filter == "pending":
        query["notified"] = False

    skip = (page - 1) * limit
    cursor = db.gift_cards.find(query).sort("assigned_at", -1).skip(skip).limit(limit)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)

    total = await db.gift_cards.count_documents(query)
    return {"assignments": results, "total": total, "page": page, "limit": limit}


async def create_gift_card_offer(
    customer_email: str,
    amount: float,
    gift_type: str = "retention",
    channel: str = "email",
    ticket_id: str = None,
    assigned_by: str = "bot",
    merchant_id: str = None,
) -> dict:
    """Create a retention gift card offer (used by retention_service).
    This creates a local DB record. Admin must later pick a real Shopify card to assign."""
    db = get_db()

    customer = await db.customers.find_one({"email": customer_email})
    customer_id = customer.get("id") if customer else None

    assignment = GiftCardAssignment(
        shopify_gift_card_id="pending",  # will be set when admin picks a real card
        code="pending",
        balance=str(amount),
        customer_email=customer_email,
        customer_id=customer_id,
        channel=channel,
        assigned_by=assigned_by,
        ticket_id=ticket_id,
        type=gift_type,
        merchant_id=merchant_id,
    )
    doc = assignment.model_dump()
    await db.gift_cards.insert_one(doc)

    await log_activity(
        entity_type="gift_card",
        entity_id=assignment.id,
        event="gift_card.retention_offer",
        actor_type="system",
        description=f"Retention gift card offer for {customer_email} ({amount})",
        customer_email=customer_email,
    )

    doc.pop("_id", None)
    return doc


async def expire_gift_card(assignment_id: str) -> dict:
    """Expire/disable a gift card on Shopify and update local DB."""
    db = get_db()
    gc = await db.gift_cards.find_one({"id": assignment_id})
    if not gc:
        return {"error": "Assignment not found"}

    shopify_id = gc.get("shopify_gift_card_id", "")
    if not shopify_id or shopify_id == "pending":
        return {"error": "No Shopify gift card linked to this assignment"}

    # Step 1: Disable on Shopify
    try:
        await shopify_post(f"/gift_cards/{shopify_id}/disable.json", {})
    except ShopifyAPIError as e:
        return {"error": f"Shopify API error: {e.message}"}

    # Step 2: Update local DB only after Shopify succeeds
    await db.gift_cards.update_one(
        {"id": assignment_id},
        {"$set": {"expired": True, "expired_at": datetime.utcnow()}},
    )

    await log_activity(
        entity_type="gift_card",
        entity_id=assignment_id,
        event="gift_card.expired",
        actor_type="agent",
        description=f"Gift card expired for {gc.get('customer_email', '')}",
        customer_email=gc.get("customer_email"),
    )

    return {"success": True}
