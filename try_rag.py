import sys
import time
from app.rag import answer_question

questions = [
    "How long do I have to return an item?",
    "I opened my earbuds, can I still return them?",
    "How much does express shipping to Canada cost?",
    "Do you deliver to Mexico?",
    "Do you offer price matching?",
    "What is the capital of France?",
]

# If you type a question after the command, use that one instead
if len(sys.argv) > 1:
    questions = [" ".join(sys.argv[1:])]

for question in questions:
    result = answer_question(question)
    print(f"\nQ: {question}")
    print(f"A: {result['answer']}")
    if result["sources"]:
        print("Sources: " + "; ".join(result["sources"]))
    time.sleep(2)  # be gentle with free-tier rate limits