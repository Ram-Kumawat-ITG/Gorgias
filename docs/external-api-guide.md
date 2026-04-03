# Gorgias Helpdesk — External API Integration Guide

## Overview

The Gorgias Helpdesk External API allows registered Shopify stores to create support tickets on our platform programmatically. If your app is installed alongside ours on a Shopify store, you can use this API to route customer support requests into our helpdesk system.

**Base URL**: `https://gorgias.onrender.com`

---

## Getting Started

### Step 1: Request Registration
Contact our team to register your Shopify store. Provide:
- Your store domain (e.g., `your-store.myshopify.com`)
- Your app name

### Step 2: Receive Your API Key
Our admin will register your store and give you an API key that looks like:
```
ghd_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
```
**Save this key immediately.** It is shown only once. If lost, we must regenerate it (which invalidates the old one).

### Step 3: Start Making API Calls
Every request to our API requires two headers:
```
X-Shop-Domain: your-store.myshopify.com
X-API-Key: ghd_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
```

---

## Authentication

We use an **API Key + Shop Domain** handshake:

1. You send `X-Shop-Domain` and `X-API-Key` headers with every request.
2. We look up your shop domain in our database.
3. We verify the API key hash matches what we have on file.
4. If both match and your account is active, the request proceeds.

**No OAuth, no Shopify access token, no JWT needed.**

### What happens when auth fails:

| Scenario | HTTP Code | Error Message |
|---|---|---|
| Missing `X-Shop-Domain` header | 422 | `X-Shop-Domain header is required` |
| Missing `X-API-Key` header | 422 | `X-API-Key header is required` |
| Invalid domain format | 422 | `X-Shop-Domain must end with .myshopify.com` |
| Store not registered | 401 | `Store not registered. Please install the app first.` |
| Wrong API key | 401 | `Invalid API key` |
| Store deactivated | 403 | `Store access disabled. Contact the administrator.` |

---

## Endpoints

### Create Ticket

```
POST /api/external/tickets
```

**Headers:**

| Header | Required | Description |
|---|---|---|
| `Content-Type` | Yes | `application/json` |
| `X-Shop-Domain` | Yes | Your Shopify store domain |
| `X-API-Key` | Yes | Your API key (provided during registration) |

**Request Body:**

| Field | Type | Required | Default | Description | Example |
|---|---|---|---|---|---|
| `subject` | string | **Yes** | — | Ticket subject | `"Refund request for order #1042"` |
| `customer_email` | string | **Yes** | — | Customer email | `"alice@gmail.com"` |
| `customer_name` | string | No | Auto-detected | Customer name | `"Alice Smith"` |
| `shopify_customer_id` | string | No | Auto-detected | Shopify customer ID | `"7891234560"` |
| `channel` | enum | No | `"manual"` | One of: `email`, `manual`, `shopify`, `whatsapp`, `chat`, `instagram` | `"email"` |
| `priority` | enum | No | `"normal"` | One of: `low`, `normal`, `high`, `urgent` | `"urgent"` |
| `tags` | array | No | `[]` | Tags for categorization | `["refund", "vip"]` |
| `initial_message` | string | No | `null` | First customer message | `"My order arrived damaged..."` |

**Success Response (200):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "subject": "Refund request for order #1042",
  "customer_email": "alice@gmail.com",
  "customer_name": "Alice Smith",
  "source_store": "your-store.myshopify.com",
  "merchant_id": "m1e2r3c4-h5a6-n7t8-id90-1234567890ab",
  "channel": "email",
  "status": "open",
  "priority": "urgent",
  "ticket_type": "refund",
  "tags": ["refund", "vip"],
  "created_at": "2026-04-03T12:00:00.000000",
  "updated_at": "2026-04-03T12:00:00.000000"
}
```

---

## cURL Examples

### 1. Create ticket (success — minimum fields)
```bash
curl -X POST https://gorgias.onrender.com/api/external/tickets \
  -H "Content-Type: application/json" \
  -H "X-Shop-Domain: store-alpha.myshopify.com" \
  -H "X-API-Key: ghd_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8" \
  -d '{
    "subject": "Order not delivered",
    "customer_email": "john@example.com"
  }'
```

### 2. Create ticket (success — all fields)
```bash
curl -X POST https://gorgias.onrender.com/api/external/tickets \
  -H "Content-Type: application/json" \
  -H "X-Shop-Domain: store-alpha.myshopify.com" \
  -H "X-API-Key: ghd_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8" \
  -d '{
    "subject": "Refund request for damaged item - Order #1042",
    "customer_email": "alice.smith@gmail.com",
    "customer_name": "Alice Smith",
    "shopify_customer_id": "7891234560",
    "channel": "email",
    "priority": "urgent",
    "tags": ["refund", "damaged", "vip-customer"],
    "initial_message": "Hi, I received order #1042 today but the item was damaged in shipping. I would like a full refund."
  }'
```

### 3. Error — wrong API key (401)
```bash
curl -X POST https://gorgias.onrender.com/api/external/tickets \
  -H "Content-Type: application/json" \
  -H "X-Shop-Domain: store-alpha.myshopify.com" \
  -H "X-API-Key: ghd_live_WRONG_KEY_HERE" \
  -d '{"subject": "Test", "customer_email": "test@test.com"}'
# Response: {"detail": "Invalid API key"}
```

### 4. Error — unregistered store (401)
```bash
curl -X POST https://gorgias.onrender.com/api/external/tickets \
  -H "Content-Type: application/json" \
  -H "X-Shop-Domain: unknown-store.myshopify.com" \
  -H "X-API-Key: ghd_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8" \
  -d '{"subject": "Test", "customer_email": "test@test.com"}'
# Response: {"detail": "Store not registered. Please install the app first."}
```

### 5. Error — missing headers (422)
```bash
curl -X POST https://gorgias.onrender.com/api/external/tickets \
  -H "Content-Type: application/json" \
  -d '{"subject": "Test", "customer_email": "test@test.com"}'
# Response: {"detail": "X-Shop-Domain header is required"}
```

---

## Admin API (For Our Team Only)

### Register a new store
```bash
curl -X POST https://gorgias.onrender.com/api/admin/merchants/register \
  -H "Content-Type: application/json" \
  -d '{
    "shop_domain": "new-store.myshopify.com",
    "app_name": "PartnerApp",
    "permissions": ["create_ticket"],
    "rate_limit": 100
  }'
```

### List all registered stores
```bash
curl -X GET https://gorgias.onrender.com/api/admin/merchants
```

### Regenerate API key
```bash
curl -X POST https://gorgias.onrender.com/api/admin/merchants/store-b.myshopify.com/regenerate-key
```

### Deactivate a store
```bash
curl -X PATCH https://gorgias.onrender.com/api/admin/merchants/store-b.myshopify.com/deactivate
```

### Reactivate a store
```bash
curl -X PATCH https://gorgias.onrender.com/api/admin/merchants/store-b.myshopify.com/activate
```

---

## Security Notes

- API keys are hashed (SHA-256) before storage. We never store the raw key.
- The raw key is shown exactly **once** at registration time.
- Keys can be regenerated (old key is instantly invalidated).
- Stores can be deactivated to revoke access immediately.
- Every API call updates `last_used_at` for audit purposes.
- Shop domain must be a valid `.myshopify.com` domain.
