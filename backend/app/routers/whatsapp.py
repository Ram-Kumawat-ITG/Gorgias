# WhatsApp webhook router — handles Meta webhook verification and inbound messages
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from app.config import settings
from app.database import get_db
from app.services.whatsapp_service import (
    verify_webhook_signature,
    get_whatsapp_config,
    mark_as_read,
    download_media,
    send_text_message,
    send_interactive_buttons,
    send_image_with_buttons,
    send_media_message,
)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp"])


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification — responds with hub.challenge if token matches."""
    if hub_mode == "subscribe":
        # Check global config first
        global_token = settings.whatsapp_verify_token
        if global_token and hub_verify_token == global_token:
            return PlainTextResponse(content=hub_challenge)

        # Always fall through to merchant lookup — covers both "no global token" and
        # "global token set but this webhook is for a different (merchant) WABA"
        db = get_db()
        merchant = await db.merchants.find_one(
            {"whatsapp_verify_token": hub_verify_token, "is_active": True}
        )
        if merchant:
            return PlainTextResponse(content=hub_challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/test")
async def test_connection(request: Request):
    """Test WhatsApp API connection by verifying credentials are valid."""
    import httpx
    body = await request.json()
    merchant_id = body.get("merchant_id")

    # Use inline credentials if provided (e.g. validating before save),
    # otherwise fall back to the stored config for this merchant.
    phone_number_id = body.get("phone_number_id") or ""
    access_token = body.get("access_token") or ""

    if not phone_number_id or not access_token:
        config = await get_whatsapp_config(merchant_id)
        phone_number_id = phone_number_id or config.get("phone_number_id", "")
        access_token = access_token or config.get("access_token", "")

    if not phone_number_id or not access_token:
        raise HTTPException(status_code=400, detail="WhatsApp credentials not configured")

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://graph.facebook.com/v21.0/{phone_number_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "status": "connected",
                "phone_number": data.get("display_phone_number", ""),
                "quality_rating": data.get("quality_rating", ""),
                "verified_name": data.get("verified_name", ""),
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"WhatsApp API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@router.post("")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive inbound WhatsApp messages and status updates from Meta."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Verify signature — try global secret first, then merchant-specific secret.
    # Only hard-reject when a secret IS configured but the signature doesn't match.
    if signature:
        global_secret = settings.whatsapp_app_secret
        sig_ok = bool(global_secret) and verify_webhook_signature(body, signature, global_secret)

        if not sig_ok:
            # Parse payload to find phone_number_id → look up merchant secret
            import json as _json
            try:
                _temp = _json.loads(body)
                _phone_id = (
                    _temp.get("entry", [{}])[0]
                    .get("changes", [{}])[0]
                    .get("value", {})
                    .get("metadata", {})
                    .get("phone_number_id", "")
                )
                if _phone_id:
                    _db = get_db()
                    _merchant = await _db.merchants.find_one(
                        {"whatsapp_phone_number_id": _phone_id, "is_active": True}
                    )
                    if _merchant and _merchant.get("whatsapp_app_secret"):
                        sig_ok = verify_webhook_signature(body, signature, _merchant["whatsapp_app_secret"])
            except Exception:
                pass

        # Reject only if a secret was configured but the signature didn't match
        if not sig_ok and global_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Queue processing as a background task — return 200 to Meta immediately
    background_tasks.add_task(_process_webhook_payload, payload)
    return {"status": "ok"}


async def _process_webhook_payload(payload: dict):
    """Process a webhook payload in the background after returning 200 to Meta."""
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    try:
                        await _handle_messages(value)
                    except Exception as e:
                        print(f"[WhatsApp] _handle_messages error: {e}")
                if "statuses" in value:
                    try:
                        await _handle_statuses(value)
                    except Exception as e:
                        print(f"[WhatsApp] _handle_statuses error: {e}")
    except Exception as e:
        print(f"[WhatsApp] _process_webhook_payload error: {e}")


async def _handle_messages(value: dict):
    """Process incoming customer messages."""
    db = get_db()
    metadata = value.get("metadata", {})
    phone_number_id = metadata.get("phone_number_id", "")

    # Find merchant by phone_number_id
    merchant = await db.merchants.find_one(
        {"whatsapp_phone_number_id": phone_number_id, "is_active": True}
    )
    merchant_id = merchant["id"] if merchant else None

    contacts = value.get("contacts", [])
    messages = value.get("messages", [])

    for msg in messages:
        wa_message_id = msg.get("id", "")
        from_phone = msg.get("from", "")  # customer's phone number
        msg_type = msg.get("type", "text")

        # Extract message body based on type
        body = ""
        media_url = ""
        media_type = ""

        if msg_type == "text":
            body = msg.get("text", {}).get("body", "")
        elif msg_type in ("image", "video", "document", "audio"):
            media_obj = msg.get(msg_type, {})
            body = media_obj.get("caption", f"[{msg_type} received]")
            media_id = media_obj.get("id", "")
            media_type = msg_type
            if media_id:
                config = await get_whatsapp_config(merchant_id)
                media_url = await download_media(media_id, config)
        elif msg_type == "location":
            loc = msg.get("location", {})
            body = f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"
        elif msg_type == "contacts":
            body = "[Contact card received]"
        elif msg_type == "sticker":
            body = "[Sticker received]"
        elif msg_type == "interactive":
            interactive_data = msg.get("interactive", {})
            if interactive_data.get("type") == "button_reply":
                btn_reply = interactive_data.get("button_reply", {})
                btn_title = btn_reply.get("title", "")
                btn_id = btn_reply.get("id", "")
                # Map button IDs to natural-language bodies the AI can parse
                # Formats: cancel_<oid>, refund_<oid>, replace_<oid>, return_<oid>,
                #          accept_gc_<type>, decline_gc_<type>,
                #          issue_damaged_<type>, issue_wrong_<type>, issue_missing_<type>
                if btn_id.startswith("refund_"):
                    _oid = btn_id[len("refund_"):]
                    body = f"I want a refund for my order (order_id:{_oid})"
                elif btn_id.startswith("replace_"):
                    _oid = btn_id[len("replace_"):]
                    body = f"I want a replacement for my order (order_id:{_oid})"
                elif btn_id.startswith("return_"):
                    _oid = btn_id[len("return_"):]
                    body = f"I want to return my order (order_id:{_oid})"
                elif btn_id.startswith("cancel_"):
                    _oid = btn_id[len("cancel_"):]
                    body = f"Please cancel my order (order_id:{_oid})"
                elif btn_id.startswith("accept_gc_"):
                    _atype = btn_id[len("accept_gc_"):]
                    body = f"I accept the gift card offer (action_type:{_atype})"
                elif btn_id.startswith("decline_gc_"):
                    _atype = btn_id[len("decline_gc_"):]
                    body = f"No, I don't want the gift card, please continue with my {_atype} request"
                elif btn_id.startswith("issue_damaged_"):
                    _atype = btn_id[len("issue_damaged_"):]
                    body = f"The item was damaged (issue:damaged action_type:{_atype})"
                elif btn_id.startswith("issue_wrong_"):
                    _atype = btn_id[len("issue_wrong_"):]
                    body = f"I received the wrong item (issue:wrong_item action_type:{_atype})"
                elif btn_id.startswith("issue_missing_"):
                    _atype = btn_id[len("issue_missing_"):]
                    body = f"An item is missing from my order (issue:missing action_type:{_atype})"
                else:
                    _btn_action, _, _btn_ref = btn_id.partition("_")
                    body = btn_title + (f" (order {_btn_ref})" if _btn_ref else "")
            else:
                body = f"[Interactive message received]"
        else:
            body = f"[{msg_type} message received]"

        # Get contact name
        contact_name = ""
        for c in contacts:
            if c.get("wa_id") == from_phone:
                profile = c.get("profile", {})
                contact_name = profile.get("name", "")
                break

        # Mark as read
        try:
            config = await get_whatsapp_config(merchant_id)
            await mark_as_read(wa_message_id, config)
        except Exception:
            pass

        # Detect brand-new users before ticket creation so we can send a one-time greeting.
        # A user is "new" if they have no customer record yet, or if they have one but
        # wa_greeted is False/missing (covers pre-existing data with no flag).
        _existing_customer = await db.customers.find_one({"phone": from_phone})
        if not _existing_customer:
            _existing_customer = await db.customers.find_one(
                {"email": f"{from_phone}@whatsapp.placeholder"}
            )
        _is_new_user = not _existing_customer or not _existing_customer.get("wa_greeted")

        # Create or update ticket via ticket_service
        from app.services.ticket_service import create_ticket_from_whatsapp
        ticket_doc = await create_ticket_from_whatsapp(
            phone=from_phone,
            customer_name=contact_name,
            message_body=body,
            wa_message_id=wa_message_id,
            media_url=media_url,
            media_type=media_type,
            merchant_id=merchant_id,
        )

        # One-time greeting for brand-new users.
        # Sends the welcome message, persists it, marks the customer as greeted,
        # then skips the AI reply so the bot waits for the user's next message.
        if _is_new_user and body:
            _GREETING = (
                "Hey! 👋 Welcome! I'm Aria, your personal shopping assistant.\n\n"
                "I can help you place orders, track shipments, cancel orders, "
                "check product availability, and more.\n\n"
                "What can I help you with today? 😊"
            )
            try:
                from app.services.whatsapp_service import send_text_message as _send
                from app.models.message import MessageInDB as _MsgInDB
                _wa_cfg = await get_whatsapp_config(merchant_id)
                _gr_result = await _send(from_phone, _GREETING, _wa_cfg)
                _gr_msgs = _gr_result.get("messages") or []
                _gr_sent_id = _gr_msgs[0].get("id") if _gr_msgs else None
                _gr_doc = _MsgInDB(
                    ticket_id=ticket_doc.get("id", ""),
                    body=_GREETING,
                    sender_type="agent",
                    channel="whatsapp",
                    ai_generated=True,
                    whatsapp_message_id=_gr_sent_id,
                    whatsapp_status="sent" if _gr_sent_id else "failed",
                )
                await db.messages.insert_one(_gr_doc.model_dump())
            except Exception as _gr_err:
                print(f"WhatsApp greeting send failed: {_gr_err}")
            # Persist the flag — update by phone (set by create_ticket_from_whatsapp)
            await db.customers.update_one(
                {"phone": from_phone},
                {"$set": {"wa_greeted": True}},
            )
            # Skip AI reply this turn — resume normal flow on user's next message
            continue

        # Auto-reply via AI Sales Agent for every inbound customer message
        if body:
            try:
                from app.services.whatsapp_ai_agent import process_whatsapp_message
                from app.models.message import MessageInDB as _MsgInDB

                ticket_id = ticket_doc.get("id", "")
                if ticket_id:
                    ai_result = await process_whatsapp_message(
                        ticket_id=ticket_id,
                        phone_number_id=phone_number_id,
                        customer_phone=from_phone,
                        current_message=body,
                        merchant_id=merchant_id,
                        customer_name=contact_name,
                    )
                    if ai_result:
                        wa_config = await get_whatsapp_config(merchant_id)
                        # ai_result is {"reply": str, "buttons": list, "image_url": str}
                        reply_text = (ai_result.get("reply", "") if isinstance(ai_result, dict) else str(ai_result)).strip()
                        buttons    = (ai_result.get("buttons") or []) if isinstance(ai_result, dict) else []
                        image_url  = (ai_result.get("image_url") or "") if isinstance(ai_result, dict) else ""

                        if not reply_text:
                            continue

                        if image_url and buttons:
                            wa_result = await send_image_with_buttons(from_phone, image_url, reply_text, buttons, wa_config)
                        elif image_url:
                            wa_result = await send_media_message(from_phone, "image", image_url, reply_text, wa_config)
                        elif buttons:
                            wa_result = await send_interactive_buttons(from_phone, reply_text, buttons, wa_config)
                        else:
                            wa_result = await send_text_message(from_phone, reply_text, wa_config)

                        messages_list = wa_result.get("messages") or []
                        sent_id = messages_list[0].get("id") if messages_list else None
                        wa_status = "sent" if sent_id else "failed"
                        if not sent_id:
                            send_error = wa_result.get("error") or wa_result.get("detail") or str(wa_result)
                            print(
                                f"[WhatsApp] AI reply NOT delivered\n"
                                f"  to={from_phone}\n"
                                f"  error={send_error}\n"
                                f"  config phone_number_id={wa_config.get('phone_number_id')}\n"
                                f"  token_set={bool(wa_config.get('access_token'))}"
                            )
                        reply_msg = _MsgInDB(
                            ticket_id=ticket_id,
                            body=reply_text,
                            sender_type="agent",
                            channel="whatsapp",
                            ai_generated=True,
                            whatsapp_message_id=sent_id,
                            whatsapp_status=wa_status,
                        )
                        await db.messages.insert_one(reply_msg.model_dump())

                        # Stamp first_response_at if this is the first agent reply
                        if not ticket_doc.get("first_response_at"):
                            from datetime import datetime, timezone
                            now = datetime.now(timezone.utc)
                            ticket_updates = {"first_response_at": now, "updated_at": now}
                            first_response_due = ticket_doc.get("first_response_due_at")
                            if first_response_due:
                                ticket_updates["first_response_sla_status"] = "met" if now <= first_response_due else "breached"
                            else:
                                ticket_updates["first_response_sla_status"] = "met"
                            await db.tickets.update_one(
                                {"id": ticket_id},
                                {"$set": ticket_updates},
                            )
            except Exception as _ai_err:
                print(f"WhatsApp AI agent auto-reply failed: {_ai_err}")


async def _handle_statuses(value: dict):
    """Process message delivery status updates (sent/delivered/read/failed)."""
    db = get_db()
    statuses = value.get("statuses", [])

    for status in statuses:
        wa_message_id = status.get("id", "")
        status_value = status.get("status", "")  # sent, delivered, read, failed

        if wa_message_id:
            await db.messages.update_one(
                {"whatsapp_message_id": wa_message_id},
                {"$set": {"whatsapp_status": status_value}},
            )

            # Log failures
            if status_value == "failed":
                errors = status.get("errors", [])
                error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
                print(f"WhatsApp message {wa_message_id} failed: {error_msg}")
