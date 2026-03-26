# Agent authentication router — JWT login and token validation
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
import bcrypt
from datetime import datetime, timedelta
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(agent_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=12)
    return jwt.encode({"sub": agent_id, "exp": expire}, settings.secret_key, algorithm="HS256")


async def get_current_agent(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        agent_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    db = get_db()
    agent = await db.agents.find_one({"id": agent_id, "is_active": True})
    if not agent:
        raise HTTPException(status_code=401, detail="Agent not found")
    return agent


@router.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    db = get_db()
    agent = await db.agents.find_one({"email": form.username})
    if not agent or not verify_password(form.password, agent.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "access_token": create_token(agent["id"]),
        "token_type": "bearer",
        "agent": {
            "id": agent["id"],
            "email": agent["email"],
            "full_name": agent["full_name"],
            "role": agent["role"],
        },
    }


@router.get("/me")
async def me(agent=Depends(get_current_agent)):
    return {k: v for k, v in agent.items() if k not in ["_id", "hashed_password"]}
