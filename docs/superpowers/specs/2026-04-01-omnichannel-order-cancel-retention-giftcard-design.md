# Design Spec: Omnichannel Order Actions, Cancel Retention & Gift Card System

**Date:** 2026-04-01  
**Status:** Approved  
**Scope:** 6 features across WhatsApp, Instagram, Email channels

---

## 1. Feature Overview

| # | Feature | Summary |
|---|---------|---------|
| F1 | Cancel-Only Actions | Remove refund/replacement buttons, keep only Cancel across all channels |
| F2 | Omnichannel Order Integration | Bring order lookup + cancel to Instagram and Email (autonomous AI) |
| F3 | Ticket-Based Order Status Reply | Bot checks ticket + Shopify data when customer asks "where is my order" |
| F4 | Cancel Retention System | Intercept cancel requests with gift card/discount offer before proceeding |
| F5 | Gift Card System | Bot auto-offer (retention) + Admin manual assignment |
| F6 | Ticket System Audit | Verify ticket flows work correctly before building new features |

---

## 2. Current System Analysis

### 2A. WhatsApp Order Flow (Current)
- `whatsapp_ai_agent.py` — Groq/Llama AI agent processes messages
- Detects order queries via AI intent classification
- Looks up orders via Shopify REST API (by order number, order ID, or email)
- Displays order details with 3 interactive buttons: Cancel, Refund, Replacement
- Cancel calls `POST /orders/{id}/cancel.json` directly
- Refund/Replacement add order notes with tags (manual agent follow-up)

### 2B. Instagram Order Flow (Current)
- `instagram_sales_agent_service.py` — Groq AI agent
- Has order lookup (`_shopify_get_orders`) and cancel (`_shopify_cancel_order`)
- Text-based responses (no interactive buttons — Instagram API limitation)
- Also supports product search, order creation, customer lookup

### 2C. Email Order Flow (Current)
- NO autonomous AI agent — only manual `generate_reply_suggestion()` for agents
- Order data stored as snapshot at ticket creation time
- Agent must manually approve and send replies via Mailgun
- **Gap: Needs full autonomous AI agent like WhatsApp/Instagram**

### 2D. Shopify Gift Card / Discount Code API
- Current codebase uses REST Admin API 2024-01
- Gift cards: NOT available via REST — requires GraphQL Admin API
- Discount codes: Price Rules API exists in REST but not implemented
- **Decision: Use Shopify REST Price Rules + Discount Codes API for discount codes; store gift card offers in DB until admin approves via Shopify admin**

---

## 3. Architecture Design

### 3A. Shared Order Service (NEW)

Create `backend/app/services/order_service.py` — a channel-agnostic service that all 3 channels use:

```
order_service.py
├── lookup_order_by_number(order_number, customer_email=None) -> dict
├── lookup_order_by_email(email) -> dict
├── lookup_order_by_id(order_id) -> dict
├── cancel_order(order_id) -> dict
├── format_order_details(order_data) -> str
├── detect_order_intent(message) -> str  # "order_status", "cancel", None
└── get_cancel_only_actions(order_id) -> list  # returns only cancel action
```

All channels call this service instead of duplicating Shopify API logic.

### 3B. Shared Retention Service (NEW)

Create `backend/app/services/retention_service.py`:

```
retention_service.py
├── detect_cancel_intent(message) -> bool
├── check_retention_attempted(ticket_id) -> bool
├── create_cancel_ticket(customer_email, order_id, channel) -> dict
├── send_retention_offer(ticket_id, channel) -> str  # returns offer message
├── process_retention_response(ticket_id, accepted: bool) -> str
└── RETENTION_CONFIG  # configurable constants
```

### 3C. Gift Card Service (NEW)

Create `backend/app/services/gift_card_service.py`:

```
gift_card_service.py
├── create_gift_card_offer(customer_id, amount, type, channel) -> dict
├── approve_gift_card(gift_card_id) -> dict  # generates Shopify discount code
├── generate_discount_code(amount, type) -> str  # Shopify Price Rules API
├── notify_customer(gift_card_id) -> bool  # send via customer's channel
├── get_customer_gift_cards(customer_id) -> list
└── GIFT_CARD_CONFIG  # configurable constants
```

