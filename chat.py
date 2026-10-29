from app.assistant import Assistant

assistant = Assistant()
print("ShopLite support assistant.")
print("Type 'new' to start a new conversation, 'quit' to exit.")

while True:
    try:
        message = input("\nYou: ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not message:
        continue
    if message.lower() in ("quit", "exit"):
        break
    if message.lower() == "new":
        assistant.reset()
        print("(new conversation)")
        continue

    result = assistant.reply(message)
    print(f"\nAssistant: {result['answer']}")
    if result.get("handoff"):
        print("(This conversation was passed to a human agent. Type 'new' to start again.)")