# FastAPI application entry point — registers all routers and lifecycle events
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import connect_db, close_db

app = FastAPI(title="Shopify Helpdesk API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await connect_db()
    from app.services.sla_worker import start_sla_scheduler
    start_sla_scheduler()


@app.on_event("shutdown")
async def shutdown():
    await close_db()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# Register all routers
from app.routers import auth, tickets, customers, orders, returns, webhooks, email_inbound, ai, macros, automations, sla, history, analytics

app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(orders.router)
app.include_router(returns.router)
app.include_router(webhooks.router)
app.include_router(email_inbound.router)
app.include_router(ai.router)
app.include_router(macros.router)
app.include_router(automations.router)
app.include_router(sla.router)
app.include_router(history.router)
app.include_router(analytics.router)
