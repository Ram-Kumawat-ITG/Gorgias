# Implementation Plan: Omnichannel Order Actions, Cancel Retention & Gift Card System

**Design Spec:** `2026-04-01-omnichannel-order-cancel-retention-giftcard-design.md`  
**Date:** 2026-04-01

---

## Step 1: Ticket System Audit Fixes (F6)

### 1.1 Add orders/cancelled webhook handler
- **File:** `backend/app/routers/webhooks.py`
- Add `POST /webhooks/orders/cancelled` endpoint
- When Shopify sends cancellation webhook:
  - Update `order_snapshots` with `cancelled_at` and `cancel_reason`
  - Find ticket linked to this order (`shopify_order_id`) and update status/add note
  - Log activity

### 1.2 Add orders/updated webhook handler
- **File:** `backend/app/routers/webhooks.py`
- Add `POST /webhooks/orders/updated` endpoint
- Update `order_snapshots` collection with latest order data
- If ticket linked, refresh order data on ticket

### 1.3 Add retention metadata to ticket model
- **File:** `backend/app/models/ticket.py`
- Add fields: `retention_offered`, `retention_accepted`, `retention_offered_at`, `cancel_requested_order_id`

### Verification:
- Read webhook handlers and confirm they follow existing patterns
- Confirm ticket model changes don't break existing ticket creation

---

## Step 2: Remove Extra Order Actions — Cancel Only (F1)

### 2.1 WhatsApp — Remove refund/replacement buttons
- **File:** `backend/app/services/whatsapp_ai_agent.py`
- In the interactive buttons section (~line 449-459): remove `refund_{order_id}` and `replace_{order_id}` buttons
- Keep only `cancel_{order_id}` → "Cancel Order"
- Remove `_add_order_note()` function and refund/replacement handlers from `_execute_action()`
- Update system prompt: remove "request_refund" and "request_replacement" from action list

### 2.2 Instagram — Remove non-cancel actions
- **File:** `backend/app/services/instagram_sales_agent_service.py`
- Update system prompt: remove update_order action, keep only cancel_order for order modifications
- Keep: product search, order lookup, order creation, cancel

### 2.3 Update AI system prompts
- WhatsApp: Remove refund/replacement actions from JSON schema
- Instagram: Remove update_order action
- Both: Emphasize cancel-only for order modifications

### Verification:
- Review updated system prompts
- Confirm only cancel action remains in button/action lists

---

## Step 3: Create Shared Order Service

### 3.1 Create `backend/app/services/order_service.py`
- `lookup_order_by_number(order_number, customer_email=None)` — calls Shopify `/orders.json?name=#{number}&status=any`
- `lookup_order_by_email(email, limit=1)` — calls Shopify `/orders.json?email={email}&limit={limit}&status=any`
- `lookup_order_by_id(order_id)` — calls Shopify `/orders/{order_id}.json`
- `cancel_order(order_id)` — calls Shopify `POST /orders/{order_id}/cancel.json`
- `format_order_details_text(order)` — plain text format (for Instagram/Email)
- `format_order_details_whatsapp(order)` — markdown format with emojis (for WhatsApp)
- `get_order_status_with_ticket_context(customer_email, order_number=None)` — combines ticket + Shopify data

### 3.2 Refactor WhatsApp agent to use shared service
- **File:** `backend/app/services/whatsapp_ai_agent.py`
- Replace inline `_fetch_order_by_number()`, `_fetch_order_by_email()`, `_cancel_order()` with calls to `order_service.py`
- Keep WhatsApp-specific formatting and interactive button logic

### 3.3 Refactor Instagram agent to use shared service
- **File:** `backend/app/services/instagram_sales_agent_service.py`
- Replace `_shopify_get_orders()`, `_shopify_cancel_order()` with calls to `order_service.py`
- Keep Instagram-specific conversation flow

### Verification:
- Confirm shared service functions match existing Shopify API call patterns
- Verify WhatsApp and Instagram still work after refactor

---

## Step 4: Email AI Agent + Instagram Refinement (F2)

### 4.1 Create `backend/app/services/email_ai_agent.py`
- Model: Groq `llama-3.1-8b-instant` (same as WhatsApp)
- System prompt: email-specific persona (professional, helpful)
- JSON response schema: `{action, email, order_number, order_id, message}`
- Actions: fetch_order, cancel_order, check_inventory, none
- Conversation context: last 10 messages from ticket
- Order context: from shared `order_service.py`
- `process_email_message(ticket_id, customer_email, current_message)` → returns reply string

### 4.2 Wire email AI agent into inbound flow
- **File:** `backend/app/routers/email_inbound.py`
- After `create_ticket_from_email()`, call `process_email_message()`
- Send auto-reply via `send_reply_email()`
- Store AI reply as message with `sender_type: "ai"`, `ai_generated: True`

### 4.3 Instagram order display refinement
- **File:** `backend/app/services/instagram_sales_agent_service.py`
- Ensure order format matches shared service output
- Verify cancel-only flow works end-to-end

### Verification:
- Confirm email AI agent returns valid responses
- Confirm email auto-reply is sent via Mailgun
- Confirm Instagram order flow consistency

---

## Step 5: Ticket-Based Order Status Reply (F3)

