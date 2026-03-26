# Mailgun inbound email handler — creates tickets from incoming support emails
from fastapi import APIRouter, Request
from app.services.ticket_service import create_ticket_from_email

router = APIRouter(prefix="/webhooks/email", tags=["Email"])


@router.post("/inbound")
async def inbound_email(request: Request):
    form = await request.form()
    sender = form.get("sender", "")
    subject = form.get("subject", "No Subject")
    body = form.get("stripped-text") or form.get("body-plain", "")

    if not body or not body.strip():
        return {"status": "skipped", "reason": "empty body"}

    ticket = await create_ticket_from_email(
        customer_email=sender,
        subject=subject,
        body=body.strip(),
    )
    return {"status": "received", "ticket_id": ticket.get("id")}
