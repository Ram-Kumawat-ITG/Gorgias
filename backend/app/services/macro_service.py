# Macro service — renders Jinja2 template macros with ticket/customer/order context
from jinja2 import Environment, BaseLoader, Undefined
from app.database import get_db


class SilentUndefined(Undefined):
    def __str__(self):
        return "[unknown]"

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return False


env = Environment(loader=BaseLoader(), undefined=SilentUndefined)


async def render_macro(body: str, ticket: dict) -> str:
    db = get_db()

    customer = await db.customers.find_one({"email": ticket.get("customer_email")})
    if not customer:
        customer = {}

    latest_order = await db.order_snapshots.find_one(
        {"email": ticket.get("customer_email")},
        sort=[("created_at", -1)],
    )
    if not latest_order:
        latest_order = {}

    context = {
        "customer": {
            "first_name": customer.get("first_name", ""),
            "last_name": customer.get("last_name", ""),
            "full_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            "email": customer.get("email", ""),
        },
        "ticket": {
            "id": ticket.get("id", ""),
            "subject": ticket.get("subject", ""),
            "status": ticket.get("status", ""),
        },
        "order": {
            "number": latest_order.get("order_number", ""),
            "tracking_url": latest_order.get("tracking_url", ""),
            "tracking_number": latest_order.get("tracking_number", ""),
            "fulfillment_status": latest_order.get("fulfillment_status", ""),
            "total_price": latest_order.get("total_price", ""),
        },
    }

    template = env.from_string(body)
    return template.render(**context)
