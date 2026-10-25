import time
from openai import OpenAI
from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

def ask_llm(messages, temperature=0.2):
    start = time.time()

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=temperature,
    )

    seconds = round(time.time() - start, 2)
    usage = response.usage
    if usage:
        print(
            f"[LLM] {seconds}s | prompt tokens: {usage.prompt_tokens}"
            f"| answer tikens: {usage.completion_tokens}"
        )
    else:
        print(f"[LLM] {seconds}s")

    return response.choices[0].message.content