import re
from app.tools import save_ticket

# Rules in code, checked BEFORE any LLM call: fast, free, and the model cannot talk its
# way around them. These lists are a starting point. Tune them as you see real messages.

# "I want to talk to a human", "get me a manager", "transfer me to an agent" ...
HUMAN_REQUEST = re.compile(
    r"\b(?:talk|speak|chat|connect|transfer|escalate)\b.{0,30}?"
    r"\b(?:human|person|agent|representative|manager|supervisor|someone|somebody)\b"
    r"|\b(?:real|actual|live)\s+(?:person|human|agent)\b"
    r"|\bhuman\s+agent\b"
    r"|\b(?:i\s+want|i\s+need|give\s+me|get\s+me)\s+(?:a|an|the)?\s*(?:real\s+|live\s+)?"
    r"(?:human|person|agent|manager|supervisor|representative)\b",
    re.IGNORECASE,
)

# Topics a bot should never handle alone: legal threats, fraud, physical safety
SENSITIVE = re.compile(
    r"\b(?:lawyer|attorney|suing|lawsuit|legal\s+action|consumer\s+protection)\b"
    r"|\bsue\s+(?:you|them|shoplite|this\s+company|the\s+company)\b"
    r"|\b(?:fraud|fraudulent|scam|scammed|chargeback"
    r"|unauthori[sz]ed\s+(?:charge|transaction|purchase|payment))\b"
    r"|\b(?:caught\s+fire|on\s+fire|electric\s+shock|exploded|injur(?:ed|y|ies)"
    r"|burned\s+(?:me|my)|burnt\s+(?:me|my))\b",
    re.IGNORECASE,
)

INTROS = {
    "human_request": "Of course, I'm passing your conversation to a human agent.",
    "sensitive": "This needs a human agent, so I'm passing your conversation to one.",
    "upset": "I'm sorry for the trouble. I'm passing your conversation to a human agent.",
    "stuck": "I'm sorry I haven't been able to help. I'm passing your conversation to a human agent.",
    "verification": "I couldn't verify those order details, so I'm passing your conversation to a human agent.",
}

HOURS = "Human support is available Monday to Friday, 9 AM to 6 PM Eastern Time."


def detect_handoff_reason(message):
    """Return a reason if this message must go to a human, otherwise None."""
    if SENSITIVE.search(message):
        return "sensitive"
    if HUMAN_REQUEST.search(message):
        return "human_request"
    return None


def create_handoff_ticket(reason, transcript):
    """Save a ticket with the conversation, so the human does not start from zero."""
    customer_messages = [m["content"] for m in transcript if m["role"] == "user"]
    customer_text = " ".join(customer_messages)
    order_ids = re.findall(r"SL-\d{4}", customer_text, flags=re.IGNORECASE)
    emails = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", customer_text)

    # After failed order checks the typed email may belong to someone else,
    # so it is never saved as the person to contact.
    contact_email = None if reason == "verification" else (emails[-1] if emails else None)

    return save_ticket(
        "human_handoff",
        f"Handoff ({reason}). Last customer message: {customer_messages[-1]}",
        order_id=order_ids[-1] if order_ids else None,
        customer_email=contact_email,
        details={"reason": reason, "transcript": transcript},
    )


def handoff_message(reason, ticket):
    """What the customer sees. Only promises what the policies support: an email
    follow-up and the published support hours, no invented response times."""
    if ticket["customer_email"]:
        middle = (
            "They can see our conversation, so you won't need to repeat yourself, "
            f"and they will follow up by email. Your ticket number is {ticket['ticket_id']}."
        )
    else:
        middle = (
            "They can see our conversation, but I don't have your email address, so please "
            f"email support@shoplite.example and quote ticket number {ticket['ticket_id']}."
        )
    return f"{INTROS[reason]} {middle} {HOURS}"


def already_handed_over_message(ticket_id):
    return (
        f"Your conversation has already been passed to a human agent (ticket {ticket_id}). "
        "Please wait for their reply. To ask something else, start a new conversation."
    )