import json
from datetime import date, datetime, timedelta
from pathlib import Path

ORDERS_FILE = Path("data/orders.json")

# "Today" is fixed so every test run gives the same answer.
# The order dates in orders.json are built around this day.
TODAY = date(2026, 10, 25)

# These numbers come from the policy documents.
# If a policy changes, change it here too.
RETURN_WINDOW_DAYS = 21
WARRANTY_MONTHS = 12
LATE_AFTER_BUSINESS_DAYS = 5

TICKETS_FILE = Path("data/tickets.json")
TICKET_CATEGORIES = ["late_package", "damaged_item", "refund_issue", "warranty", "other"]

def create_ticket(category, summary, order_id=None, customer_email=None):
    """Save a support ticket for a human agent to handle."""
    if category not in TICKET_CATEGORIES:
        return {
            "error": "INVALID_CATEGORY",
            "message": f"category must be one of {TICKET_CATEGORIES}",
        }
    summary = str(summary).strip()
    if not summary:
        return {"error": "EMPTY_SUMMARY", "message": "summary cannot be empty."}

    tickets = []
    if TICKETS_FILE.exists():
        tickets = json.loads(TICKETS_FILE.read_text(encoding="utf-8"))

    ticket = {
        "ticket_id": f"TK-{len(tickets) + 1:04d}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "open",
        "category": category,
        "summary": summary[:500],
        "order_id": str(order_id).strip().upper() if order_id else None,
        "customer_email": str(customer_email).strip().lower() if customer_email else None,
    }
    tickets.append(ticket)
    TICKETS_FILE.write_text(json.dumps(tickets, indent=2), encoding="utf-8")

    return {
        "ticket_id": ticket["ticket_id"],
        "status": "open",
        "message": "Ticket created. A human agent will follow up by email.",
    }

def add_months(start, months):
    """Return the same day N months later (step back for shorter months)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = start.day
    while True:
        try:
            return date(year, month, day)
        except ValueError:  # e.g. 31 February does not exist
            day -= 1


def business_days_after(start, end):
    """Count Monday-Friday days after `start`, up to and including `end`.
    Public holidays are ignored to keep this simple."""
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 0 = Monday ... 4 = Friday
            count += 1
    return count


def load_orders():
    return json.loads(ORDERS_FILE.read_text(encoding="utf-8"))


def describe_order(order):
    """Pick the fields the assistant may see, plus facts computed in code."""
    result = {
        "order_id": order["order_id"],
        "status": order["status"],
        "country": order["country"],
        "order_date": order["order_date"],
        "shipped_date": order["shipped_date"],
        "delivered_date": order["delivered_date"],
        "estimated_delivery": order["estimated_delivery"],
        "shipping_method": order["shipping_method"],
        "carrier": order["carrier"],
        "tracking_number": order["tracking_number"],
        "items": order["items"],
        "shipping_cost": order["shipping_cost"],
        "total": order["total"],
        "notes": order["notes"],
    }

    status = order["status"]
    if status == "Delivered":
        delivered = date.fromisoformat(order["delivered_date"])
        deadline = delivered + timedelta(days=RETURN_WINDOW_DAYS)
        warranty_end = add_months(delivered, WARRANTY_MONTHS)
        result["days_since_delivery"] = (TODAY - delivered).days
        result["return_deadline"] = deadline.isoformat()
        result["return_window_open"] = TODAY <= deadline  # time only, not item type
        result["return_days_left"] = max((deadline - TODAY).days, 0)
        result["warranty_period_end"] = warranty_end.isoformat()
        result["warranty_period_open"] = TODAY <= warranty_end  # time only, not item type
    elif status == "Shipped":
        estimated = date.fromisoformat(order["estimated_delivery"])
        late_days = business_days_after(estimated, TODAY)
        result["business_days_past_estimate"] = late_days
        result["late_enough_to_report"] = late_days >= LATE_AFTER_BUSINESS_DAYS
    elif status == "Processing":
        result["can_cancel"] = True
        result["can_change_address"] = True

    return result


def lookup_order(order_id, email):
    """Find an order. It needs BOTH the order number and the customer's email."""
    order_id = str(order_id).strip().upper()
    email = str(email).strip().lower()

    for order in load_orders():
        if order["order_id"] == order_id and order["customer_email"].lower() == email:
            return describe_order(order)

    # Same answer for "no such order" and "wrong email", so nobody can
    # use this tool to find out which order numbers exist.
    return {
        "error": "ORDER_NOT_FOUND",
        "message": "No order matches that order number and email.",
    }



# What the model sees: a name, a description, and the arguments each tool takes.
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": (
                "Look up a ShopLite order: its status, dates, items, total, and "
                "whether it can still be returned. Needs BOTH the order number and "
                "the email used for the order. If the customer has not given both, "
                "ask for the missing one instead of calling this tool. Never guess."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order number, like SL-1001",
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address used for the order",
                    },
                },
                "required": ["order_id", "email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": (
                "Create a support ticket so a human agent follows up. Use it when "
                "the customer has a problem the assistant cannot solve itself, such "
                "as a package that is late enough to report, a damaged item, or a "
                "refund problem."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": TICKET_CATEGORIES},
                    "summary": {
                        "type": "string",
                        "description": "One or two sentences describing the problem",
                    },
                    "order_id": {"type": "string", "description": "Order number, if known"},
                    "customer_email": {"type": "string", "description": "Customer email, if known"},
                },
                "required": ["category", "summary"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "lookup_order": lookup_order,
    "create_ticket": create_ticket,
}


def run_tool(name, arguments_json):
    """Run a tool the model asked for. Always returns a JSON string, never crashes."""
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return json.dumps({"error": "UNKNOWN_TOOL", "message": f"No tool named {name}."})

    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "BAD_ARGUMENTS", "message": "Arguments were not valid JSON."})

    try:
        result = function(**arguments)
    except TypeError as e:  # missing or unexpected argument
        return json.dumps({"error": "BAD_ARGUMENTS", "message": str(e)})

    return json.dumps(result)