# Mailgun email sending service — sends agent replies to customers via email
import httpx
from app.config import settings
from app.database import get_db


async def send_reply_email(to: str, subject: str, body: str, ticket_id: str):
    # Try to get merchant-specific Mailgun config from ticket
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id})
    merchant = None
    if ticket and ticket.get("merchant_id"):
        merchant = await db.merchants.find_one({"id": ticket["merchant_id"]})

    # Use merchant config if available and not a placeholder, else fall back to global .env config
    _PLACEHOLDER_DOMAINS = {"placeholder.mailgun.org", ""}
    if merchant:
        api_key = merchant.get("mailgun_api_key", "")
        domain = merchant.get("mailgun_domain", "")
        if not api_key or domain in _PLACEHOLDER_DOMAINS:
            api_key = settings.mailgun_api_key
            domain = settings.mailgun_domain
    else:
        api_key = settings.mailgun_api_key
        domain = settings.mailgun_domain

    if not api_key or not domain:
        print("Mailgun not configured — skipping email send")
        return

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://api.mailgun.net/v3/{domain}/messages",
                auth=("api", api_key),
                data={
                    "from": f"Support <mailgun@{domain}>",
                    "to": to,
                    "subject": subject,
                    "text": body,
                    "h:X-Ticket-ID": ticket_id,
                },
                timeout=10.0,
            )
            r.raise_for_status()
            print(f"Email sent to {to} for ticket {ticket_id}")
    except Exception as e:
        print(f"Mailgun send failed: {e}")


async def send_gift_card_email(to: str, subject: str, html: str, text_fallback: str, ticket_id: str):
    """Send an HTML gift card email to a customer (with plain-text fallback)."""
    db = get_db()
    ticket = await db.tickets.find_one({"id": ticket_id}) if ticket_id else None
    merchant = None
    if ticket and ticket.get("merchant_id"):
        merchant = await db.merchants.find_one({"id": ticket["merchant_id"]})

    _PLACEHOLDER_DOMAINS = {"placeholder.mailgun.org", ""}
    if merchant:
        api_key = merchant.get("mailgun_api_key", "")
        domain = merchant.get("mailgun_domain", "")
        if not api_key or domain in _PLACEHOLDER_DOMAINS:
            api_key = settings.mailgun_api_key
            domain = settings.mailgun_domain
    else:
        api_key = settings.mailgun_api_key
        domain = settings.mailgun_domain

    if not api_key or not domain:
        print("Mailgun not configured — skipping gift card email send")
        return

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://api.mailgun.net/v3/{domain}/messages",
                auth=("api", api_key),
                data={
                    "from": f"Support <mailgun@{domain}>",
                    "to": to,
                    "subject": subject,
                    "text": text_fallback,
                    "html": html,
                    "h:X-Ticket-ID": ticket_id or "",
                },
                timeout=10.0,
            )
            r.raise_for_status()
            print(f"Gift card HTML email sent to {to}")
    except Exception as e:
        print(f"Mailgun gift card email failed: {e}")