### 5.1 Add `get_order_status_with_ticket_context()` to order service
- **File:** `backend/app/services/order_service.py`
- Query: find open/pending ticket for customer
- If ticket has order_id → fetch live Shopify status
- If ticket is open/in_progress → add "team is working on it" context
- If no ticket → return just Shopify order data
- Return structured response with ticket context + order data

### 5.2 Integrate into all 3 channel agents
- WhatsApp: when `action == "fetch_order"`, call `get_order_status_with_ticket_context()`
- Instagram: same integration
- Email: same integration
- Response includes ticket status context when relevant

### Verification:
- Test: customer with open ticket asking order status → gets ticket-aware reply
- Test: customer without ticket → gets order status + new ticket created

---

## Step 6: Cancel Retention System (F4)

### 6.1 Create `backend/app/services/retention_service.py`
- `RETENTION_CONFIG` dict with configurable amounts
- `detect_cancel_intent(message)` → keyword matching for cancel intent
- `check_retention_attempted(ticket_id)` → check `retention_offered` flag on ticket
- `create_or_update_cancel_ticket(customer_email, order_id, channel, ticket_id=None)` → set `ticket_type="cancel_requested"`, link order
- `get_retention_offer_message()` → return non-pushy retention message
- `process_retention_response(ticket_id, accepted)`:
  - If accepted → create gift card offer (DB), resolve ticket
  - If declined → escalate to admin, keep ticket open

### 6.2 Integrate retention into WhatsApp agent
- **File:** `backend/app/services/whatsapp_ai_agent.py`
- When `action == "cancel_order"`:
  - Check if retention already offered for this ticket
  - If not → send retention offer, set `retention_offered=True`
  - If yes and customer says NO → escalate
  - If yes and customer says YES → create gift card offer

### 6.3 Integrate retention into Instagram agent
- **File:** `backend/app/services/instagram_sales_agent_service.py`
- Same retention flow as WhatsApp (text-based, no buttons)

### 6.4 Integrate retention into Email agent
- **File:** `backend/app/services/email_ai_agent.py`
- Same retention flow

### Verification:
- Test: cancel request → retention offer sent (not cancel)
- Test: retention YES → gift card created, ticket resolved
- Test: retention NO → admin notified, ticket stays open
- Test: second cancel on same ticket → no duplicate retention

---

## Step 7: Gift Card — Bot Auto-Offer (F5A)

### 7.1 Create gift card model
- **File:** `backend/app/models/gift_card.py`
- Fields: id, customer_id, customer_email, code, amount, type, status, assigned_by, assigned_at, approved_at, used_at, expires_at, channel, ticket_id, shopify_price_rule_id, shopify_discount_code_id, merchant_id

### 7.2 Create gift card service
- **File:** `backend/app/services/gift_card_service.py`
- `create_gift_card_offer(customer_id, customer_email, amount, type, channel, ticket_id)` → insert to DB with status=pending
- `generate_discount_code(gift_card_id)` → Shopify Price Rules API:
  - `POST /price_rules.json` → create rule
  - `POST /price_rules/{id}/discount_codes.json` → create code
  - Update gift card record with code + shopify IDs
- `notify_customer(gift_card_id)` → send code via appropriate channel

### 7.3 Add gift_cards collection indexes
- **File:** `backend/app/database.py`
- Indexes: (customer_id), (status), (customer_email), (code unique sparse)

### 7.4 Wire into retention flow
- **File:** `backend/app/services/retention_service.py`
- When customer accepts retention → call `create_gift_card_offer()` with type="retention"

### Verification:
- Test: retention accepted → gift card record created in DB
- Test: gift card status is "pending" until admin approves

---

## Step 8: Gift Card — Admin Manual (F5B)

### 8.1 Create gift card router
- **File:** `backend/app/routers/gift_cards.py`
- `GET /gift-cards` — list all, with status/type filters
- `GET /gift-cards/{id}` — get details
- `POST /gift-cards` — create manual gift card (admin assigns)
- `POST /gift-cards/{id}/approve` — approve + generate Shopify discount code
- `POST /gift-cards/{id}/notify` — send to customer via their channel
- `DELETE /gift-cards/{id}` — revoke

### 8.2 Register router
- **File:** `backend/app/main.py`
- Add `from app.routers import gift_cards` and `app.include_router(gift_cards.router, ...)`

### 8.3 Create frontend Gift Card page
- **File:** `frontend/src/pages/GiftCardPage.jsx`
- Table listing all gift cards with status badges
- Filters: status (pending/active/used/expired), type (retention/manual)
- "Assign Gift Card" button → modal: select customer, amount, type
- "Approve" action for pending cards
- "Notify" action for active cards
- "Revoke" action

### 8.4 Add navigation
- **File:** `frontend/src/components/Sidebar.jsx` (or Layout.jsx)
- Add "Gift Cards" link in sidebar nav
- **File:** `frontend/src/App.jsx`
- Add `/gift-cards` route pointing to GiftCardPage

### Verification:
- Test: admin creates manual gift card → record in DB
- Test: admin approves → Shopify discount code created
- Test: admin notifies → customer receives code via channel
- Test: frontend page renders correctly with all actions
