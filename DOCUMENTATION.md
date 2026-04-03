# Gorgias Helpdesk — Complete Technical Documentation

> **Version:** 2.0.0 | **Last Updated:** 2026-04-03 | **Status:** Production

---

## 1. Project Overview

A full-stack, multi-channel customer support helpdesk for Shopify merchants. Support agents manage tickets, view customer/order data, get AI-suggested replies, and track SLA compliance across **WhatsApp**, **Email**, **Instagram DMs**, and manual channels.

### Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · FastAPI · Uvicorn |
| Database | MongoDB (async via Motor) |
| Frontend | React 18 · Vite 5 · Tailwind CSS 3 |
| AI/LLM | Groq (Llama 3.1 8B) · OpenAI · Gemini |
| E-commerce | Shopify REST Admin API |
| Email | Mailgun |
| Messaging | Meta WhatsApp Cloud API · Meta Instagram Messenger API |
| Deployment | Render.com (backend + frontend static) |
| Auth | JWT (python-jose + passlib/bcrypt) |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                       │
│  InboxPage · RequestPage · TicketDetailPage · OrdersPage · etc.     │
│  ─────────────────── Axios (JWT) ───────────────────────────────────│
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTP (REST JSON)
┌────────────────────────────────▼────────────────────────────────────┐
│                     BACKEND (FastAPI + Uvicorn)                      │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐│
│  │ Routers  │  │ Services │  │ Models   │  │ Middleware           ││
│  │ (20)     │→ │ (20)     │→ │ (12)     │  │ · CORS              ││
│  │          │  │          │  │          │  │ · Shopify HMAC       ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────────┘│
│                      │              │                                │
│            ┌─────────┴──────────────┴──────────┐                    │
│            ▼                                    ▼                    │
│  ┌──────────────────┐               ┌──────────────────────┐       │
│  │    MongoDB        │               │  External APIs       │       │
│  │  · tickets        │               │  · Shopify REST      │       │
│  │  · messages       │               │  · Groq / OpenAI     │       │
│  │  · customers      │               │  · Mailgun           │       │
│  │  · returns        │               │  · WhatsApp Cloud    │       │
│  │  · merchants      │               │  · Instagram Messenger│      │
│  │  · automation_rules│              │  · Twitter/X         │       │
│  │  · gift_cards     │               └──────────────────────┘       │
│  │  · activity_logs  │                                              │
│  │  · sla_policies   │                                              │
│  │  · order_snapshots│                                              │
│  └──────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘

