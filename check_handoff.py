"""Tests the handover rules with a fake LLM: instant, free, and always the same."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from app import tools
import app.assistant as assistant_module
from app.assistant import Assistant
from app.handoff import detect_handoff_reason

# A temporary tickets file, so data/tickets.json stays untouched
tools.TICKETS_FILE = Path(tempfile.mkdtemp()) / "tickets.json"

failures = []
llm_calls = []


def check(name, condition):
    print(f"{'PASS' if condition else 'FAIL'} | {name}")
    if not condition:
        failures.append(name)


def fake_llm(answer):
    """Replace the real LLM with one that always answers with the same text."""
    def fake(messages, tools, temperature=0.2):
        llm_calls.append(messages)
        return SimpleNamespace(content=answer, tool_calls=None)
    assistant_module.ask_llm_with_tools = fake


def saved_tickets():
    if not tools.TICKETS_FILE.exists():
        return []
    return json.loads(tools.TICKETS_FILE.read_text(encoding="utf-8"))


# --- 1. Keyword rules ---
SHOULD_HAND_OVER = {
    "I want to talk to a human": "human_request",
    "Can I speak to someone about my refund?": "human_request",
    "get me a manager": "human_request",
    "Please transfer me to an agent": "human_request",
    "I need a real person": "human_request",
    "I will take legal action": "sensitive",
    "There is an unauthorized charge on my card": "sensitive",
    "The charger caught fire": "sensitive",
    "I'm going to file a chargeback": "sensitive",
}
for message, reason in SHOULD_HAND_OVER.items():
    check(f"'{message}' -> {reason}", detect_handoff_reason(message) == reason)

SHOULD_NOT = [
    "What are the hours of human support?",
    "Do you offer phone support?",
    "I ordered this for someone else",
    "Can you talk me through the return steps?",
    "Hi, my name is Sue and I want to return an order",
    "Where is my order SL-1003?",
]
for message in SHOULD_NOT:
    check(f"'{message}' -> no handover", detect_handoff_reason(message) is None)

# --- 2. Customer asks for a human: handed over without any LLM call ---
fake_llm("This must not be used")
a = Assistant()
r = a.reply("I want to talk to a human about order SL-1001. My email is emma.carter@example.com")
t = saved_tickets()
check("human request: handoff is True", r["handoff"] is True and r["found"] is False)
check("human request: no LLM call was made", len(llm_calls) == 0)
check("human request: ticket saved with category human_handoff",
      len(t) == 1 and t[0]["category"] == "human_handoff" and t[0]["details"]["reason"] == "human_request")
check("human request: order and email found in the conversation",
      t[0]["order_id"] == "SL-1001" and t[0]["customer_email"] == "emma.carter@example.com")
check("human request: transcript saved",
      t[0]["details"]["transcript"][-1]["content"].startswith("I want to talk to a human"))
check("human request: answer shows the ticket number and promises an email follow-up",
      r["ticket_id"] in r["answer"] and "follow up by email" in r["answer"])

# --- 3. After a handover the bot stays out of it ---
r = a.reply("Where is my order?")
check("after handover: no LLM call and no new ticket",
      len(llm_calls) == 0 and len(saved_tickets()) == 1 and r["handoff"] is True)
check("after handover: answer mentions the same ticket", t[0]["ticket_id"] in r["answer"])
a.reset()
fake_llm("Happy to help.")
r = a.reply("Hello")
check("after reset: a normal conversation works again", r["handoff"] is False and r["answer"] == "Happy to help.")

# --- 4. No email known: tell the customer how to reach support ---
b = Assistant()
r = b.reply("Let me speak to a manager")
check("no email: answer asks the customer to email support",
      "support@shoplite.example" in r["answer"] and "follow up by email" not in r["answer"])
check("no email: ticket has no email or order", saved_tickets()[-1]["customer_email"] is None)

# --- 5. The model says HANDOFF (angry customer) ---
fake_llm("Happy to help.")
c = Assistant()
c.reply("Hi")
fake_llm("HANDOFF")
r = c.reply("This is useless!!")
last = saved_tickets()[-1]
check("model HANDOFF: handed over with reason 'upset'", r["handoff"] is True and last["details"]["reason"] == "upset")
check("model HANDOFF: transcript includes the earlier message",
      [m["content"] for m in last["details"]["transcript"]][0] == "Hi")

# --- 6. Stuck: three unanswered messages in a row ---
d = Assistant()
fake_llm("NOT_FOUND")
r1 = d.reply("Do you offer price matching?")
r2 = d.reply("Do you sell gift cards?")
check("stuck: first two unanswered messages get the normal 'not found' reply",
      r1["handoff"] is False and r2["handoff"] is False and r2["found"] is False)
r3 = d.reply("How many loyalty points do I earn?")
check("stuck: the third is handed over", r3["handoff"] is True and saved_tickets()[-1]["details"]["reason"] == "stuck")

e = Assistant()
fake_llm("NOT_FOUND")
e.reply("q1"); e.reply("q2")
fake_llm("Here is an answer.")
e.reply("q3 (answered)")
fake_llm("NOT_FOUND")
r = e.reply("q4"); r = e.reply("q5")
check("stuck: an answered message resets the count", r["handoff"] is False)
r = e.reply("q6")
check("stuck: three in a row again triggers the handover", r["handoff"] is True)

# --- 7. The model cannot create handover tickets itself ---
check("create_ticket tool rejects the category human_handoff",
      tools.create_ticket("human_handoff", "x").get("error") == "INVALID_CATEGORY")
enum = tools.TOOL_DEFINITIONS[1]["function"]["parameters"]["properties"]["category"]["enum"]
check("the model is not offered human_handoff as a ticket category", "human_handoff" not in enum)

# --- 8. Provider problems (timeouts, rate limits) must not crash or hand over ---
import openai
import app.llm as llm_module
from app.llm import LLMUnavailable


def broken_llm(messages, tools, temperature=0.2):
    raise LLMUnavailable("provider unreachable")


assistant_module.ask_llm_with_tools = broken_llm
f = Assistant()
tickets_before = len(saved_tickets())
results = [f.reply("Where is my package?") for _ in range(4)]
check("API error: the customer gets a friendly message instead of a crash",
      all(r.get("error") is True and "technical problem" in r["answer"] for r in results))
check("API error: nothing is remembered and it never counts as 'stuck'",
      f.history == [] and all(r["handoff"] is False for r in results)
      and len(saved_tickets()) == tickets_before)


class FakeProviderError(openai.OpenAIError):
    pass


def raising(**kwargs):
    raise FakeProviderError("boom")


llm_module.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=raising)))
try:
    llm_module.ask_llm([{"role": "user", "content": "hi"}])
    wrapped = False
except LLMUnavailable:
    wrapped = True
check("llm.py: a library error becomes LLMUnavailable", wrapped)

print(f"\n{len(failures)} check(s) failed" if failures else "\nAll handover checks passed.")
sys.exit(1 if failures else 0)