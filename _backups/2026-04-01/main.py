# FastAPI application entry point — registers all routers and lifecycle events
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import connect_db, close_db
from app.config import settings
from app.services.sla_worker import start_sla_scheduler, stop_sla_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_db()
    start_sla_scheduler()
    yield
    # Shutdown
    stop_sla_scheduler()
    await close_db()
    from app.services.shopify_client import close_shopify_client
    await close_shopify_client()


app = FastAPI(title="Shopify Helpdesk API", version="2.0.0", lifespan=lifespan)

# CORS — reads allowed origins from env (comma-separated), falls back to localhost for dev
_raw_origins = getattr(settings, "cors_origins", "") or ""
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ── Register all routers ──────────────────────────────────────────────────────
from app.routers import (
    tickets, customers, orders, returns,
    webhooks, email_inbound, ai, macros, automations,
    history, analytics, shopify, channels,
    instagram, merchants, whatsapp, sla,
)
from app.routers import media

app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(orders.router)
app.include_router(returns.router)
app.include_router(webhooks.router)
app.include_router(email_inbound.router)
app.include_router(ai.router)
app.include_router(macros.router)
app.include_router(automations.router)
app.include_router(history.router)
app.include_router(analytics.router)
app.include_router(shopify.router)
app.include_router(channels.router)
app.include_router(instagram.router)
app.include_router(merchants.router)
app.include_router(whatsapp.router)
app.include_router(sla.router)
app.include_router(media.router)