INBOUND WEBHOOKS:
  Meta → POST /webhooks/whatsapp     (customer WhatsApp messages)
  Meta → POST /webhooks/instagram    (customer Instagram DMs)
  Mailgun → POST /webhooks/email/inbound (customer emails)
  Shopify → POST /webhooks/orders/*  (order create/fulfill/cancel)
```

---

## 3. Module Breakdown

### Backend Modules

| Module | Router Prefix | Purpose |
|---|---|---|
| **Tickets** | `/tickets` | CRUD + message threads for support tickets |
| **Customers** | `/customers` | Customer profiles synced with Shopify |
| **Orders** | `/orders` | Shopify order management, draft orders, fulfillment |
| **Returns** | `/returns` | Return/refund/replacement request lifecycle |
| **AI** | `/ai` | AI suggestions, conversation analysis, autonomous processing |
| **WhatsApp** | `/webhooks/whatsapp` | Meta webhook verification + inbound message processing |
| **Instagram** | `/webhooks/instagram` | Meta webhook verification + inbound DM processing |
| **Email** | `/webhooks/email` | Mailgun inbound email processing |
| **Shopify Webhooks** | `/webhooks` | Order created/fulfilled/cancelled events |
| **Macros** | `/macros` | Canned response templates with variable interpolation |
| **Automations** | `/automations` | Event-driven if-then rules |
| **Analytics** | `/analytics` | Dashboard stats (volume, SLA, channels, response times) |
| **SLA** | `/sla` | Manual SLA breach checking |
| **SLA Policies** | `/sla-policies` | CRUD for SLA policies per priority |
| **History** | `/history` | Activity timelines for customers, tickets, orders |
| **Channels** | `/channels` | Channel listing for filter tabs |
| **Merchants** | `/merchants` | Multi-merchant config (WhatsApp/Instagram/Email creds) |
| **Gift Cards** | `/gift-cards` | Shopify gift card assignment & distribution |
| **Media** | `/media` | Proxy for WhatsApp/Instagram media (auth-gated by Meta) |
| **Shopify Sync** | `/shopify` | Bulk order sync from Shopify |

### Frontend Pages

| Page | Route | Purpose |
|---|---|---|
| **InboxPage** | `/` | Main ticket list with status/channel/type filters |
| **TicketDetailPage** | `/tickets/:id` | Message thread, reply composer, admin actions |
| **RequestPage** | `/requests` | AI-powered request view with Shopify sidebar, auto-analysis |
| **CustomersPage** | `/customers` | Customer list + create |
| **CustomerDetailPage** | `/customers/:id` | Profile, orders, tickets, gift cards |
| **OrdersPage** | `/orders` | Order list + draft orders |
| **OrderDetailPage** | `/orders/:id` | Order details, fulfill, refund, cancel, initiate return |
| **ReturnsPage** | `/returns` | Returns list with status filters + stats |
| **ReturnDetailPage** | `/returns/:id` | Return timeline, approve/reject, tracking |
| **AnalyticsPage** | `/analytics` | Charts: daily volume, status distribution, channels |
| **SLAPage** | `/sla` | SLA compliance dashboard with ticket table |
| **SLAPoliciesPage** | `/sla-policies` | Create/edit SLA policies |
| **MacrosPage** | `/macros` | Canned response management |
| **AutomationsPage** | `/automations` | Automation rule builder |
| **GiftCardPage** | `/gift-cards` | Gift card assignment + history |
| **WhatsAppSettingsPage** | `/whatsapp-settings` | WhatsApp API configuration |
| **InstagramSettingsPage** | `/instagram-settings` | Instagram API configuration |
| **EmailSettingsPage** | `/email-settings` | Mailgun configuration |

---

## 4. API Documentation

### 4.1 Authentication

#### POST /auth/login

Login with email and password.

**Request:**
```json
{
  "email": "admin@yourstore.com",
  "password": "change-this-password"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "agent": {
    "id": "uuid",
    "email": "admin@yourstore.com",
    "full_name": "Admin",
    "role": "admin"
  }
}
```

**Headers (all authenticated endpoints):**
```
Authorization: Bearer <access_token>
```

---

### 4.2 Tickets

#### GET /tickets

List tickets with filters.

| Param | Type | Default | Description |
|---|---|---|---|
| `status` | string | `"active"` | `active` (open+pending+pending_admin_action), `open`, `pending`, `resolved`, `closed`, or empty for all |
| `channel` | string | — | `whatsapp`, `email`, `instagram`, `manual`, `shopify` |
| `ticket_type` | string | — | `refund`, `return`, `cancel_requested`, etc. |
| `search` | string | — | Search by subject or customer email |
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Results per page |

**Response:**
```json
{
  "tickets": [
    {
      "id": "uuid",
      "subject": "WhatsApp: John",
      "customer_email": "john@email.com",
      "customer_name": "John Doe",
      "channel": "whatsapp",
      "status": "pending_admin_action",
      "priority": "normal",
      "ticket_type": "refund",
      "pending_action_type": "refund",
      "pending_action_order_number": "1042",
      "pending_action_issue": "damaged",
      "created_at": "2026-04-03T01:44:00Z",
      "updated_at": "2026-04-03T01:45:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "limit": 20
}
```

#### POST /tickets

Create a manual ticket.

**Request:**
```json
{
  "subject": "Customer issue with order",
  "customer_email": "customer@email.com",
  "customer_name": "Jane",
  "channel": "manual",
  "priority": "high",
  "initial_message": "Customer reports damaged item"
}
```

#### GET /tickets/{ticket_id}

Get full ticket document (all fields including pending_action_*, SLA, Shopify links).

#### PATCH /tickets/{ticket_id}

Update ticket fields.

**Request:**
```json
{
  "status": "resolved",
  "priority": "urgent",
  "ticket_type": "refund",
  "assignee_id": "agent-uuid",
  "tags": ["vip", "urgent"]
}
```

#### GET /tickets/{ticket_id}/messages

Get all messages in a ticket thread (sorted by created_at ascending).

**Response:**
```json
[
  {
    "id": "uuid",
    "ticket_id": "ticket-uuid",
    "body": "I want a refund for my order",
    "sender_type": "customer",
    "ai_generated": false,
    "channel": "whatsapp",
    "whatsapp_media_id": "meta-media-id",
    "whatsapp_media_url": "https://fbsbx.com/...",
    "whatsapp_media_type": "image",
    "whatsapp_status": "read",
    "created_at": "2026-04-03T01:44:00Z"
  }
]
```

#### POST /tickets/{ticket_id}/messages

Add a message (agent reply or internal note).

**Request:**
```json
{
  "body": "We'll process your refund within 5-7 days.",
  "sender_type": "agent",
  "is_internal_note": false
}
```

---

### 4.3 Orders (Shopify)

#### GET /orders

List Shopify orders.

| Param | Type | Description |
|---|---|---|
| `search` | string | Search by order number or email |
| `limit` | int | Max results (default 50) |
| `status` | string | `any`, `open`, `closed`, `cancelled` |

#### GET /orders/{order_id}

Get full Shopify order (line items, fulfillments, tracking, financial status).

#### POST /orders/{order_id}/cancel

```json
{ "reason": "customer", "restock": true, "email": false }
```

#### POST /orders/{order_id}/refund

```json
{ "custom_amount": "29.99", "note": "Damaged product", "notify": true }
```

#### POST /orders/{order_id}/fulfill

```json
{ "tracking_number": "1Z999AA1...", "tracking_company": "UPS" }
```

#### GET /orders/products/search

Search Shopify products for order creation.

| Param | Type | Description |
|---|---|---|
| `q` | string | Product title search |
| `limit` | int | Max results |
| `since_id` | string | Pagination cursor |

---

### 4.4 Returns

#### POST /returns

Create a return request.

```json
{
  "order_id": "shopify-order-id",
  "items": [
    { "line_item_id": "123", "title": "Blue T-Shirt", "quantity": 1, "price": "29.99" }
  ],
  "reason": "defective",
  "reason_notes": "Zip is broken",
  "resolution": "refund",
  "images": ["https://..."]
}
```

#### POST /returns/{return_id}/status

Update return status (approval workflow).

```json
{ "status": "approved", "note": "Item confirmed defective" }
```

Status flow: `requested → approved → shipped → received → resolved`

#### GET /returns/stats/overview

Returns counts by status for dashboard cards.

---

### 4.5 AI Agent

#### POST /ai/analyze

Analyze a conversation for intent, sentiment, and suggested actions.

**Request:**
```json
{
  "subject": "Order refund request",
  "customer_email": "john@email.com",
  "shopify_order_id": "123456",
  "messages": [
    { "sender": "customer", "message": "I want a refund, product arrived broken" },
    { "sender": "agent", "message": "I'm sorry to hear that. Can you share photos?" }
  ]
}
```

**Response:**
```json
{
  "summary": "Customer requesting refund for damaged product on order #1042",
  "intent": { "primary": "refund_request", "secondary": ["complaint"] },
  "sentiment": { "tone": "frustrated", "urgency": "high", "escalation_risk": true },
  "customer": { "name": "John", "email": "john@email.com" },
  "order": { "order_number": "1042", "amount": "29.99" },
  "issue": { "type": "damaged", "evidence_provided": true },
  "flags": { "possible_fraud": false },
  "actions": [
    {
      "type": "REFUND_ORDER",
      "label": "Process Refund",
      "confidence": 0.92,
      "requires_approval": true,
      "extracted_data": { "order_id": "123456", "reason": "damaged" }
    }
  ],
  "suggested_reply": "I understand your frustration. Let me process that refund for you right away."
}
```

#### POST /ai/process-ticket/{ticket_id}

Autonomous ticket processing. For WhatsApp: runs AI agent → executes Shopify actions → sends reply → saves to thread.

#### POST /ai/approve-action/{ticket_id}

Admin approves a pending request. Triggers Shopify action + multi-channel notification.

**Response:**
```json
{
  "status": "approved",
  "action_type": "refund",
  "shopify_result": "refund_approved",
  "customer_notified": true
}
```

#### POST /ai/reject-action/{ticket_id}

Admin rejects with optional reason. Notifies customer on original channel.

**Request:**
```json
{ "rejection_reason": "Order outside return window" }
```

---

### 4.6 WhatsApp Webhook

#### GET /webhooks/whatsapp

Meta webhook verification (hub.mode, hub.verify_token, hub.challenge).

#### POST /webhooks/whatsapp

Receives inbound messages. Background-processed:
1. Parse message type (text, image, video, interactive button/list reply)
2. Map button/list IDs to natural-language messages for AI
3. Create/update ticket via ticket_service
4. New user → send greeting, skip AI this turn
5. Returning user → run `process_whatsapp_message()` → send interactive reply

---

### 4.7 Instagram Webhook

#### GET /webhooks/instagram

Meta webhook verification.

#### POST /webhooks/instagram

Receives inbound DMs. Similar flow to WhatsApp but uses Instagram Messenger API.

---

### 4.8 Email Webhook

#### POST /webhooks/email/inbound

Mailgun inbound email. Creates/updates ticket from email body.

---

### 4.9 Gift Cards

#### POST /gift-cards/assign

Assign a Shopify gift card to a customer and notify them.

```json
{
  "shopify_gift_card_id": "123",
  "code": "GIFT-ABC123",
  "balance": "500.00",
  "currency": "INR",
  "customer_email": "customer@email.com",
  "channels": ["email", "whatsapp"],
  "ticket_id": "ticket-uuid"
}
```

#### GET /gift-cards/shopify

List Shopify gift cards (with status filter: enabled/disabled).

---

### 4.10 Media Proxy

#### GET /media/whatsapp/{message_id}

Proxy WhatsApp/Instagram media. Re-fetches fresh download URL from Meta using stored `whatsapp_media_id` (Meta URLs expire within minutes). Streams binary back with correct content-type.

---

### 4.11 Other Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/macros` | GET/POST/PATCH/DELETE | Canned response templates |
| `/automations` | GET/POST/PATCH/DELETE | Event-driven automation rules |
| `/analytics/overview` | GET | Dashboard stats (params: `days`) |
| `/sla/check` | POST | Manual SLA breach scan |
| `/sla-policies` | GET/POST/PATCH/DELETE | SLA policy CRUD |
| `/history/customer/{email}` | GET | Customer activity timeline |
| `/history/ticket/{ticket_id}` | GET | Ticket activity timeline |
| `/channels` | GET | List available channels for filter tabs |
| `/merchants` | GET/POST/PATCH/DELETE | Multi-merchant config |
| `/shopify/sync-orders` | POST | Bulk import orders from Shopify |
| `/customers` | GET/POST/PATCH/DELETE | Customer CRUD |
| `/health` | GET | `{"status": "ok", "version": "2.0.0"}` |

---

## 5. Workflow Documentation

### 5.1 Customer Chat Flow (WhatsApp)

```
Customer sends "Hi" on WhatsApp
       │
       ▼
Meta Webhook → POST /webhooks/whatsapp
       │
       ▼
Is this a new user? (no customer record or wa_greeted=false)
  YES → Send greeting → Mark wa_greeted=true → STOP (wait for next msg)
  NO  → Continue
       │
       ▼
Parse message type:
  • text → body = raw text
  • image/video → download_media(id) → store media_id + media_url
  • interactive.button_reply → map button ID to natural language
  • interactive.list_reply → map list ID to natural language
       │
       ▼
create_ticket_from_whatsapp():
  • Find/create customer by phone
  • Find existing open ticket for this phone OR create new
  • Save message to messages collection
       │
       ▼
process_whatsapp_message():
  • Load conversation history from DB
  • Build chat_messages array (system prompt + history)
  • Call Groq LLM → get JSON { action, email, order_number, ... }
  • Execute action via _execute_action():
    ┌─ show_menu      → send list message (6 options)
    ├─ fetch_order    → Shopify API → rich order card + buttons
    ├─ offer_gift_card→ order details + gift card value + Accept/Reject
    ├─ ask_reason     → list message with reason options
    ├─ ask_evidence   → text prompt for photo/video upload
    ├─ ask_confirmation → summary + Yes/No buttons
    ├─ submit_ticket  → set status=pending_admin_action + notify
    ├─ cancel_order   → retention flow (gift card → confirm → ticket)
    └─ none           → conversational reply (no action)
  • Send reply via WhatsApp API (text, buttons, list, or image+buttons)
  • Save reply to messages collection
```

### 5.2 Refund / Return / Replacement Flow

```
Step 1: Customer taps "Get Refund" (button on order card)
        → AI receives: "I want a refund for my order (order_id:123)"
        → Action: ask_retention → Gift Card offer with order details
        → [Accept Gift Card] [No, Continue]

Step 2a: Accept Gift Card → create Shopify gift card → END
Step 2b: No, Continue → ask_reason (list message: Wrong Product, Damaged, etc.)

Step 3: Customer picks reason (e.g. "Damaged Product")
        → Action: ask_evidence
        → "Please upload clear photos or video of the product"

Step 4: Customer uploads image → media saved with media_id
        → Action: ask_confirmation
        → Summary: Request Type, Order, Reason, Proof ✓
        → [Yes, Submit Request] [No]

Step 5: Yes → submit_ticket
        → DB: ticket.status = "pending_admin_action"
        → DB: ticket.pending_action_type = "refund"
        → DB: ticket.pending_action_order_id = "123"
        → Customer message: "Your request has been submitted 🙏"

Step 6: ADMIN sees orange banner in TicketDetailPage / RequestPage
        → Shows: Order #, Customer, Issue, Description, Proof thumbnails
        → [✅ Approve Request] [❌ Reject Request]

Step 7a: Admin clicks Approve
         → Shopify API action (cancel/refund/replace/return)
         → Notify customer on original channel:
           · WhatsApp: bold + emojis
           · Email: formal with subject line
           · Instagram: concise DM
         → ticket.status = "resolved"

Step 7b: Admin clicks Reject (+ optional reason)
         → Notify customer with rejection reason
         → ticket.status = "open"
```

### 5.3 Cancel Order Flow

```
Customer: "I want to cancel my order"
       │
       ▼
AI: offer_gift_card
  → Full order details (items, total)
  → Gift card benefits (value, no expiry, any product)
  → [Accept Gift Card] [Reject Gift Card]
       │
  ┌────┴────┐
  ▼         ▼
ACCEPT    REJECT
  │         │
  ▼         ▼
Gift card  ask_cancel_confirm
created    → "Are you sure?"
→ END      → [Yes, Cancel] [No, Keep]
                │
           ┌────┴────┐
           ▼         ▼
          YES       NO
           │         │
           ▼         ▼
    submit_ticket   "No worries 😊"
    (pending_admin  → END
     _action)
```

### 5.4 Message Sync & Media Flow

```
Customer sends image on WhatsApp
       │
       ▼
Webhook: msg.image.id = "meta-media-123"
       │
       ▼
download_media("meta-media-123") → temporary URL (expires in ~5 min)
       │
       ▼
Message saved to DB:
  whatsapp_media_id: "meta-media-123"  ← permanent
  whatsapp_media_url: "https://fbsbx.com/..." ← expires
  whatsapp_media_type: "image"
       │
       ▼
Admin opens ticket in browser
       │
       ▼
Frontend renders: <img src="/media/whatsapp/{message_id}" />
       │
       ▼
Backend proxy (GET /media/whatsapp/{msg_id}):
  1. Look up message → find whatsapp_media_id
  2. Call Meta API to get FRESH download URL
  3. Fetch binary from fresh URL with auth header
  4. Stream back to browser with correct content-type
```

---

## 6. Bug Report & Fixes

### BUG 1: WhatsApp Media Images Not Displaying (FIXED)

**Problem:** Customer-uploaded images showed as broken icons in admin UI.

**Root Cause:** Two issues:
1. Meta media download URLs expire within minutes, but stored URL was used hours later
2. Frontend proxy detection only checked for `facebook.com` / `graph.facebook.com`, but Meta CDN uses `fbsbx.com` / `whatsapp.net`

**Fix Applied:**
- Added `whatsapp_media_id` field to MessageInDB model
- Webhook now stores both `media_id` (permanent) and `media_url` (temporary)
- Media proxy re-fetches fresh URL from Meta using `media_id` each time
- Frontend always proxies WhatsApp media through backend (no domain-sniffing)

### BUG 2: AI Suggest Block Showing "Failed to generate suggestion" (FIXED)

**Problem:** The AISuggestion component appeared on TicketDetailPage and always showed error for WhatsApp tickets.

**Root Cause:** The AI suggest endpoint uses a different service than the WhatsApp AI agent, and was not properly configured.

**Fix Applied:** Removed the AISuggestion component from TicketDetailPage entirely (WhatsApp tickets are auto-processed by the AI agent).

### BUG 3: `pending_admin_action` Status Not in Enum (FIXED)

**Problem:** The TicketStatus enum only had 5 values (open, pending, in_progress, resolved, closed). The `pending_admin_action` status was set directly in MongoDB but not in the enum.

**Root Cause:** Enum was never updated when the admin approval flow was added.

**Fix Applied:** Added `PENDING_ADMIN_ACTION = "pending_admin_action"` to TicketStatus enum.

### BUG 4: SLA Worker Not Running

**Problem:** `sla_worker.py` exists but the scheduler was removed from `main.py`'s lifespan. SLA breach detection does not run automatically.

**Root Cause:** Scheduler was intentionally removed (commented reference in CLAUDE.md), but SLA policies and the SLA page still exist in the UI.

**Recommendation:** Either re-enable the scheduler in main.py lifespan, or add a note in the SLA page UI that breach detection requires manual trigger via `POST /sla/check`.

### BUG 5: Auth is Placeholder

**Problem:** `get_current_agent` in `auth.py` falls back to returning the first active agent or a hardcoded `local-admin` dict when no token is provided.

**Root Cause:** Development convenience that was never hardened for production.

**Impact:** Any unauthenticated request can perform admin actions.

**Recommendation:** Remove the fallback. Enforce JWT validation on all protected endpoints.

### BUG 6: Twitter Router Not Registered

**Problem:** `twitter_service.py` and related code exist but the twitter router is NOT registered in `main.py`.

**Root Cause:** Feature was started but never completed.

**Impact:** Twitter/X channel configuration in merchant settings has no functional backend.

### BUG 7: Duplicate Reason Prompt in WhatsApp

**Problem:** In some flows, the AI sends "Could you tell us why you'd like to return?" twice (seen in screenshot at 1:44:35 and 1:44:39).

**Root Cause:** The LLM sometimes produces `ask_reason` when the system has already sent reason buttons. The conversation history shows both the text reply and the interactive message, but the AI doesn't distinguish between them.

**Recommendation:** Add deduplication logic — if the last agent message was an `ask_reason` list, suppress a second `ask_reason` within 30 seconds.

### BUG 8: `datetime.utcnow()` Deprecation

**Problem:** Multiple files use `datetime.utcnow()` which is deprecated in Python 3.12+.

**Root Cause:** Legacy code pattern.

**Recommendation:** Replace all `datetime.utcnow()` with `datetime.now(timezone.utc)` across `whatsapp_ai_agent.py`, `ticket_service.py`, and model defaults.

---

## 7. System Improvements

### 7.1 Architecture

| Area | Current | Recommended |
|---|---|---|
| **Message Queue** | Webhook processing in FastAPI background tasks | Add Redis + Celery/ARQ for reliable async processing. Background tasks die if the process restarts mid-execution. |
| **Media Storage** | Meta temporary URLs + re-fetch proxy | Download media binary on receipt → store in S3/MinIO → serve from permanent URL. Eliminates Meta API dependency for viewing. |
| **Caching** | None | Add Redis cache for Shopify order/customer lookups (TTL 5 min). Reduces Shopify API calls and improves response time. |
| **Rate Limiting** | None | Add rate limiting on webhook endpoints to prevent abuse. |
| **Health Checks** | Basic `/health` | Add DB connectivity check, Shopify API check, Meta API check. |

### 7.2 Security

| Issue | Fix |
|---|---|
| Auth fallback bypasses JWT | Remove `local-admin` fallback in `get_current_agent` |
| No CSRF protection | Add CSRF tokens for state-changing endpoints |
| `.env` secrets in plain text | Use a secrets manager (Vault, AWS Secrets Manager) |
| No input sanitization on message body | Sanitize HTML/script tags before storing |
| Webhook signature verification is optional | Make it mandatory (reject unsigned webhooks) |

### 7.3 Scalability

- **Database indexing:** Already comprehensive (20+ indexes). Consider TTL indexes for activity_logs and old messages.
- **Connection pooling:** Motor's AsyncIOMotorClient already handles this, but configure `maxPoolSize` for production.
- **Horizontal scaling:** Backend is stateless (no in-memory sessions). Can scale horizontally behind a load balancer. The only concern is the SLA scheduler — use a distributed lock (Redis) to prevent duplicate runs.

### 7.4 Monitoring & Logging

| Current | Recommended |
|---|---|
| `print()` statements | Structured logging with `structlog` or `loguru` |
| No metrics | Add Prometheus metrics (request latency, webhook processing time, AI response time) |
| No error tracking | Add Sentry for exception tracking |
| No request tracing | Add correlation IDs to track requests across services |

### 7.5 Retry Mechanisms

| Service | Current | Recommended |
|---|---|---|
| Shopify API | Single retry in `_request_with_retry` | Exponential backoff with jitter (3 attempts) |
| WhatsApp send | No retry | Retry with 2s delay on 5xx errors (max 2 attempts) |
| Mailgun send | No retry | Retry on timeout/5xx (max 2 attempts) |
| LLM (Groq) | No retry | Retry on rate limit (429) with backoff |

---

## 8. AI System Prompt Summary

The WhatsApp AI agent uses a Groq-hosted Llama 3.1 8B model with a detailed system prompt that enforces:

### Core Behavior
- English-only, warm/empathetic tone
- Button-driven interactions (customers never type except email/order number)
- Never process refund/return/replace/cancel directly — always create ticket for admin approval
- Never create duplicate tickets for the same active request

### Supported Actions (20 total)
`show_menu`, `fetch_order`, `create_order`, `check_inventory`, `fetch_customer`, `create_customer`, `ask_email`, `ask_order_number`, `ask_product`, `ask_quantity`, `offer_gift_card`, `accept_gift_card`, `ask_cancel_confirm`, `ask_reason`, `ask_evidence`, `ask_confirmation`, `submit_ticket`, `create_ticket`, `cancel_order`, `none`

### Flow Enforcement
1. **Cancel:** Always offer gift card first → accept/reject → confirm → ticket
2. **Refund/Replace/Return:** Reason → Evidence (MANDATORY, block until received) → Summary confirmation → Ticket
3. **Order tracking:** Fetch order → show rich card with buttons based on fulfillment status

### Output Format
Strict JSON with fields: `action`, `email`, `order_id`, `order_number`, `action_type`, `issue`, `evidence_description`, `products`, `inventory_query`, `message`

---

## 9. Environment Variables Reference

```bash
# Required
MONGODB_URL=mongodb+srv://user:pass@cluster/dbname
SECRET_KEY=your-jwt-secret

# Shopify
SHOPIFY_STORE_DOMAIN=yourstore.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_...

# AI (at least one required for AI features)
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...

# WhatsApp Cloud API
WHATSAPP_PHONE_NUMBER_ID=123456
WHATSAPP_WABA_ID=789012
WHATSAPP_ACCESS_TOKEN=EAA...
WHATSAPP_VERIFY_TOKEN=your-verify-token
WHATSAPP_APP_SECRET=abc123

# Instagram Messenger
INSTAGRAM_PAGE_ID=123456
INSTAGRAM_ACCESS_TOKEN=EAA...
INSTAGRAM_APP_SECRET=abc123
INSTAGRAM_VERIFY_TOKEN=your-verify-token

# Email (Mailgun)
MAILGUN_API_KEY=key-...
MAILGUN_DOMAIN=mg.yourdomain.com

# CORS
CORS_ORIGINS=https://yourdomain.com,http://localhost:5173

# Optional
MONGODB_DB_NAME=helpdesk
```

---

## 10. Deployment

### Backend (Render.com)

```yaml
# backend/render.yaml
services:
  - type: web
    name: helpdesk-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Frontend (Render.com Static)

```yaml
# frontend/render.yaml
services:
  - type: static
    name: helpdesk-frontend
    buildCommand: npm install && npm run build
    staticPublishPath: dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

### Default Dev Login

```
Email: admin@yourstore.com
Password: change-this-password
```

---

## 11. Database Collections

| Collection | Document Count (est.) | Key Indexes |
|---|---|---|
| `tickets` | High | status+created_at, customer_email, whatsapp_phone+channel+status |
| `messages` | Very High | ticket_id+created_at, whatsapp_message_id |
| `customers` | Medium | email (unique), phone, shopify_customer_id |
| `order_snapshots` | High | shopify_order_id (unique), email |
| `returns` | Low-Medium | status+created_at, order_id, customer_email |
| `merchants` | Very Low | whatsapp_phone_number_id, instagram_page_id |
| `automation_rules` | Very Low | trigger_event+is_active |
| `macros` | Very Low | — |
| `sla_policies` | Very Low | — |
| `gift_cards` | Low | customer_email, shopify_gift_card_id |
| `activity_logs` | Very High | entity_type+entity_id+created_at, customer_email+created_at |
| `agents` | Very Low | email (unique) |

---

*Generated from full codebase analysis. For questions, refer to the source code or contact the development team.*
