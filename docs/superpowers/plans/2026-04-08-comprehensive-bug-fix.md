# Comprehensive Bug Fix & Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 14 numbered bugs and 10 bullet-point issues across the helpdesk app's backend and frontend, in a targeted way that does not rewrite working code.

**Architecture:** FastAPI backend (`backend/app/`) with Motor/MongoDB + Shopify REST API. React+Vite frontend (`frontend/src/`) with Tailwind CSS. No test suite exists.

**Tech Stack:** Python 3.11, FastAPI, Motor (async MongoDB), React 18, Vite, Tailwind CSS v3, Axios, React Router v6.

---

## Pre-flight: Key Files & Findings

| File | Relevant bugs |
|------|---------------|
| `backend/app/routers/external_tickets.py` | Bug 1 |
| `backend/app/routers/returns.py:140-265` | Bug 2 |
| `backend/app/routers/orders.py:278-287` | Bug 3, 4 |
| `backend/app/services/gift_card_service.py:68-165` | Bug 11 |
| `frontend/src/pages/TicketDetailPage.jsx:527-531` | Bug 5, P2 |
| `frontend/src/pages/SLAPoliciesPage.jsx:18,26` | Bug 10 |
| `frontend/src/pages/GiftCardPage.jsx:114-123` | Bug 12 |
| `frontend/src/components/Sidebar.jsx:44-58,72-86` | Bug 8, Bug 14 |
| `frontend/src/pages/InboxPage.jsx:83-85,178-206` | Bug 7, P10 |
| `frontend/src/pages/RequestPage.jsx:776-1549` | Bug 7, P4, P5 |
| `frontend/src/pages/NewTicketPage.jsx` | P1 |
| `frontend/src/pages/CustomersPage.jsx:25-36` | P7 |
| `frontend/src/pages/OrdersPage.jsx:38-43` | P9 |
| `frontend/src/pages/OrderDetailPage.jsx:634,928` | P8 |
| `frontend/src/components/AiBanner.jsx:889-928` | Bug 2 (frontend), Bug 13 |

---

## Task 1: Bug 1 — Merge duplicate external tickets

**Files:**
- Modify: `backend/app/routers/external_tickets.py:74-161`

Context: `POST /api/external/tickets` always creates a new ticket. Must check for an existing open ticket for the same customer + merchant first.

- [ ] **Step 1: Add merge logic before ticket creation (lines 88-161)**

Replace the current `create_external_ticket` body with this version (keep imports/header/dependency unchanged):

```python
@router.post("/tickets")
async def create_external_ticket(
    data: TicketCreate,
    shop_domain: str = Depends(verify_merchant),
):
    db = get_db()

    merchant = await db.merchants.find_one({"shopify_store_domain": shop_domain})
    merchant_id = merchant["id"] if merchant else None

    store_domain, access_token = await get_shopify_creds(merchant_id=merchant_id, store_domain=shop_domain)
    customer = await fetch_and_sync_customer(
        data.customer_email,
        store_domain=store_domain,
        access_token=access_token,
    )

    body = data.message or data.initial_message
    images = [url for url in (data.images or []) if url and url.startswith("http")]

    # ── Check for an existing OPEN ticket from the same customer + merchant ──
    existing_ticket = await db.tickets.find_one({
        "customer_email": data.customer_email,
        "merchant_id": merchant_id,
        "status": "open",
    })

    if existing_ticket:
        # Append new message to existing ticket instead of creating a new one
        if body or images:
            from app.models.message import MessageInDB
            msg = MessageInDB(
                ticket_id=existing_ticket["id"],
                body=body or "",
                sender_type="customer",
                attachments=images,
                channel="whatsapp" if data.channel == "whatsapp" else None,
            )
            await db.messages.insert_one(msg.model_dump())

        await db.tickets.update_one(
            {"id": existing_ticket["id"]},
            {"$set": {"updated_at": datetime.now(timezone.utc)}},
        )

        await log_activity(
            entity_type="ticket",
            entity_id=existing_ticket["id"],
            event="message.added",
            actor_type="external_store",
            actor_id=shop_domain,
            actor_name=shop_domain,
            description=f"Message merged into existing open ticket from {shop_domain}",
            customer_email=data.customer_email,
        )

        existing_ticket.pop("_id", None)
        return {"merged": True, "ticket": existing_ticket}

    # ── No open ticket found — create a new one ──
    admin_id = await _get_admin_agent_id()

    ticket = TicketInDB(
        subject=data.subject,
        customer_email=data.customer_email,
        customer_name=data.customer_name or f"{customer.get('first_name') or ''} {customer.get('last_name') or ''}".strip() or None,
        shopify_customer_id=data.shopify_customer_id or customer.get("shopify_customer_id"),
        merchant_id=merchant_id,
        store_domain=store_domain or shop_domain,
        source_store=shop_domain,
        channel=data.channel.value if hasattr(data.channel, "value") else data.channel,
        priority=data.priority.value if hasattr(data.priority, "value") else data.priority,
        tags=data.tags,
        images=images,
        ticket_type=classify_ticket_type(data.subject, data.initial_message or data.message or ""),
        assignee_id=admin_id,
    )

    ticket_doc = ticket.model_dump()
    ticket_doc = await apply_sla_policy(ticket_doc)
    await db.tickets.insert_one(ticket_doc)

    if body or images:
        from app.models.message import MessageInDB
        msg = MessageInDB(
            ticket_id=ticket.id,
            body=body or "",
            sender_type="customer",
            attachments=images,
            channel="whatsapp" if data.channel == "whatsapp" else None,
        )
        await db.messages.insert_one(msg.model_dump())

    await log_activity(
        entity_type="ticket",
        entity_id=ticket.id,
        event="ticket.created",
        actor_type="external_store",
        actor_id=shop_domain,
        actor_name=shop_domain,
        description=f"External ticket created from {shop_domain}: {data.subject}",
        customer_email=data.customer_email,
    )

    try:
        from app.services.automation_engine import evaluate_automations
        await evaluate_automations("ticket.created", ticket_doc)
    except Exception:
        pass

    ticket_doc.pop("_id", None)
    return {"merged": False, "ticket": ticket_doc}
```