### 3D. Email AI Agent (NEW)

Create `backend/app/services/email_ai_agent.py` — mirrors WhatsApp/Instagram agents:

```
email_ai_agent.py
├── process_email_message(ticket_id, customer_email, message) -> str
├── _build_conversation_context(ticket_id) -> list
├── _execute_action(action, params) -> str
└── System prompt with email-specific persona
```

### 3E. Channel Response Flow (Updated)

```
Customer Message (any channel)
    ↓
Channel Router (whatsapp.py / instagram.py / email_inbound.py)
    ↓
Ticket Service (create/update ticket)
    ↓
Shared Order Service (order lookup, cancel)
    ↓
Retention Service (if cancel detected)
    ↓
Channel-specific AI Agent (format response for channel)
    ↓
Channel-specific Send (WhatsApp buttons / Instagram text / Email reply)
```

---

## 4. Feature Specifications

### F1: Cancel-Only Actions

**WhatsApp changes (`whatsapp_ai_agent.py`):**
- Remove `refund_{order_id}` and `replace_{order_id}` buttons from interactive payload
- Keep only `cancel_{order_id}` button
- Remove `request_refund` and `request_replacement` action handlers
- Update system prompt to remove refund/replacement actions

**Instagram changes (`instagram_sales_agent_service.py`):**
- Remove `cancel_order` action that does immediate cancellation
- Replace with retention-aware cancel flow (F4)
- Keep order lookup intact

**Email changes:**
- New email AI agent will only have cancel action from the start

**System prompt updates (all channels):**
- Remove: "request_refund", "request_replacement" from available actions
- Keep: "cancel_order", "fetch_order", "check_inventory", etc.

### F2: Omnichannel Order Integration

**Instagram (already has order lookup, needs refinement):**
- Verify `_shopify_get_orders()` works correctly
- Ensure order display format matches WhatsApp
- Use shared `order_service.py` for consistency

**Email (new autonomous AI agent):**
- Create `email_ai_agent.py` with Groq/Llama integration
- Auto-reply on inbound email (trigger in `email_inbound.py`)
- Order lookup by customer email (reliable — real email, not placeholder)
- Format order details for email (plain text, no buttons)
- Cancel-only action

**Trigger point in `email_inbound.py`:**
```python
# After ticket creation, auto-reply:
reply = await process_email_message(ticket_id, customer_email, body)
if reply:
    await send_reply_email(to=customer_email, subject=f"Re: {subject}", body=reply, ticket_id=ticket_id)
```

### F3: Ticket-Based Order Status Reply

**Flow for "where is my order" queries (all channels):**

1. Customer sends order status query
2. AI detects `order_status` intent
3. Check for existing ticket with `shopify_order_id`:
   - If ticket exists and is `open`/`in_progress` → "Your order is being processed, our team is on it"
   - If ticket has `shopify_order_id` → fetch live status from Shopify API
   - If no ticket → create new ticket + fetch order status
4. Reply with combined ticket + Shopify data

**Implementation in shared `order_service.py`:**
```python
async def get_order_status_with_ticket_context(customer_email, order_number=None):
    # 1. Find existing ticket
    ticket = await db.tickets.find_one({
        "customer_email": customer_email,
        "status": {"$in": ["open", "pending", "in_progress"]}
    })
    
    # 2. Get live order data
    order = await lookup_order_by_email(customer_email) or
            await lookup_order_by_number(order_number)
    
    # 3. Build contextual response
    return {"ticket": ticket, "order": order, "message": format_status_reply(ticket, order)}
```

### F4: Cancel Retention System

**Constants (`retention_service.py`):**
```python
RETENTION_CONFIG = {
    "gift_card_amount": 500,        # in cents ($5.00)
    "discount_percentage": 10,       # 10% off next order
    "max_retention_attempts": 1,     # only 1 attempt per cancel request
    "currency": "INR",               # or from Shopify store settings
}
```

