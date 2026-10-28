import sys
import time
from app.order_agent import answer_with_tools

questions = [
    "Where is my order SL-1003? My email is noah.patel@example.com",
    "Can I still return order SL-1001? My email is emma.carter@example.com",
    "I want to return order SL-1002. My email is liam.brooks@example.com",
    "Where is my order SL-1003?",
    "Show me order SL-1001. My email is hacker@example.com",
    "Order SL-1008 has not arrived and it is very late. Please report it. My email is ava.thompson@example.com",
]

# If you type a question after the command, use that one instead
if len(sys.argv) > 1:
    questions = [" ".join(sys.argv[1:])]

for question in questions:
    print(f"\nQ: {question}")
    result = answer_with_tools(question)
    print(f"A: {result['answer']}")
    time.sleep(2)  # be gentle with free-tier rate limits