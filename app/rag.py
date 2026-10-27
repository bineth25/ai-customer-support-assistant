import re
from app.llm import ask_llm
from app.prompts import SYSTEM_PROMPT, NOT_FOUND_MESSAGE
from app.vectorstore import search

MAX_DISTANCE = 1.5
TOP_K = 3

def build_context(hits):
    """Turn the retrieved chunks into a numbered block of text for the prompt."""
    parts = []
    for number, hit in enumerate(hits, start=1):
        parts.append(f"[{number}] ({hit['source']} > {hit['section']})\n{hit['text']}")
    return "\n\n".join(parts)

def not_found():
    return {"answer": NOT_FOUND_MESSAGE, "sources": [], "found": False}

def answer_question(question):
    """Answer a question from the documents. Returns answer, sources and found."""
    # Layer 1: keep only chunks that are close enough to the question
    hits = [h for h in search(question, top_k=TOP_K) if h["distance"] <= MAX_DISTANCE]
    if not hits:
        return not_found()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=build_context(hits))},
        {"role": "user", "content": question},
    ]

    reply = (ask_llm(messages) or "").strip()

    # Layer 2: the model says the context does not contain the answer
    if not reply or "NOT_FOUND" in reply:
        return not_found()

    # Turn the [1] [2] markers into real source names
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", reply)})
    sources = [
        f"{hits[n - 1]['source']} > {hits[n-1]['section']}"
        for n in cited
        if 1<= n <= len(hits)
    ]

    return {"answer": reply, "sources": sources, "found": True}