**Flow:**
```
Customer: "I want to cancel my order"
    ↓
detect_cancel_intent(message) → True
    ↓
check_retention_attempted(ticket_id) → False (first time)
    ↓
create_cancel_ticket(customer_email, order_id, channel)
  → Creates ticket with ticket_type="cancel_requested"
  → Links to order
    ↓
send_retention_offer(ticket_id, channel)
  → Returns retention message (not pushy)
  → Sets ticket metadata: retention_offered=True
    ↓
[Wait for customer response]
    ↓
Customer replies YES → process_retention_response(ticket_id, accepted=True)
  → Create gift card offer in DB (status: pending_admin_approval)
  → Reply: "Great! We'll set up your gift card shortly."
  → Update ticket status: resolved
    ↓
Customer replies NO → process_retention_response(ticket_id, accepted=False)
  → Escalate to admin (assign ticket, set priority: high)
  → Reply: "We understand. Our team will process your cancellation shortly."
  → Do NOT auto-cancel — admin handles it
```

**Retention message template:**
```
We're sorry to hear you'd like to cancel your order.
Before we proceed, we'd love to make it right for you.

We can offer you:
- A Gift Card worth $5.00
- A 10% Discount on your next order

Would you like to accept this offer instead?
Reply YES to accept or NO to proceed with cancellation.
```

**Ticket metadata fields (added to ticket model):**
```python
retention_offered: bool = False
retention_accepted: Optional[bool] = None
retention_offered_at: Optional[datetime] = None
cancel_requested_order_id: Optional[str] = None
```

### F5: Gift Card System

**Mode A — Bot Auto-Offer (Cancel Retention):**
- During retention flow, bot offers gift card
- Gift card record created in DB with `status: "pending"`
- NOT generated until admin approves
- Admin sees pending gift cards in dashboard

**Mode B — Admin Manual Gift Card:**
- Admin dashboard page to assign gift cards
- Select customer → set amount → generate code
- Uses Shopify Price Rules API to create discount code:
  ```
  POST /price_rules.json → creates rule
  POST /price_rules/{id}/discount_codes.json → creates code
  ```
- Customer notified via their channel (WhatsApp/Instagram/Email)

**Gift Card DB Model (`backend/app/models/gift_card.py`):**
```python
class GiftCardInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    customer_id: str
    customer_email: str
    code: Optional[str] = None          # generated on approval
    amount: float                        # in store currency
    type: str                           # "retention" or "manual"
    status: str = "pending"             # pending, active, used, expired
    assigned_by: str                    # "bot" or agent_id
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    channel: str                        # whatsapp, instagram, email
    ticket_id: Optional[str] = None     # linked ticket (for retention)
    shopify_price_rule_id: Optional[str] = None
    shopify_discount_code_id: Optional[str] = None
    merchant_id: Optional[str] = None
```

**Gift Card Router (`backend/app/routers/gift_cards.py`):**
```
GET    /gift-cards                  → list all gift cards (admin)
GET    /gift-cards/{id}             → get single gift card
POST   /gift-cards                  → create manual gift card (admin)
POST   /gift-cards/{id}/approve     → approve & generate Shopify discount code
POST   /gift-cards/{id}/notify      → send notification to customer
DELETE /gift-cards/{id}             → revoke gift card
```

**Frontend — Gift Card Admin Page (`GiftCardPage.jsx`):**
- Table of all gift cards with status filters
- "Assign Gift Card" modal: select customer, set amount, choose type
- "Approve" button for pending retention gift cards
- Status badges: pending (yellow), active (green), used (gray), expired (red)

### F6: Ticket System Audit

**Audit items and findings from code review:**

| Check | Status | Notes |
|-------|--------|-------|
| Ticket creation — WhatsApp | OK | `create_ticket_from_whatsapp()` works correctly |
| Ticket creation — Instagram | OK | `create_ticket_from_instagram()` works correctly |
| Ticket creation — Email | OK | `create_ticket_from_email()` works correctly |
| Order created → ticket created | PARTIAL | Webhook stores snapshot but does NOT create ticket |
| Order cancelled → ticket updated | MISSING | No webhook handler for `orders/cancelled` |
| Order updated → ticket reflects | MISSING | No webhook handler for `orders/updated` |
| Bot replies linked to correct ticket | OK | All channels use ticket_id consistently |
| Messages appended correctly | OK | Existing ticket lookup by phone/IGSID/email works |
| Status transitions | OK | Manual, no state machine enforcement |
| Admin assignment | OK | Via `assignee_id` field |
| Duplicate tickets | LOW RISK | Race condition possible but unlikely |

