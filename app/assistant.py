import json
import re
from app.handoff import (
    already_handed_over_message,
    create_handoff_ticket,
    detect_handoff_reason,
    handoff_message,
)
from app.llm import LLMUnavailable, ask_llm_with_tools
from app.order_agent import fix_ticket_number
from app.policy_search import SEARCH_TOOL_DEFINITION, run_search_tool
from app.prompts import (
    ASSISTANT_SYSTEM_PROMPT,
    NOT_FOUND_MESSAGE,
    TECH_PROBLEM_MESSAGE,
    TOOL_FAILED_MESSAGE,
)
from app.tools import TODAY, TOOL_DEFINITIONS, run_tool

ALL_TOOLS = TOOL_DEFINITIONS + [SEARCH_TOOL_DEFINITION]

MAX_ROUNDS = 6             # tool rounds allowed for one customer message
MAX_HISTORY_MESSAGES = 12  # memory: the last 6 question/answer pairs
MAX_FAILS_IN_A_ROW = 3     # after this many unanswered messages in a row, hand over

# Citations look like [returns_policy-1] or [returns_policy-1, faq-3]
CITATION = r"\[[a-z_]+-\d+(?:\s*,\s*[a-z_]+-\d+)*\]"

# The model sometimes writes an order number in brackets, like [SL-1001]
ORDER_MARKER = r"\[SL-\d{4}\]"


def split_citations(text, known_sources):
    """Turn [chunk-id] markers into a source list and remove them from the text."""
    sources = []
    for marker in re.findall(CITATION, text):
        for chunk_id in re.findall(r"[a-z_]+-\d+", marker):
            source = known_sources.get(chunk_id)  # unknown ids are ignored
            if source and source not in sources:
                sources.append(source)
    # A marker stuck to the next word ("[x]our") must leave a space, not glue the words
    clean_text = re.sub(r"\s*" + CITATION + r"(?=\w)", " ", text)
    clean_text = re.sub(r"\s*" + CITATION, "", clean_text)
    clean_text = re.sub(r"\s*" + ORDER_MARKER + r"(?=\w)", " ", clean_text)
    clean_text = re.sub(r"\s*" + ORDER_MARKER, "", clean_text).strip()
    return clean_text, sources


class Assistant:
    def __init__(self):
        # Memory: only plain user and assistant text, no tool requests or results
        self.history = []
        self.fail_streak = 0        # unanswered messages in a row
        self.handoff_ticket = None  # set once the conversation was passed to a human

    def reset(self):
        self.history = []
        self.fail_streak = 0
        self.handoff_ticket = None

    def hand_over(self, user_message, reason, tools_used=None):
        """Pass the conversation to a human: save a ticket with the transcript."""
        transcript = self.history[-10:] + [{"role": "user", "content": user_message}]
        ticket = create_handoff_ticket(reason, transcript)
        answer = handoff_message(reason, ticket)

        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": answer})
        self.handoff_ticket = ticket
        return {
            "answer": answer, "sources": [], "found": False, "handoff": True,
            "ticket_id": ticket["ticket_id"], "tools_used": tools_used or [],
        }

    def reply(self, user_message):
        """Answer one customer message, using memory and tools."""
        # 1. Already handed over: the bot stays out of it (no LLM call)
        if self.handoff_ticket:
            return {
                "answer": already_handed_over_message(self.handoff_ticket["ticket_id"]),
                "sources": [], "found": False, "handoff": True,
                "ticket_id": self.handoff_ticket["ticket_id"], "tools_used": [],
            }

        # 2. Rules in code come before the model: explicit requests, legal, fraud, safety
        reason = detect_handoff_reason(user_message)
        if reason:
            return self.hand_over(user_message, reason)

        # 3. Normal path: the model answers, using memory and tools
        system = {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT.format(today=TODAY.isoformat())}
        messages = [system] + self.history[-MAX_HISTORY_MESSAGES:]
        messages.append({"role": "user", "content": user_message})

        tools_used = []
        known_sources = {}  # chunk id -> "file > section", for every chunk found this turn

        for _ in range(MAX_ROUNDS):
            try:
                message = ask_llm_with_tools(messages, ALL_TOOLS)
            except LLMUnavailable:
                # The provider cannot be reached. Tell the customer, remember nothing, and
                # do not count it as "stuck": a network problem is not a reason to hand over.
                return {
                    "answer": TECH_PROBLEM_MESSAGE, "sources": [], "found": False,
                    "handoff": False, "error": True, "tools_used": tools_used,
                }

            if not message.tool_calls:
                text = (message.content or "").strip()
                if not text:
                    break  # an empty answer counts as a failure

                # The model says the customer needs a human (angry, unsolved problem)
                if "HANDOFF" in text:
                    return self.hand_over(user_message, "upset", tools_used)

                if "NOT_FOUND" in text:
                    self.fail_streak += 1
                    if self.fail_streak >= MAX_FAILS_IN_A_ROW:
                        return self.hand_over(user_message, "stuck", tools_used)
                    answer, sources, found = NOT_FOUND_MESSAGE, [], False
                else:
                    self.fail_streak = 0
                    text = fix_ticket_number(text, tools_used)
                    answer, sources = split_citations(text, known_sources)
                    found = True

                # Remember this exchange for the next message
                self.history.append({"role": "user", "content": user_message})
                self.history.append({"role": "assistant", "content": answer})
                return {
                    "answer": answer, "sources": sources, "found": found,
                    "handoff": False, "tools_used": tools_used,
                }

            # The model asked for tools: keep its request, run them, send back the results
            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                name = call.function.name
                arguments = call.function.arguments
                print(f"[TOOL] {name}({arguments})")

                if name == "search_policies":
                    result = run_search_tool(arguments)
                else:
                    result = run_tool(name, arguments)
                data = json.loads(result)
                tools_used.append({"name": name, "arguments": arguments, "result": data})

                if name == "search_policies":
                    for item in data.get("results", []):
                        known_sources[item["id"]] = f"{item['source']} > {item['section']}"

                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        # Failure: the exchange is NOT added to memory, but it counts toward "stuck"
        self.fail_streak += 1
        if self.fail_streak >= MAX_FAILS_IN_A_ROW:
            return self.hand_over(user_message, "stuck", tools_used)
        return {
            "answer": TOOL_FAILED_MESSAGE, "sources": [], "found": False,
            "handoff": False, "tools_used": tools_used,
        }