# MongoDB connection management with Motor async driver
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings


class Database:
    client: AsyncIOMotorClient = None
    db = None


class DatabaseB:
    client: AsyncIOMotorClient = None
    db = None


db = Database()
db_b = DatabaseB()


async def connect_db():
    # ── Database A (Gorgias) ──────────────────────────────────────────────────
    try:
        db.client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=5000,
            tz_aware=True,
        )
        db.db = db.client[settings.mongodb_db_name]
        await db.client.admin.command("ping")
        await create_indexes()
        print("MongoDB Database A connected")
    except Exception as e:
        print(f"WARNING: MongoDB Database A connection failed: {e}")
        print("App will start but database operations will fail.")
        if db.client:
            db.db = db.client[settings.mongodb_db_name]

    # ── Database B (Seniors' chatbot) ─────────────────────────────────────────
    if settings.mongodb_b_url:
        try:
            db_b.client = AsyncIOMotorClient(
                settings.mongodb_b_url,
                serverSelectionTimeoutMS=5000,
                tz_aware=True,
            )
            db_b.db = db_b.client[settings.mongodb_b_name]
            await db_b.client.admin.command("ping")
            print("MongoDB Database B (chatbot) connected")
        except Exception as e:
            print(f"WARNING: MongoDB Database B connection failed: {e}")
            if db_b.client:
                db_b.db = db_b.client[settings.mongodb_b_name]
    else:
        print("MongoDB Database B not configured (MONGODB_B_URL not set) — skipping")


async def close_db():
    if db.client:
        db.client.close()
    if db_b.client:
        db_b.client.close()


def get_db():
    return db.db


def get_db_b():
    """Return Database B (seniors' chatbot database). Returns None if not configured."""
    return db_b.db


async def create_indexes():
    d = db.db
    await d.tickets.create_index([("status", 1), ("created_at", -1)])
    await d.tickets.create_index([("customer_email", 1)])
    await d.tickets.create_index([("assignee_id", 1), ("status", 1)])
    await d.tickets.create_index([("sla_due_at", 1)])
    await d.tickets.create_index([("tags", 1)])
    await d.tickets.create_index([("ticket_type", 1), ("status", 1), ("created_at", -1)])
    await d.messages.create_index([("ticket_id", 1), ("created_at", 1)])
    await d.customers.create_index([("email", 1)], unique=True)
    await d.customers.create_index([("shopify_customer_id", 1)])
    await d.order_snapshots.create_index([("shopify_order_id", 1)], unique=True)
    await d.order_snapshots.create_index([("email", 1)])
    await d.automation_rules.create_index([("trigger_event", 1), ("is_active", 1)])
    await d.activity_logs.create_index([("entity_type", 1), ("entity_id", 1), ("created_at", -1)])
    await d.activity_logs.create_index([("customer_email", 1), ("created_at", -1)])
    await d.returns.create_index([("status", 1), ("created_at", -1)])
    await d.returns.create_index([("order_id", 1)])
    await d.returns.create_index([("customer_email", 1)])
    # WhatsApp indexes
    await d.tickets.create_index([("whatsapp_phone", 1), ("channel", 1), ("status", 1)])
    await d.customers.create_index([("phone", 1)])
    await d.messages.create_index([("whatsapp_message_id", 1)])
    await d.merchants.create_index([("whatsapp_phone_number_id", 1)])
    # Instagram indexes
    await d.tickets.create_index([("instagram_user_id", 1), ("channel", 1), ("status", 1)])
    await d.messages.create_index([("instagram_message_id", 1)])
    await d.merchants.create_index([("instagram_page_id", 1)])
    # Merchant domain index for external ticket handshake
    await d.merchants.create_index([("shopify_store_domain", 1)], unique=True, sparse=True)
    await d.tickets.create_index([("shopify_order_id", 1)])
    await d.tickets.create_index([("shopify_order_number", 1)])
    # Gift cards
    await d.gift_cards.create_index([("customer_email", 1)])
    await d.gift_cards.create_index([("shopify_gift_card_id", 1)])
    print("Indexes created")
