from app.llm import ask_llm

messages = [
    {
        "role": "system",
        "content": "You are a friendly customer support assistant for an online store called ShopLite. Keep answers short.",
    },
    {"role": "user", "content": "How do I return a product?"},
]

print(ask_llm(messages))