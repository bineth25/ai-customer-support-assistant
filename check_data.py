"""Checks that the ShopLite documents and order data are consistent."""
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

DATA_DIR = Path("data")
DOCS_DIR = DATA_DIR / "docs"
ORDERS_FILE = DATA_DIR / "orders.json"

EXPECTED_DOCS = [
    "returns_policy.md",
    "shipping_policy.md",
    "payments_and_refunds.md",
    "faq.md",
]
VALID_STATUSES = {"Processing", "Shipped", "Delivered", "Cancelled", "Returned"}
VALID_COUNTRIES = {"US", "CA"}
VALID_METHODS = {"standard", "express"}
REQUIRED_FIELDS = [
    "order_id", "customer_name", "customer_email", "country", "status",
    "order_date", "shipped_date", "delivered_date", "estimated_delivery",
    "shipping_method", "carrier", "tracking_number", "items",
    "shipping_cost", "total", "notes",
]

errors = []


def error(message):
    errors.append(message)


def parse_date(value, label):
    """Turn 'YYYY-MM-DD' into a date. Records an error if it is invalid."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        error(f"{label}: '{value}' is not a valid YYYY-MM-DD date")
        return None


def expected_shipping(country, method, subtotal):
    """Shipping price according to shipping_policy.md."""
    if country == "US" and method == "standard":
        return 0.0 if subtotal >= 50 else 4.99
    if country == "US" and method == "express":
        return 12.99
    if country == "CA" and method == "standard":
        return 9.99
    return 19.99  # Canada express


def check_docs():
    total_words = 0
    for name in EXPECTED_DOCS:
        path = DOCS_DIR / name
        if not path.exists():
            error(f"Missing document: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        total_words += len(text.split())
        if not text.lstrip().startswith("# "):
            error(f"{name}: should start with a '# ' title")
        sections = re.findall(r"^## .+$", text, flags=re.MULTILINE)
        if len(sections) < 3:
            error(f"{name}: needs at least 3 '## ' sections, found {len(sections)}")
    print(f"Documents: {len(EXPECTED_DOCS)} expected, {total_words} words in total")


def check_orders():
    if not ORDERS_FILE.exists():
        error(f"Missing file: {ORDERS_FILE}")
        return

    try:
        orders = json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        error(f"orders.json is not valid JSON: {e}")
        return

    seen_ids = set()
    status_counts = Counter()

    for order in orders:
        oid = order.get("order_id", "<no id>")

        missing = [f for f in REQUIRED_FIELDS if f not in order]
        if missing:
            error(f"{oid}: missing fields {missing}")
            continue

        # Basic format checks
        if not re.fullmatch(r"SL-\d{4}", oid):
            error(f"{oid}: order_id should look like SL-1234")
        if oid in seen_ids:
            error(f"{oid}: duplicate order_id")
        seen_ids.add(oid)
        if "@" not in order["customer_email"]:
            error(f"{oid}: customer_email looks wrong")
        if order["country"] not in VALID_COUNTRIES:
            error(f"{oid}: country must be US or CA")
        if order["shipping_method"] not in VALID_METHODS:
            error(f"{oid}: shipping_method must be standard or express")
        if order["status"] not in VALID_STATUSES:
            error(f"{oid}: unknown status '{order['status']}'")
            continue
        status_counts[order["status"]] += 1

        # Dates
        order_date = parse_date(order["order_date"], f"{oid} order_date")
        shipped = parse_date(order["shipped_date"], f"{oid} shipped_date")
        delivered = parse_date(order["delivered_date"], f"{oid} delivered_date")
        parse_date(order["estimated_delivery"], f"{oid} estimated_delivery")

        dates_in_order = [d for d in (order_date, shipped, delivered) if d]
        if dates_in_order != sorted(dates_in_order):
            error(f"{oid}: dates are not in order (order, shipped, delivered)")

        # Each status needs the right dates
        status = order["status"]
        if status in ("Delivered", "Returned"):
            if not shipped or not delivered:
                error(f"{oid}: {status} order needs shipped_date and delivered_date")
        elif status == "Shipped":
            if not shipped or delivered:
                error(f"{oid}: Shipped order needs shipped_date and no delivered_date")
            if not order["estimated_delivery"]:
                error(f"{oid}: Shipped order needs estimated_delivery")
        else:  # Processing or Cancelled
            if shipped or delivered:
                error(f"{oid}: {status} order must not have shipped/delivered dates")

        # Money
        if not order["items"]:
            error(f"{oid}: order has no items")
        subtotal = 0.0
        for item in order["items"]:
            if item["quantity"] < 1 or item["unit_price"] <= 0:
                error(f"{oid}: bad quantity or price for '{item['name']}'")
            subtotal += item["quantity"] * item["unit_price"]

        want_shipping = expected_shipping(
            order["country"], order["shipping_method"], subtotal
        )
        if abs(order["shipping_cost"] - want_shipping) > 0.005:
            error(
                f"{oid}: shipping_cost is {order['shipping_cost']}, "
                f"policy says {want_shipping}"
            )
        want_total = round(subtotal + order["shipping_cost"], 2)
        if abs(order["total"] - want_total) > 0.005:
            error(f"{oid}: total is {order['total']}, items + shipping = {want_total}")

    print(f"Orders: {len(orders)} found")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")


check_docs()
check_orders()

if errors:
    print(f"\n{len(errors)} problem(s) found:")
    for message in errors:
        print(f"  - {message}")
    sys.exit(1)

print("\nAll checks passed.")