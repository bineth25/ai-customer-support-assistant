"""Checks the tools without any LLM, so results are instant and always the same."""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

from app import tools

failures = []


def check(name, condition):
    print(f"{'PASS' if condition else 'FAIL'} | {name}")
    if not condition:
        failures.append(name)


# --- lookup_order: facts computed in code (today is fixed at 2026-10-25) ---
r = tools.lookup_order("SL-1001", "emma.carter@example.com")
check("SL-1001 delivered 5 days ago: return window open, 16 days left",
      r["status"] == "Delivered" and r["days_since_delivery"] == 5
      and r["return_window_open"] is True and r["return_days_left"] == 16)

r = tools.lookup_order("SL-1002", "liam.brooks@example.com")
check("SL-1002 delivered 30 days ago: return window closed",
      r["days_since_delivery"] == 30 and r["return_window_open"] is False
      and r["return_days_left"] == 0)

r = tools.lookup_order("SL-1007", "lucas.martin@example.com")
check("SL-1007 delivered 18 days ago: 3 days left",
      r["days_since_delivery"] == 18 and r["return_days_left"] == 3)

r = tools.lookup_order("SL-1010", "isabella.rossi@example.com")
check("SL-1010 delivered 8 months ago: window closed but under warranty",
      r["return_window_open"] is False and r["under_warranty"] is True
      and r["warranty_end"] == "2027-02-10")

r = tools.lookup_order("SL-1003", "noah.patel@example.com")
check("SL-1003 shipped, estimate still in the future: not late",
      r["business_days_past_estimate"] == 0 and r["late_enough_to_report"] is False)

r = tools.lookup_order("SL-1008", "ava.thompson@example.com")
check("SL-1008 shipped, 5 business days past the estimate: can be reported",
      r["business_days_past_estimate"] == 5 and r["late_enough_to_report"] is True)

r = tools.lookup_order("SL-1004", "olivia.reed@example.com")
check("SL-1004 processing: can cancel and change address",
      r["can_cancel"] is True and r["can_change_address"] is True)

# --- lookup_order: security and input handling ---
wrong_email = tools.lookup_order("SL-1001", "someone.else@example.com")
no_such_order = tools.lookup_order("SL-9999", "emma.carter@example.com")
check("wrong email is refused", wrong_email.get("error") == "ORDER_NOT_FOUND")
check("wrong email and unknown order give the same answer (no probing)",
      wrong_email == no_such_order)

r = tools.lookup_order("  sl-1001 ", "EMMA.CARTER@example.com")
check("extra spaces and capital letters are tolerated", r.get("order_id") == "SL-1001")

r = tools.lookup_order("SL-1001", "emma.carter@example.com")
check("customer email and name are not returned",
      "customer_email" not in r and "customer_name" not in r)

# --- helper functions ---
check("add_months handles short months", tools.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28))
check("add_months handles year change", tools.add_months(date(2026, 11, 15), 3) == date(2027, 2, 15))

# --- create_ticket (uses a temporary file so data/tickets.json stays untouched) ---
with tempfile.TemporaryDirectory() as folder:
    tools.TICKETS_FILE = Path(folder) / "tickets.json"

    t1 = tools.create_ticket("late_package", "Package SL-1008 is late", "sl-1008", "Ava.Thompson@example.com")
    t2 = tools.create_ticket("other", "General problem")
    check("first ticket is TK-0001", t1["ticket_id"] == "TK-0001")
    check("second ticket is TK-0002", t2["ticket_id"] == "TK-0002")

    saved = json.loads(tools.TICKETS_FILE.read_text(encoding="utf-8"))
    check("tickets are saved, with order id and email cleaned up",
          len(saved) == 2 and saved[0]["order_id"] == "SL-1008"
          and saved[0]["customer_email"] == "ava.thompson@example.com")

    check("unknown category is rejected",
          tools.create_ticket("nonsense", "x").get("error") == "INVALID_CATEGORY")
    check("empty summary is rejected",
          tools.create_ticket("other", "   ").get("error") == "EMPTY_SUMMARY")
    check("rejected tickets are not saved",
          len(json.loads(tools.TICKETS_FILE.read_text(encoding="utf-8"))) == 2)

# --- run_tool: the function the model's requests go through ---
good = json.loads(tools.run_tool("lookup_order", '{"order_id": "SL-1001", "email": "emma.carter@example.com"}'))
check("run_tool runs a valid request", good.get("status") == "Delivered")
check("run_tool survives broken JSON",
      json.loads(tools.run_tool("lookup_order", "{not json")).get("error") == "BAD_ARGUMENTS")
check("run_tool survives a missing argument",
      json.loads(tools.run_tool("lookup_order", '{"order_id": "SL-1001"}')).get("error") == "BAD_ARGUMENTS")
check("run_tool survives an unknown tool",
      json.loads(tools.run_tool("delete_everything", "{}")).get("error") == "UNKNOWN_TOOL")

print(f"\n{len(failures)} check(s) failed" if failures else "\nAll tool checks passed.")
sys.exit(1 if failures else 0)