**Issues to fix:**
1. Add `orders/cancelled` webhook handler → update linked ticket
2. Add `orders/updated` webhook handler → update order snapshot
3. Ensure order snapshot refreshes when ticket is viewed (not just at creation)

---

## 5. Files Changed / Created

### New Files
| File | Purpose |
|------|---------|
| `backend/app/services/order_service.py` | Shared order lookup, cancel, format |
| `backend/app/services/retention_service.py` | Cancel retention flow |
| `backend/app/services/gift_card_service.py` | Gift card CRUD + Shopify discount codes |
| `backend/app/services/email_ai_agent.py` | Autonomous email AI agent |
| `backend/app/models/gift_card.py` | Gift card DB model |
| `backend/app/routers/gift_cards.py` | Gift card admin endpoints |
| `frontend/src/pages/GiftCardPage.jsx` | Admin gift card management UI |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/services/whatsapp_ai_agent.py` | Remove refund/replacement, use shared order service, add retention flow |
| `backend/app/services/instagram_sales_agent_service.py` | Use shared order service, add retention flow, cancel-only |
| `backend/app/routers/email_inbound.py` | Add auto-reply trigger |
| `backend/app/routers/whatsapp.py` | Minor: handle retention responses |
| `backend/app/routers/webhooks.py` | Add orders/cancelled and orders/updated handlers |
| `backend/app/models/ticket.py` | Add retention metadata fields |
| `backend/app/database.py` | Add gift_cards collection indexes |
| `backend/app/main.py` | Register gift_cards router |
| `frontend/src/App.jsx` | Add GiftCardPage route |
| `frontend/src/components/Sidebar.jsx` | Add Gift Cards nav link |

---

## 6. Implementation Order

| Step | Feature | Dependencies |
|------|---------|-------------|
| 1 | Ticket audit fixes (F6) | None |
| 2 | Remove extra order actions (F1) | None |
| 3 | Shared order service | F1 |
| 4 | Email AI agent + Instagram refinement (F2) | F3 shared service |
| 5 | Ticket-based order status reply (F3) | F2, shared service |
| 6 | Cancel retention system (F4) | F3, shared service |
| 7 | Gift card — bot auto-offer (F5A) | F4 |
| 8 | Gift card — admin manual (F5B) | F5A model exists |

---

## 7. Flow Diagrams

### Cancel Retention Flow
```
Customer: "cancel my order"
    → AI detects cancel intent
    → Check: retention already offered for this ticket?
        → YES: escalate to admin immediately
        → NO: continue
    → Create/update ticket with type="cancel_requested"
    → Send retention offer message
    → Wait for response
        → "YES" / accept:
            → Create gift card offer (DB, status=pending)
            → Reply: "Gift card is being prepared"
            → Ticket status → resolved
        → "NO" / decline:
            → Assign to admin, priority=high
            → Reply: "Team will process cancellation"
            → Ticket stays open for admin
```

### Order Status Query Flow
```
Customer: "where is my order"
    → AI detects order_status intent
    → Extract order number (if provided)
    → Check existing ticket for this customer
        → Has open ticket with order_id?
            → Fetch live Shopify status
            → Reply with status + ticket context
        → No ticket?
            → Lookup order by email/number
            → Create new ticket
            → Reply with order status
    → Show cancel-only option
```

### Admin Gift Card Flow
```
Admin opens Gift Card page
    → Sees list of all gift cards (pending/active/used)
    → Click "Assign Gift Card"
        → Select customer
        → Set amount
        → Submit → creates gift_card record (status=pending)
    → Click "Approve" on pending card
        → System creates Shopify Price Rule + Discount Code
        → Gift card status → active
        → Code stored on gift_card record
    → Click "Notify Customer"
        → Sends discount code via customer's channel
        → WhatsApp: text message with code
        → Instagram: DM with code
        → Email: email with code
```
