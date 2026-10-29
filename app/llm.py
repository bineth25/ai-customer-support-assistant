import time
from openai import OpenAI, OpenAIError, Timeout
from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# Wait up to 15 s to connect and 60 s for the answer. The library's default of 5 s to
# connect is too short on a slow connection. It also retries twice by itself.
client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    timeout=Timeout(60.0, connect=15.0),
)


class LLMUnavailable(Exception):
    """The model provider could not be reached, or kept returning errors."""


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


def call_llm(**kwargs):
    """Call the API. Every library error (timeout, rate limit, server error, ...)
    becomes one clear exception, and the real error is printed for you to read."""
    start = time.time()
    try:
        response = client.chat.completions.create(model=LLM_MODEL, **kwargs)
    except OpenAIError as e:
        print(f"[LLM ERROR] {type(e).__name__}: {e}")
        raise LLMUnavailable(str(e)) from e
    log_call(start, response)
    return response


def ask_llm(messages, temperature=0.2):
    """Send a list of messages to the LLM and return its text answer."""
    response = call_llm(messages=messages, temperature=temperature)
    return response.choices[0].message.content


def ask_llm_with_tools(messages, tools, temperature=0.2):
    """Like ask_llm, but the model may ask to call a tool.
    Returns the whole message: it has .content (text) and .tool_calls (requests)."""
    response = call_llm(messages=messages, tools=tools, temperature=temperature)
    return response.choices[0].message