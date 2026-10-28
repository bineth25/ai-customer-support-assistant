import json
from app.rag import MAX_DISTANCE, TOP_K
from app.vectorstore import search

# What the model sees about this tool
SEARCH_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_policies",
        "description": (
            "Search ShopLite's policy documents (returns, shipping, payments and "
            "refunds, FAQ). Use it for any question about rules, fees, deadlines, "
            "prices, shipping options, how-to steps, or which items can or cannot "
            "be returned. The search does not see the conversation, so write the "
            "query so it makes sense on its own, with the topic words included "
            "(for example 'return fee when customer changes their mind')."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A short, self-contained question or keywords",
                },
            },
            "required": ["query"],
        },
    },
}


def search_policies(query):
    """Find the policy chunks closest to the query. Far-away chunks are dropped."""
    query = str(query).strip()
    if not query:
        return {"error": "EMPTY_QUERY", "message": "query cannot be empty."}

    hits = [h for h in search(query, top_k=TOP_K) if h["distance"] <= MAX_DISTANCE]
    if not hits:
        return {"results": [], "message": "No relevant policy text found."}

    return {
        "results": [
            {"id": h["id"], "source": h["source"], "section": h["section"], "text": h["text"]}
            for h in hits
        ]
    }


def run_search_tool(arguments_json):
    """Same job as run_tool in tools.py: always returns a JSON string, never crashes."""
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "BAD_ARGUMENTS", "message": "Arguments were not valid JSON."})

    try:
        result = search_policies(**arguments)
    except TypeError as e:  # missing or unexpected argument
        return json.dumps({"error": "BAD_ARGUMENTS", "message": str(e)})

    return json.dumps(result)