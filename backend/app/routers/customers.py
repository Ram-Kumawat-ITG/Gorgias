# Customer router — fetches customer profile and Shopify order data
from fastapi import APIRouter, Depends
from app.routers.auth import get_current_agent
from app.services.shopify_sync import fetch_and_sync_customer, fetch_customer_orders

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/{email}/profile")
async def get_customer_profile(email: str, agent=Depends(get_current_agent)):
    customer = await fetch_and_sync_customer(email)
    orders = []
    if customer.get("shopify_customer_id"):
        orders = await fetch_customer_orders(customer["shopify_customer_id"])
    return {"customer": customer, "orders": orders}
