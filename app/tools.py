import json
from datetime import date, timedelta
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
        result["warranty_end"] = warranty_end.isoformat()
        result["under_warranty"] = TODAY <= warranty_end
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