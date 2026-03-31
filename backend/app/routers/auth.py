"""
Auth compatibility shim

The project previously used JWT-based agent authentication with
login/signup endpoints. These have been removed per the request to
disable login/signup. Many routers depend on `get_current_agent` —
to avoid changing all those call sites we provide a simple shim that
returns a default active agent (if one exists) or a lightweight
placeholder agent. This effectively removes the need for client
login while keeping handler signatures intact.
"""
from fastapi import Depends
from app.database import get_db


async def get_current_agent(_=None):
    """Return the first active agent from DB or a placeholder.

    This replaces token-based lookup so endpoints that depend on
    `get_current_agent` continue to receive an `agent` dict.
    """
    db = get_db()
    try:
        agent = await db.agents.find_one({"is_active": True})
        if agent:
            # strip sensitive fields
            agent.pop("_id", None)
            agent.pop("hashed_password", None)
            return agent
    except Exception:
        pass
    # Fallback placeholder
    return {"id": "local-admin", "email": "admin@local", "full_name": "Local Admin", "role": "admin"}
