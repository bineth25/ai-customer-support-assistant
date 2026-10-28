import json
import re
from app.llm import ask_llm_with_tools
from app.prompts import TOOL_SYSTEM_PROMPT, TOOL_FAILED_MESSAGE
from app.tools import TODAY, TOOL_DEFINITIONS, run_tool

# Safety limit: stop if the model keeps asking for tools without finishing
MAX_ROUNDS = 5


def fix_ticket_number(answer, tools_used):
    """The model can garble numbers when it copies them. If a ticket was created,
    make sure the answer shows the real ticket number from our own code."""
    ticket_ids = [
        t["result"]["ticket_id"]
        for t in tools_used
        if t["name"] == "create_ticket" and "ticket_id" in t["result"]
    ]
    if len(ticket_ids) != 1:
        return answer
    real_id = ticket_ids[0]
    if re.search(r"TK-\d+", answer):
        return re.sub(r"TK-\d+", real_id, answer)
    return f"{answer} Your ticket number is {real_id}."


def answer_with_tools(question):
    """Answer a question, letting the model call tools. Returns answer and tools_used."""
    messages = [
        {"role": "system", "content": TOOL_SYSTEM_PROMPT.format(today=TODAY.isoformat())},
        {"role": "user", "content": question},
    ]
    tools_used = []

    for _ in range(MAX_ROUNDS):
        message = ask_llm_with_tools(messages, TOOL_DEFINITIONS)

        # No tool requested: this is the final answer
        if not message.tool_calls:
            answer = (message.content or "").strip()
            if not answer:
                return {"answer": TOOL_FAILED_MESSAGE, "tools_used": tools_used}
            answer = fix_ticket_number(answer, tools_used)
            return {"answer": answer, "tools_used": tools_used}

        # Keep the model's request in the conversation. model_dump keeps extra
        # fields too, like Gemini's hidden thought signature.
        messages.append(message.model_dump(exclude_none=True))

        for call in message.tool_calls:
            name = call.function.name
            arguments = call.function.arguments
            print(f"[TOOL] {name}({arguments})")

            result = run_tool(name, arguments)
            tools_used.append({"name": name, "arguments": arguments, "result": json.loads(result)})

            # Send the result back, linked to the request by its id
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    return {"answer": TOOL_FAILED_MESSAGE, "tools_used": tools_used}