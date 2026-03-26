# MongoDB connection management with Motor async driver
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings


class Database:
    client: AsyncIOMotorClient = None
    db = None


db = Database()


async def connect_db():
    try:
        db.client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=5000,
        )
        db.db = db.client[settings.mongodb_db_name]
        # Ping to verify the connection works
        await db.client.admin.command("ping")
        await create_indexes()
        print("MongoDB connected")
    except Exception as e:
        print(f"WARNING: MongoDB connection failed: {e}")
        print("App will start but database operations will fail.")
        # Still set db reference so app can start
        if db.client:
            db.db = db.client[settings.mongodb_db_name]


async def close_db():
    if db.client:
        db.client.close()


def get_db():
    return db.db


async def create_indexes():
    d = db.db
    await d.tickets.create_index([("status", 1), ("created_at", -1)])
    await d.tickets.create_index([("customer_email", 1)])
    await d.tickets.create_index([("assignee_id", 1), ("status", 1)])
    await d.tickets.create_index([("sla_due_at", 1)])
    await d.tickets.create_index([("tags", 1)])
    await d.messages.create_index([("ticket_id", 1), ("created_at", 1)])
    await d.customers.create_index([("email", 1)], unique=True)
    await d.customers.create_index([("shopify_customer_id", 1)])
    await d.order_snapshots.create_index([("shopify_order_id", 1)], unique=True)
    await d.order_snapshots.create_index([("email", 1)])
    await d.automation_rules.create_index([("trigger_event", 1), ("is_active", 1)])
    await d.activity_logs.create_index([("entity_type", 1), ("entity_id", 1), ("created_at", -1)])
    await d.activity_logs.create_index([("customer_email", 1), ("created_at", -1)])
    print("Indexes created")
