import time
from openai import OpenAI
from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# The client is the connection to the model provider
client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def log_call(start, response):
    """Print how long the call took and how many tokens it used."""
    seconds = round(time.time() - start, 2)
    usage = response.usage
    if usage:
        print(
            f"[LLM] {seconds}s | prompt tokens: {usage.prompt_tokens} "
            f"| answer tokens: {usage.completion_tokens}"
        )
    else:
        print(f"[LLM] {seconds}s")


def ask_llm(messages, temperature=0.2):
    """Send a list of messages to the LLM and return its text answer."""
    start = time.time()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=temperature,
    )
    log_call(start, response)
    return response.choices[0].message.content


def ask_llm_with_tools(messages, tools, temperature=0.2):
    """Like ask_llm, but the model may ask to call a tool.
    Returns the whole message: it has .content (text) and .tool_calls (requests)."""
    start = time.time()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        tools=tools,
        temperature=temperature,
    )
    log_call(start, response)
    return response.choices[0].message