- [ ] **Step 2: Verify no import changes needed** — `datetime`, `timezone` already imported at top of file. `MessageInDB` is imported inside the blocks to avoid circular import risk (it was already imported at module level — remove the inline import and keep the top-level one).

- [ ] **Step 3: Test manually**
  - POST to `/api/external/tickets` twice with same `customer_email` + same merchant
  - First response: `{merged: false, ticket: {...}}`
  - Second response: `{merged: true, ticket: {...}}` — same ticket ID as first
  - Open that ticket in the UI — both messages should appear

---

## Task 2: Bug 2 — Policy window: no countdown when order not fulfilled

**Files:**
- Modify: `backend/app/routers/returns.py:140-218` (`order_policy_check`)
- Modify: `backend/app/routers/returns.py:221-265` (`return_policy_check`)
- Modify: `frontend/src/components/AiBanner.jsx:906-919` (metrics row window display)

**Root cause:** When `fulfillments` is empty the code falls back to `order.created_at` as baseline. The spec requires: if no fulfillment → show "Policy window starts after fulfillment" rather than a countdown.

- [ ] **Step 1: Fix `order_policy_check` (returns.py ~line 155-185)**

Change lines 160-184 in `order_policy_check`:

```python
    # Determine baseline: fulfillment date preferred, order date as fallback
    fulfillments = order.get("fulfillments") or []
    if fulfillments:
        raw = fulfillments[-1].get("created_at") or ""
        if raw:
            window_baseline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            baseline_label = "fulfillment"
    if not window_baseline:
        # Order not yet fulfilled — policy window hasn't started
        baseline_label = "not_fulfilled"
```

Remove the block that falls back to `order.created_at` (the original `if not window_baseline: raw = order.get("created_at")...` block).

Then update the within_window logic (after the baseline block):
```python
    if window_baseline and window_baseline.tzinfo is None:
        window_baseline = window_baseline.replace(tzinfo=timezone.utc)

    window_days = WINDOW_DAYS_BY_TYPE.get(ticket_type, RETURN_WINDOW_DAYS)

    within_window = None
    days_since_baseline = None
    if window_baseline and baseline_label != "not_fulfilled":
        now = datetime.now(timezone.utc)
        days_since_baseline = (now - window_baseline).days
        within_window = days_since_baseline <= window_days
```

And update the return dict:
```python
    return {
        "return_window": {
            "pass": within_window,
            "days": window_days,
            "days_since_baseline": days_since_baseline,
            "baseline": baseline_label,   # "fulfillment" | "not_fulfilled"
        },
        ...
    }
```

- [ ] **Step 2: Apply same fix to `return_policy_check` (~line 233-264)**

Same pattern: remove the fallback to `order.created_at`. When `fulfillments` is empty, set `baseline_label = "not_fulfilled"` and skip `within_window` / `days_since_baseline` calculation.

- [ ] **Step 3: Update AiBanner.jsx metrics row (lines 906-919)**

The window metric card currently reads:
```jsx
<p className={clsx('text-sm font-semibold mt-0.5',
  daysLeft === null ? 'text-gray-400' :
    daysLeft > 7 ? 'text-green-600' :
      daysLeft > 0 ? 'text-yellow-600' : 'text-red-500')}>
  {daysLeft === null ? '—' : daysLeft > 0 ? `${daysLeft} days left` : 'Expired'}
</p>
```

`daysLeft` is computed from `returnPolicyData?.return_window`. Update to handle `not_fulfilled`:

```jsx
{(() => {
  const rw = returnPolicyData?.return_window
  const isNotFulfilled = rw?.baseline === 'not_fulfilled'
  if (isNotFulfilled) {
    return <p className="text-sm font-medium text-gray-400 mt-0.5">Starts after fulfillment</p>
  }
  return (
    <p className={clsx('text-sm font-semibold mt-0.5',
      daysLeft === null ? 'text-gray-400' :
        daysLeft > 7 ? 'text-green-600' :
          daysLeft > 0 ? 'text-yellow-600' : 'text-red-500')}>
      {daysLeft === null ? '—' : daysLeft > 0 ? `${daysLeft} days left` : 'Expired'}
    </p>
  )
})()}
```

Note: `daysLeft` is computed elsewhere in AiBanner from `returnPolicyData`. You need to locate that computation (search for `daysLeft`) and ensure it also respects `not_fulfilled`.

- [ ] **Step 4: Test**
  - Open a ticket whose order has NO fulfillments → metric shows "Starts after fulfillment"
  - Open a ticket whose order IS fulfilled → metric shows correct days remaining countdown

---

## Task 3: Bug 3 & 4 — Fetch ALL customer orders (remove limit:50)

**Files:**
- Modify: `backend/app/routers/orders.py:278-287`

**Root cause:** `GET /orders/customer/{customer_id}` uses `limit: 50`, which may cut off customers with many orders.

- [ ] **Step 1: Add pagination loop to fetch all orders**

Replace lines 278-287:
```python
@router.get("/customer/{customer_id}")
async def get_orders_by_customer(customer_id: str, merchant_id: Optional[str] = Query(None),
                                  agent=Depends(get_current_agent)):
    store_domain, access_token = await get_shopify_creds(merchant_id)
    all_orders = []
    since_id = None
    try:
        while True:
            params = {"status": "any", "limit": 250, "order": "created_at DESC"}
            if since_id:
                params["since_id"] = since_id
            data = await shopify_get(
                f"/customers/{customer_id}/orders.json",
                params,
                store_domain=store_domain,
                access_token=access_token,
            )
            batch = data.get("orders", [])
            all_orders.extend(batch)
            if len(batch) < 250:
                break
            since_id = batch[-1]["id"]
        return [_format_order(o) for o in all_orders]
    except ShopifyAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
```

