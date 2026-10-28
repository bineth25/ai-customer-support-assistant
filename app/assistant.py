import json
import re
from app.llm import ask_llm_with_tools
from app.order_agent import fix_ticket_number
from app.policy_search import SEARCH_TOOL_DEFINITION, run_search_tool
from app.prompts import ASSISTANT_SYSTEM_PROMPT, NOT_FOUND_MESSAGE, TOOL_FAILED_MESSAGE
from app.tools import TODAY, TOOL_DEFINITIONS, run_tool

ALL_TOOLS = TOOL_DEFINITIONS + [SEARCH_TOOL_DEFINITION]

MAX_ROUNDS = 6             # tool rounds allowed for one customer message
MAX_HISTORY_MESSAGES = 12  # memory: the last 6 question/answer pairs

# Citations look like [returns_policy-1] or [returns_policy-1, faq-3]
CITATION = r"\[[a-z_]+-\d+(?:\s*,\s*[a-z_]+-\d+)*\]"


def split_citations(text, known_sources):
    """Turn [chunk-id] markers into a source list and remove them from the text."""
    sources = []
    for marker in re.findall(CITATION, text):
        for chunk_id in re.findall(r"[a-z_]+-\d+", marker):
            source = known_sources.get(chunk_id)  # unknown ids are ignored
            if source and source not in sources:
                sources.append(source)
    clean_text = re.sub(r"\s*" + CITATION, "", text).strip()
    return clean_text, sources


class Assistant:
    def __init__(self):
        # Memory: only plain user and assistant text, no tool requests or results
        self.history = []

    def reset(self):
        self.history = []

    def reply(self, user_message):
        """Answer one customer message, using memory and tools."""
        system = {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT.format(today=TODAY.isoformat())}
        messages = [system] + self.history[-MAX_HISTORY_MESSAGES:]
        messages.append({"role": "user", "content": user_message})

        tools_used = []
        known_sources = {}  # chunk id -> "file > section", for every chunk found this turn

        for _ in range(MAX_ROUNDS):
            message = ask_llm_with_tools(messages, ALL_TOOLS)

            if not message.tool_calls:
                text = (message.content or "").strip()
                if not text:
                    break  # an empty answer counts as a failure

                if "NOT_FOUND" in text:
                    answer, sources, found = NOT_FOUND_MESSAGE, [], False
                else:
                    text = fix_ticket_number(text, tools_used)
                    answer, sources = split_citations(text, known_sources)
                    found = True

                # Remember this exchange for the next message
                self.history.append({"role": "user", "content": user_message})
                self.history.append({"role": "assistant", "content": answer})
                return {"answer": answer, "sources": sources, "found": found, "tools_used": tools_used}

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

        # Failure: the exchange is NOT added to memory
        return {"answer": TOOL_FAILED_MESSAGE, "sources": [], "found": False, "tools_used": tools_used}