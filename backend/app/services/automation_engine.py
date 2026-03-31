# Automation engine — evaluates if-then rules against ticket events
from app.database import get_db


async def evaluate_automations(event: str, ticket: dict, message: dict = None):
    db = get_db()
    rules = await db.automation_rules.find(
        {"trigger_event": event, "is_active": True}
    ).sort("priority", 1).to_list(100)

    for rule in rules:
        if _check_conditions(rule.get("conditions", []), ticket, message):
            await _execute_actions(rule.get("actions", []), ticket, db)
            if rule.get("stop_processing"):
                break


def _check_conditions(conditions: list, ticket: dict, message: dict = None) -> bool:
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "")
        value = cond.get("value", "")

        if field == "message_body":
            actual = message.get("body", "") if message else ""
        else:
            actual = ticket.get(field, "")

        if isinstance(actual, list):
            actual_str = ", ".join(actual)
        else:
            actual_str = str(actual) if actual else ""

        if operator == "equals" and actual_str.lower() != str(value).lower():
            return False
        elif operator == "contains" and str(value).lower() not in actual_str.lower():
            return False
        elif operator == "not_contains" and str(value).lower() in actual_str.lower():
            return False
        elif operator == "is_empty" and actual_str.strip():
            return False

    return True


async def _execute_actions(actions: list, ticket: dict, db):
    ticket_id = ticket.get("id")
    for action in actions:
        action_type = action.get("type", "")
        value = action.get("value", "")

        if action_type == "add_tag":
            await db.tickets.update_one(
                {"id": ticket_id}, {"$addToSet": {"tags": value}}
            )
        elif action_type == "set_priority":
            await db.tickets.update_one(
                {"id": ticket_id}, {"$set": {"priority": value}}
            )
        elif action_type == "assign_to":
            await db.tickets.update_one(
                {"id": ticket_id}, {"$set": {"assignee_id": value}}
            )
        elif action_type == "set_status":
            await db.tickets.update_one(
                {"id": ticket_id}, {"$set": {"status": value}}
            )
        elif action_type == "set_type":
            await db.tickets.update_one(
                {"id": ticket_id}, {"$set": {"ticket_type": value}}
            )
        elif action_type == "send_macro":
            macro = await db.macros.find_one({"id": value})
            if macro:
                from app.services.macro_service import render_macro
                rendered = await render_macro(macro["body"], ticket)
                from app.models.message import MessageInDB
                msg = MessageInDB(
                    ticket_id=ticket_id,
                    body=rendered,
                    sender_type="system",
                    ai_generated=False,
                )
                await db.messages.insert_one(msg.model_dump())