- [ ] **Step 2: Test**
  - Open a ticket for a customer with 8+ orders
  - Verify the order selector / customer card shows all 8+ orders

---

## Task 4: Bug 5 — Replace "Resolve" with "Close Ticket" + confirmation

**Files:**
- Modify: `frontend/src/pages/TicketDetailPage.jsx:96-101, 527-531`

- [ ] **Step 1: Add `closeTicket` state and function**

After `async function resolveTicket()` (line 96), add:
```js
const [showCloseConfirm, setShowCloseConfirm] = useState(false);

async function closeTicket() {
  try {
    await api.patch(`/tickets/${id}`, { status: 'closed' });
    setShowCloseConfirm(false);
    await loadTicket();
  } catch {}
}
```

Add `showCloseConfirm` to the top-level state declarations at line 48.

- [ ] **Step 2: Replace "Resolve" button (lines 527-531)**

Replace:
```jsx
{ticket.status !== 'resolved' && (
  <button onClick={resolveTicket} className="btn-secondary ml-auto">
    Resolve
  </button>
)}
```

With:
```jsx
{ticket.status !== 'closed' && (
  <button
    onClick={() => setShowCloseConfirm(true)}
    className="btn-secondary ml-auto"
  >
    Close Ticket
  </button>
)}
{showCloseConfirm && (
  <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div className="bg-white rounded-xl shadow-xl p-6 w-80 space-y-4">
      <h3 className="text-base font-semibold text-gray-900">Close this ticket?</h3>
      <p className="text-sm text-gray-500">This will mark the ticket as closed. You can reopen it later.</p>
      <div className="flex gap-2 justify-end">
        <button
          onClick={() => setShowCloseConfirm(false)}
          className="btn-secondary text-sm"
        >
          Cancel
        </button>
        <button
          onClick={closeTicket}
          className="btn-primary text-sm"
        >
          Close Ticket
        </button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 3: Keep `resolveTicket` as is** — it's used by other internal flows (don't delete it).

- [ ] **Step 4: Test**
  - Open any ticket in Inbox → "Resolve" button should be gone, "Close Ticket" appears
  - Click "Close Ticket" → modal appears with Cancel / Close Ticket
  - Confirm → ticket status becomes `closed`, UI refreshes

---

## Task 5: Bug 6 — Return page investigation & fix

**Files:**
- Modify: `frontend/src/pages/ReturnsPage.jsx:38-49` (improve error display)

**Root cause (likely):** The MongoDB `returns` collection is empty — no return requests have been created yet. The page correctly shows "No return requests found." The user may also expect Shopify refunded orders to appear here (they do not; they're a separate concept).

- [ ] **Step 1: Add API error display to ReturnsPage**

In `loadReturns()` at line 38, capture errors and show them:

```js
const [loadError, setLoadError] = useState('');

