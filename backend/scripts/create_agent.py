# Script to create the first admin agent — run once after setup
# Usage: cd backend && python -m scripts.create_agent
import asyncio
import bcrypt
from app.database import connect_db, get_db
from app.models.agent import AgentInDB

EMAIL = "admin@yourstore.com"
PASSWORD = "1234"
FULL_NAME = "Admin"


async def main():
    await connect_db()
    db = get_db()
    existing = await db.agents.find_one({"email": EMAIL})
    if existing:
        print(f"Agent already exists: {EMAIL}")
        return
    hashed = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    agent = AgentInDB(
        email=EMAIL,
        full_name=FULL_NAME,
        role="admin",
        hashed_password=hashed,
    )
    await db.agents.insert_one(agent.model_dump())
    print(f"Agent created: {agent.email} (id: {agent.id})")


asyncio.run(main())