async function loadReturns() {
  setLoading(true);
  setLoadError('');
  try {
    const res = await api.get("/returns", {
      params: { status, resolution, page, limit },
    });
    setReturns(res.data.returns);
    setTotal(res.data.total);
  } catch (err) {
    setLoadError(err.response?.data?.detail || 'Failed to load returns');
  } finally {
    setLoading(false);
  }
}
```

Add `loadError` to state. In the card, show the error before the "No return requests found" fallback:
```jsx
) : loadError ? (
  <div className="p-8 text-center text-red-500 text-sm">{loadError}</div>
) : returns.length === 0 ? (
```

- [ ] **Step 2: Improve empty state message**

Change the empty-state text to be more informative:
```jsx
<div className="p-8 text-center text-gray-400">
  No return requests found. Return requests are created when customers or agents initiate a return via the return flow.
</div>
```

- [ ] **Step 3: Test**
  - Open Returns page → if no data, shows improved empty state (not blank)
  - If API fails, shows the actual error

---

## Task 6: Bug 7 — Image attachment indicator in Inbox list + images in RequestPage detail

**Files:**
- Modify: `frontend/src/pages/InboxPage.jsx:178-206`
- Modify: `frontend/src/pages/RequestPage.jsx` (detail view, after messages block)

### Part A — Inbox image indicator

- [ ] **Step 1: Add 📎 icon to ticket list items when ticket has images**

In InboxPage.jsx, in the ticket list item (around line 183-186), after `<p className="text-xs text-gray-500 mt-0.5">{t.customer_email}</p>`, add:

```jsx
{t.images?.length > 0 && (
  <span className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
    📎 {t.images.length} attachment{t.images.length > 1 ? 's' : ''}
  </span>
)}
```

### Part B — Ticket-level images in RequestPage detail

- [ ] **Step 2: Show `selectedTicket.images` in RequestPage detail view**

In RequestPage.jsx, after the closing `</div>` of the message thread (around line 895, before the "Pending Admin Action Banner"), add:

```jsx
{selectedTicket.images?.length > 0 && (
  <div className="mb-4">
    <p className="text-xs font-semibold text-gray-500 mb-1.5">📎 Ticket attachments ({selectedTicket.images.length})</p>
    <div className="flex flex-wrap gap-2">
      {selectedTicket.images.map((url, idx) => (
        <img
          key={idx}
          src={url}
          alt={`Attachment ${idx + 1}`}
          className="w-24 h-24 rounded-lg object-cover border border-gray-200 cursor-pointer hover:opacity-80 transition-opacity"
          onClick={() => window.open(url, '_blank')}
        />
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 3: Test**
  - In Inbox list: tickets with `images` should show the 📎 indicator
  - Open a ticket in RequestPage that has images → images display after message thread

---

## Task 7: Bug 8 — Back button in TicketDetailPage + Sidebar active state fix

**Files:**
- Modify: `frontend/src/pages/TicketDetailPage.jsx:126-130`
- Modify: `frontend/src/components/Sidebar.jsx:1-92`

### Part A — Back button in TicketDetailPage

- [ ] **Step 1: Add back button to TicketDetailPage**

TicketDetailPage already imports `useNavigate` is NOT imported — check. It uses `useParams`. Add `useNavigate`:

At the top import line, add `useNavigate` to the react-router-dom import. Add:
```js
const navigate = useNavigate();
```

Then in the render, before the `<div className="flex gap-6">` at line 127, add:
```jsx
<button
  onClick={() => navigate(-1)}
  className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-4 transition-colors"
>
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
  </svg>
  Back
</button>
```

### Part B — Sidebar active state using pathname prefix

- [ ] **Step 2: Fix Sidebar to use pathname-based active state**

In Sidebar.jsx, add `useLocation` to imports:
```js
import { NavLink, useLocation } from 'react-router-dom';
```

Update the NAV_ITEMS to include a `matchPrefix` field where needed:
```js
const NAV_ITEMS = [
  { to: '/', icon: Inbox, label: 'Inbox', matchPrefix: ['/', '/tickets'] },
  { to: '/customers', icon: Users, label: 'Customers', matchPrefix: ['/customers'] },
  { to: '/orders', icon: ShoppingBag, label: 'Orders', matchPrefix: ['/orders'] },
  { to: '/analytics', icon: BarChart3, label: 'Analytics', matchPrefix: ['/analytics'] },
  { to: '/sla', icon: Shield, label: 'SLA', matchPrefix: ['/sla'] },
  { to: '/sla-policies', icon: Shield, label: 'SLA Policies', matchPrefix: ['/sla-policies'] },
  { to: '/macros', icon: Bot, label: 'Macros', matchPrefix: ['/macros'] },
  { to: '/automations', icon: Zap, label: 'Automations', matchPrefix: ['/automations'] },
  { to: '/requests', icon: FileText, label: 'Requests', matchPrefix: ['/requests'] },
  { to: '/returns', icon: RotateCcw, label: 'Returns', matchPrefix: ['/returns'] },
  { to: '/gift-cards', icon: Gift, label: 'Gift Cards', matchPrefix: ['/gift-cards'] },
  { to: '/whatsapp-settings', icon: WhatsAppIcon, label: 'WhatsApp', matchPrefix: ['/whatsapp-settings'] },
  { to: '/email-settings', icon: Mail, label: 'Email', matchPrefix: ['/email-settings'] },
];
```

In the Sidebar component function, add:
```js
const location = useLocation();
```

Replace the `NavLink` usage with a regular `<a>` link using `Link` from react-router-dom and manual active detection:

```jsx
import { NavLink, useLocation, Link } from 'react-router-dom';

// Inside Sidebar:
const location = useLocation();

function isItemActive(item) {
  if (item.to === '/') {
    return item.matchPrefix.some(p =>
      p === '/' ? location.pathname === '/' : location.pathname.startsWith(p)
    )
  }
  return item.matchPrefix.some(p => location.pathname.startsWith(p))
}

// In render:
{NAV_ITEMS.map(item => {
  const active = isItemActive(item)
  return (
    <Link
      key={item.to}
      to={item.to}
      className={clsx(
        'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
        active
          ? 'bg-brand-50 text-brand-700'
          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
      )}
    >
      <item.icon size={18} />
      {item.label}
    </Link>
  )
})}
```

- [ ] **Step 3: Test**
  - Click a ticket from Inbox → `/tickets/:id` → Inbox tab in sidebar stays highlighted
  - Click a ticket from Requests → `/requests` stays highlighted
  - Click a customer → `/customers/:id` → Customers tab stays highlighted

---

## Task 8: Bug 9 — Add debounce to search bars

**Files:**
- Modify: `frontend/src/pages/CustomersPage.jsx:25-36`
- Modify: `frontend/src/pages/OrdersPage.jsx:30-43`

**Root cause:** CustomersPage triggers API on every keystroke (`useEffect([search])`). OrdersPage same. Need 300ms debounce.

- [ ] **Step 1: Add debounce to CustomersPage**

Add `searchInput` state and debounce it into `search`:
```js
const [searchInput, setSearchInput] = useState('');
const [search, setSearch] = useState('');

// Add debounce effect:
useEffect(() => {
  const t = setTimeout(() => setSearch(searchInput), 300);
  return () => clearTimeout(t);
}, [searchInput]);

// loadCustomers still depends on `search` (not searchInput)
useEffect(() => { loadCustomers(); }, [search]);
```

Change the input's `onChange` to update `searchInput` (not `search` directly):
```jsx
onChange={e => setSearchInput(e.target.value)}
value={searchInput}
```

- [ ] **Step 2: Same pattern for OrdersPage**

Add `searchInput` / `search` split with 300ms debounce. The input binds to `searchInput`, `loadOrders` depends on `search`.

- [ ] **Step 3: Add loading spinner to CustomersPage search**

When `loading` is true and `search` is non-empty, show a small spinner inside the search input (right side). Already has a spinner for the list — this is optional enhancement.

---

## Task 9: Bug 10 — Remove Instagram & Shopify from SLA channel options

**Files:**
- Modify: `frontend/src/pages/SLAPoliciesPage.jsx:18,26`

- [ ] **Step 1: Remove channels from CHANNEL_OPTIONS (line 18)**

Change:
```js
const CHANNEL_OPTIONS = ['email', 'whatsapp', 'instagram', 'manual', 'shopify']
```
To:
```js
const CHANNEL_OPTIONS = ['email', 'whatsapp', 'manual']
```

- [ ] **Step 2: Fix EMPTY_FORM defaults (line 26)**

Change:
```js
applies_to_channels: ['email', 'whatsapp', 'instagram', 'manual'],
```
To:
```js
applies_to_channels: ['email', 'whatsapp', 'manual'],
```

- [ ] **Step 3: Test**
  - Open SLA Policies page → click "New Policy" → Channel toggles show only Email, WhatsApp, Manual
  - Existing policies that have `instagram` or `shopify` in their `applies_to_channels` will still display those values (backend data) — the form just won't offer them for new selections

---

## Task 10: Bug 11 — Link customer to gift card in Shopify

**Files:**
- Modify: `backend/app/services/gift_card_service.py:68-93` (`create_shopify_gift_card`)
- Modify: `backend/app/services/gift_card_service.py:97-165` (`assign_gift_card`)

**Root cause:** `create_shopify_gift_card` doesn't pass `customer_id` to Shopify. The gift card is created unlinked.

- [ ] **Step 1: Update `create_shopify_gift_card` to accept optional customer_id**

```python
async def create_shopify_gift_card(
    initial_value: str,
    currency: str = "INR",
    note: str = "",
    customer_id: str = None,     # NEW — Shopify numeric customer ID
) -> dict | None:
    """Create a NEW gift card on Shopify linked to the given customer (if provided)."""
    try:
        gc_payload = {
            "initial_value": str(initial_value),
            "currency": currency,
        }
        if note:
            gc_payload["note"] = note
        if customer_id:
            gc_payload["customer_id"] = int(customer_id)  # Shopify requires integer

        result = await shopify_post("/gift_cards.json", {"gift_card": gc_payload})
        gc = result.get("gift_card", {})
        if gc:
            return {
                "id": str(gc["id"]),
                "code": gc.get("code", ""),
                "last_characters": gc.get("last_characters", ""),
                "balance": gc.get("balance", initial_value),
                "currency": gc.get("currency", currency),
                "initial_value": gc.get("initial_value", initial_value),
            }
        return None
    except ShopifyAPIError as e:
        print(f"Failed to create Shopify gift card: {e}")
        return None
```

- [ ] **Step 2: Update `assign_gift_card` to look up Shopify customer and pass ID**

At the start of `assign_gift_card`, after looking up local customer, add Shopify customer lookup:

```python
async def assign_gift_card(...) -> dict:
    db = get_db()

    # Look up customer in local DB
    customer = await db.customers.find_one({"email": customer_email})
    customer_id = customer.get("id") if customer else None

    # Look up Shopify customer ID by email to link the gift card
    shopify_customer_id = None
    try:
        result = await shopify_get("/customers.json", params={"email": customer_email, "limit": 1})
        shopify_customers = result.get("customers", [])
        if shopify_customers:
            shopify_customer_id = str(shopify_customers[0]["id"])
        else:
            # Customer not in Shopify yet — create them
            create_result = await shopify_post("/customers.json", {
                "customer": {
                    "email": customer_email,
                    "verified_email": True,
                    "send_email_welcome": False,
                }
            })
            created = create_result.get("customer", {})
            if created.get("id"):
                shopify_customer_id = str(created["id"])
    except ShopifyAPIError as e:
        print(f"[gift_card] Could not look up/create Shopify customer for {customer_email}: {e}")

    # Create a NEW Shopify gift card with the customer linked
    new_card = await create_shopify_gift_card(
        initial_value=balance,
        currency=currency,
        note=f"Assigned to {customer_email} via {channel}",
        customer_id=shopify_customer_id,   # NEW
    )
    # ... rest of function unchanged
```

- [ ] **Step 3: Test**
  - Assign a gift card to a customer email
  - Go to Shopify Admin → Gift Cards → find the newly created card
  - Verify "Customer" field shows the customer's name

---

## Task 11: Bug 12 — Replace browser confirm() with modal for gift card expiry

**Files:**
- Modify: `frontend/src/pages/GiftCardPage.jsx:22-28, 114-123`

- [ ] **Step 1: Add expire confirmation state**

Add state near the top of `GiftCardPage`:
```js
const [expireConfirm, setExpireConfirm] = useState(null); // null or assignment object
```

- [ ] **Step 2: Replace the `handleExpire` function**

```js
async function handleExpire(assignmentId) {
  // Replaced browser confirm() with modal — setExpireConfirm triggers the modal below
  setExpireConfirm(assignmentId);
}

async function confirmExpire() {
  if (!expireConfirm) return;
  try {
    await api.post(`/gift-cards/assignments/${expireConfirm}/expire`);
    showToast('Gift card expired successfully');
    setExpireConfirm(null);
    loadHistory();
  } catch (err) {
    showToast('Expire failed: ' + (err.response?.data?.detail || err.message), 'error');
    setExpireConfirm(null);
  }
}
```

- [ ] **Step 3: Add confirmation modal to JSX (before the closing `</div>` of the return)**

```jsx
{expireConfirm && (
  <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div className="bg-white rounded-xl shadow-xl p-6 w-80 space-y-4">
      <h3 className="text-base font-semibold text-gray-900">Expire Gift Card?</h3>
      <p className="text-sm text-gray-500">
        Are you sure you want to expire this gift card? This action cannot be undone.
      </p>
      <div className="flex gap-2 justify-end">
        <button
          onClick={() => setExpireConfirm(null)}
          className="px-4 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200"
        >
          Cancel
        </button>
        <button
          onClick={confirmExpire}
          className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700"
        >
          Expire Card
        </button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 4: Test**
  - In Gift Cards → Assigned History, click "Expire" on a card
  - Modal appears: "Expire Gift Card?" + Cancel / Expire Card buttons
  - Cancel → modal closes, nothing changes
  - Expire Card → card is expired, success toast shown

---

## Task 12: Bug 13 — Request Page inventory display (diagnosis + fix)

**Files:**
- Modify: `frontend/src/pages/RequestPage.jsx:479-494`
- Modify: `frontend/src/components/AiBanner.jsx:970-1031`

**Root cause analysis:**
1. `fetchInventory` sets `inventory = []` when `variantIds` is empty (all line items have null `variant_id`)
2. When `inventory = []` and no error, AiBanner's `inventory.find()` returns `undefined` → shows `—` for all items
3. The AiBanner never shows an error in this case — it silently shows dashes

**Fix:** Distinguish between "not yet loaded", "failed to load", "loaded but no variant IDs", and "loaded with data".

- [ ] **Step 1: Track "no variant IDs" case in RequestPage**

In `fetchInventory` (line ~479):
```js
const fetchInventory = useCallback((order) => {
  const src = order || shopifyOrder
  if (!src?.line_items?.length) { setInventory([]); setInventoryError(false); return }
  const variantIds = src.line_items.map(li => li.variant_id).filter(Boolean).map(String)
  if (!variantIds.length) {
    setInventory([])
    setInventoryError('no_variant_ids')  // special sentinel
    return
  }
  setInventoryLoading(true)
  setInventoryError(false)
  shopifyApi.getInventory(variantIds, selectedTicket?.merchant_id || null)
    .then(res => { setInventory(res.data.inventory || []); setInventoryError(false) })
    .catch(() => { setInventory([]); setInventoryError(true) })
    .finally(() => setInventoryLoading(false))
}, [shopifyOrder])
```

- [ ] **Step 2: Update AiBanner to handle the sentinel**

In AiBanner.jsx `inventoryError` check (around line 975):
```jsx
) : inventoryError === 'no_variant_ids' ? (
  <p className="text-xs text-gray-400 italic">Variant data unavailable for these items</p>
) : inventoryError ? (
  <div className="space-y-2">
    <p className="text-xs text-red-500">Failed to load inventory</p>
    ...
  </div>
```

- [ ] **Step 3: Test**
  - Open a ticket with a Shopify order → Inventory Status card should show actual counts or "Not tracked"
  - If line items have no variant_id → shows "Variant data unavailable"
  - If API fails → shows "Failed to load inventory" with retry

---

## Task 13: Bug 14 — Move Returns tab below Requests in Sidebar

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx:44-58`

**Note:** This task is combined with Task 7 (Bug 8 sidebar changes). After applying Task 7's NAV_ITEMS rewrite, the Returns entry will already be after Requests in the list. Verify the order in the updated NAV_ITEMS matches:

```
Inbox → Customers → Orders → Analytics → SLA → SLA Policies → Macros → Automations → Requests → Returns → Gift Cards → WhatsApp → Email
```

If Task 7 was done first, just verify; otherwise apply the reorder here.

- [ ] **Step 1: Confirm sidebar order after Task 7 changes**

The NAV_ITEMS in Task 7 already places Returns after Requests. No additional change needed if Task 7 is done.

---

## Task 14: P1 — New Ticket page: Add image URLs field + Back button

**Files:**
- Modify: `frontend/src/pages/NewTicketPage.jsx`

- [ ] **Step 1: Add back button, images state, and form field**

Full replacement of NewTicketPage (only adding, not changing existing logic):

```jsx
export default function NewTicketPage() {
  const [subject, setSubject] = useState('');
  const [email, setEmail] = useState('');
  const [priority, setPriority] = useState('normal');
  const [message, setMessage] = useState('');
  const [images, setImages] = useState(['']);  // NEW: array of image URL inputs
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  function addImageRow() { setImages(prev => [...prev, '']); }
  function removeImageRow(i) { setImages(prev => prev.filter((_, idx) => idx !== i)); }
  function updateImage(i, val) { setImages(prev => prev.map((v, idx) => idx === i ? val : v)); }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const validImages = images.filter(u => u.trim().startsWith('http'));
    try {
      const res = await api.post('/tickets', {
        subject,
        customer_email: email,
        priority,
        channel: 'manual',
        initial_message: message || undefined,
        images: validImages.length ? validImages : undefined,
      });
      navigate(`/tickets/${res.data.id}`);
    } catch {
      setError('Failed to create ticket');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-4 transition-colors"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back
      </button>

      <h1 className="text-2xl font-semibold text-gray-900 mb-6">New Ticket</h1>
      <form onSubmit={handleSubmit} className="card p-6 space-y-4">
        {/* existing fields unchanged: Subject, Customer Email, Priority, Initial Message */}
        ...

        {/* Images (optional) */}
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">
            Images <span className="text-gray-400 font-normal">(optional, paste URLs)</span>
          </label>
          {images.map((url, i) => (
            <div key={i} className="flex gap-2 mb-2">
              <input
                type="url"
                value={url}
                onChange={e => updateImage(i, e.target.value)}
                placeholder="https://..."
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {images.length > 1 && (
                <button type="button" onClick={() => removeImageRow(i)}
                  className="px-2 py-1 text-gray-400 hover:text-red-500 text-lg leading-none">×</button>
              )}
            </div>
          ))}
          <button type="button" onClick={addImageRow}
            className="text-sm text-brand-600 hover:text-brand-800">
            + Add image URL
          </button>
        </div>

        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Creating...' : 'Create Ticket'}
        </button>
      </form>
    </div>
  );
}
```

Note: Keep all existing fields (Subject, Customer Email, Priority, Initial Message) — only add Images and Back button.

---

## Task 15: P4 — Format request date in RequestPage detail

**Files:**
- Modify: `frontend/src/pages/RequestPage.jsx:817`

- [ ] **Step 1: Change date format**

At line 817 (approximately), find:
```jsx
{new Date(selectedTicket.created_at).toLocaleString()}
```

Replace with:
```jsx
<span title={new Date(selectedTicket.created_at).toISOString()}>
  {new Date(selectedTicket.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
  {' · '}
  {new Date(selectedTicket.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}
</span>
```

This produces: "Apr 6, 2026 · 7:11 PM" with the raw ISO timestamp on hover.

---

## Task 16: P5 — Remove Shopify tab from RequestPage channel list

**Files:**
- Modify: `frontend/src/pages/RequestPage.jsx:89-96` (`toTabChannel` / channel mapping area)

**Root cause:** The channels list is fetched from `channelsApi.list()` which returns all channels from MongoDB, including "Shopify". The simplest fix is to filter it out on the frontend.

- [ ] **Step 1: Filter out Shopify channel in channel mapping**

In RequestPage.jsx, find where channels are set (around line 250-255):
```js
channelsApi.list()
  .then(res => {
    const mapped = res.data.channels.map(toTabChannel)
    if (mapped.length > 0) setChannels(mapped)
  })
```

Change to:
```js
channelsApi.list()
  .then(res => {
    const mapped = res.data.channels
      .filter(ch => ch.value !== 'shopify')  // Shopify is not a reply channel
      .map(toTabChannel)
    if (mapped.length > 0) setChannels(mapped)
  })
```

- [ ] **Step 2: Test**
  - Open Requests page → channel tabs at top should NOT show "Shopify"
  - All other tabs (All, Email, Manual, WhatsApp, etc.) should still appear

---

## Task 17: P6 — Customer avatar (first letter) in CustomerDetailPage

**Files:**
- Modify: `frontend/src/pages/CustomerDetailPage.jsx` (find customer name display area)

- [ ] **Step 1: Add avatar component inline**

In CustomerDetailPage.jsx, wherever the customer name/email is shown in the header, add an avatar before the name:

```jsx
{/* Avatar with first letter */}
{(() => {
  const name = data?.customer?.first_name || data?.customer?.email || '?'
  const letter = name[0].toUpperCase()
  return (
    <div className="w-12 h-12 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xl font-bold shrink-0">
      {letter}
    </div>
  )
})()}
```

Place this in the customer header section, next to the name.

---

## Task 18: P7 — Add pagination to CustomersPage

**Files:**
- Modify: `frontend/src/pages/CustomersPage.jsx`

- [ ] **Step 1: Add page state and pagination UI**

Add:
```js
const [page, setPage] = useState(1);
const limit = 20;
```

Update `loadCustomers`:
```js
async function loadCustomers() {
  setLoading(true);
  try {
    const res = await api.get('/customers', { params: { search, limit, page } });
    setCustomers(res.data.customers);
    setTotal(res.data.total);
  } catch (err) {
    addToast(err.response?.data?.detail || 'Failed to load customers from Shopify', 'error');
  } finally { setLoading(false); }
}

useEffect(() => { loadCustomers(); }, [search, page]);
useEffect(() => { setPage(1); }, [search]); // Reset on search change
```

Add pagination UI after the customer list (before the Create modal):
```jsx
{Math.ceil(total / limit) > 1 && (
  <div className="flex items-center justify-between mt-4">
    <p className="text-sm text-gray-500">
      Showing {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}
    </p>
    <div className="flex gap-2">
      <button
        onClick={() => setPage(p => Math.max(1, p - 1))}
        disabled={page === 1}
        className="btn-secondary text-sm"
      >
        Previous
      </button>
      <span className="text-sm text-gray-500 px-2 py-1">Page {page} of {Math.ceil(total / limit)}</span>
      <button
        onClick={() => setPage(p => Math.min(Math.ceil(total / limit), p + 1))}
        disabled={page >= Math.ceil(total / limit)}
        className="btn-secondary text-sm"
      >
        Next
      </button>
    </div>
  </div>
)}
```

**Note:** The backend `/customers` endpoint must support a `page` param. Check `backend/app/routers/customers.py` — add `page` query param to the Shopify call using `since_id` cursor if not already supported.

---

## Task 19: P8 — Change "Fulfill Items" to "Fulfill Order" in OrderDetailPage

**Files:**
- Modify: `frontend/src/pages/OrderDetailPage.jsx:634,928`

- [ ] **Step 1: Change button text at line 634**

Find:
```jsx
<Truck size={15} /> Fulfill Items
```
Change to:
```jsx
<Truck size={15} /> Fulfill Order
```

- [ ] **Step 2: Change modal footer label at line 928**

Find:
```jsx
label="Fulfill Items"
```
Change to:
```jsx
label="Fulfill Order"
```

---

## Task 20: P9 — Add pagination to OrdersPage

**Files:**
- Modify: `frontend/src/pages/OrdersPage.jsx`

- [ ] **Step 1: Add page state and pagination**

Add:
```js
const [page, setPage] = useState(1);
const [total, setTotal] = useState(0);
const limit = 20;
```

Update `loadOrders`:
```js
async function loadOrders() {
  setLoading(true);
  try {
    const res = await api.get('/orders', { params: { search, limit, page } });
    setOrders(res.data.orders);
    setTotal(res.data.total || res.data.orders?.length || 0);
  } catch {} finally { setLoading(false); }
}

useEffect(() => {
  if (tab === 'orders') loadOrders();
  else loadDrafts();
}, [tab, search, page]);

useEffect(() => { setPage(1); }, [search, tab]);
```

Add pagination UI after the orders list (same pattern as Task 18).

**Note:** Check `backend/app/routers/orders.py` `GET /orders` to verify it returns `total` and supports `page` param.

---

## Task 21: P10 — Fix Inbox filters not working

**Files:**
- Modify: `frontend/src/pages/InboxPage.jsx:83-85`

**Root cause:** `useEffect(() => { loadTickets(); }, [status, page])` — `channel` and `ticketType` are missing from the dependency array, so changing the dropdowns doesn't re-fetch.

- [ ] **Step 1: Add channel and ticketType to useEffect dependency**

Change line 83-85 from:
```js
useEffect(() => {
  loadTickets();
}, [status, page]);
```

To:
```js
useEffect(() => {
  loadTickets();
}, [status, page, channel, ticketType]);
```

- [ ] **Step 2: Test**
  - Open Inbox → select "Return" from the Type dropdown → list should filter
  - Select "WhatsApp" from Channel dropdown → list should filter
  - Combine both → list should apply both filters simultaneously

---

## Resolution Summary Table

| # | Issue | Root Cause | Fix Location | Key Change |
|---|-------|-----------|--------------|------------|
| Bug 1 | Duplicate tickets | No merge check | `external_tickets.py:74-161` | Query open tickets before creating |
| Bug 2 | Wrong policy window date | Falls back to createdAt when unfulfilled | `returns.py:155-184,233-264`; `AiBanner.jsx:906-919` | Skip window when not fulfilled; show "Starts after fulfillment" |
| Bug 3 & 4 | Order count/list limited | `limit: 50` on customer orders endpoint | `orders.py:278-287` | Pagination loop, limit 250 per page |
| Bug 5 | Resolve → Close Ticket | Button calls wrong status | `TicketDetailPage.jsx:527-531` | Replace Resolve with Close Ticket + confirmation modal |
| Bug 6 | Return page empty | Likely empty MongoDB collection | `ReturnsPage.jsx` | Add error display + better empty state |
| Bug 7 | Missing images in Inbox/Request | Inbox has no image indicator; RequestPage misses ticket.images | `InboxPage.jsx:183-186`; `RequestPage.jsx:895` | Add 📎 to list; add ticket.images block in detail |
| Bug 8 | No back button; sidebar loses active | Missing back button; NavLink exact matching | `TicketDetailPage.jsx:126`; `Sidebar.jsx:44-86` | Add back button; switch to pathname.startsWith() |
| Bug 9 | Search not debounced | Fires on every keystroke | `CustomersPage.jsx`; `OrdersPage.jsx` | 300ms debounce via separate input/search state |
| Bug 10 | Instagram & Shopify in SLA channels | CHANNEL_OPTIONS includes them | `SLAPoliciesPage.jsx:18,26` | Remove from array |
| Bug 11 | Gift card not linked to customer | customer_id not passed to Shopify | `gift_card_service.py:68-165` | Look up/create Shopify customer, pass ID |
| Bug 12 | Browser alert on expire | Uses `confirm()` | `GiftCardPage.jsx:114-123` | State-managed modal |
| Bug 13 | Inventory shows `—` | Empty inventory array shows `—` silently | `RequestPage.jsx:479-494`; `AiBanner.jsx:975` | Distinguish empty vs error; add helpful message |
| Bug 14 | Returns tab wrong position | Sidebar order | `Sidebar.jsx:44-58` | Move Returns after Requests in NAV_ITEMS |
| P1 | New ticket: no images / back | Fields missing | `NewTicketPage.jsx` | Add image URL rows + back button |
| P2 | Ticket detail: no back button | Missing navigate | `TicketDetailPage.jsx` | Done in Bug 8 |
| P3 | Customer order count wrong | Same as Bug 3 | `orders.py:278-287` | Done in Bug 3 |
| P4 | Confusing request date | Raw toLocaleString() | `RequestPage.jsx:817` | Format as "Apr 6, 2026 · 7:11 PM" with hover tooltip |
| P5 | Shopify tab in Requests | Channel list includes shopify | `RequestPage.jsx:250-255` | Filter out shopify channel |
| P6 | No customer avatar | Missing avatar component | `CustomerDetailPage.jsx` | First-letter avatar with brand color |
| P7 | Customer list no pagination | Loads 50, no pages | `CustomersPage.jsx` | Add page state + pagination UI |
| P8 | "Fulfill Items" text | Wrong button label | `OrderDetailPage.jsx:634,928` | Change text to "Fulfill Order" |
| P9 | Orders list no pagination | Loads 50, no pages | `OrdersPage.jsx` | Add page state + pagination UI |
| P10 | Inbox filters do nothing | Missing deps in useEffect | `InboxPage.jsx:83-85` | Add `channel`, `ticketType` to dep array |

---

## Additional Bugs Found (NOT fixed — awaiting approval)

1. **CustomerDetailPage tickets list** — `loadTickets` at line 58 fetches `/tickets?limit=50` and filters client-side. This misses tickets beyond page 1. **Suggested fix:** add `customer_email` as a server-side filter param.

2. **OrdersPage total** — `GET /orders` likely doesn't return a `total` count (the backend returns `res.data.orders`, not `{orders, total}`). Pagination display in P9 may be inaccurate without this. **Suggested fix:** update the backend orders list to return `{orders: [...], total: N}`.

3. **CustomersPage `page` support** — The `/customers` backend likely doesn't support `page` param in its Shopify call. **Suggested fix:** add `page` offset calculation or `since_id` cursor.

4. **RequestPage channel filter includes `instagram` and `telegram`** — These channels appear in the tabs but may not have tickets. Consider filtering to only channels that have at least one ticket.

5. **InboxPage background poll uses stale closure** — The `channel` and `ticketType` variables in the poll useEffect (line 88-101) are captured from closure correctly but the 10s poll overwrites ticket state. Low severity.

---

## Testing Checklist

1. POST same customer+merchant to `/api/external/tickets` twice → second response has `merged: true` and same ticket ID ✓
2. Open ticket for unfulfilled order → AiBanner shows "Starts after fulfillment" not a countdown ✓
3. Open customer with 8+ orders in RequestPage → all orders appear in manual selector ✓
4. Inbox → click ticket → "Close Ticket" button visible, "Resolve" gone ✓
5. Click "Close Ticket" → confirmation modal → confirm → ticket status = closed ✓
6. Returns page with empty DB → shows helpful empty state (not broken) ✓
7. Ticket with images in Inbox list → 📎 indicator visible ✓
8. Open ticket in RequestPage → ticket.images shown after message thread ✓
9. Click ticket from Inbox → back button at top; Inbox sidebar tab stays active ✓
10. Change Type/Channel filter in Inbox → list re-fetches and filters correctly ✓
11. SLA Policies → New Policy → only Email, WhatsApp, Manual channel toggles visible ✓
12. Assign gift card → verify in Shopify admin that customer is linked to the card ✓
13. Click Expire on gift card → modal appears (not browser alert) ✓
14. Open RequestPage ticket with order → Inventory section shows count or "Not tracked" (not blank dashes) ✓
15. Sidebar: Returns tab is directly below Requests tab ✓
16. New Ticket page → back button works; can add image URL rows ✓
17. Request date shows "Apr 6, 2026 · 7:11 PM" format in detail view ✓
18. Requests page → channel tabs do NOT include Shopify ✓
19. Customer detail page → first-letter avatar in header ✓
20. Customers page → pagination controls appear and work ✓
21. Orders page → "Fulfill Order" text on button ✓
22. Orders page → pagination controls appear and work ✓
23. Inbox → select Type filter → list updates; select Channel filter → list updates ✓
