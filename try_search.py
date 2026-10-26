import sys
from app.vectorstore import search

questions = [
    "How long do I have to send something back?",
    "Can I get my money back for earbuds I already opened?",
    "Do you deliver to Mexico?",
    "My package never showed up",
    "Do you offer price matching?",
]

# If you type a question after the command, use that one instead
if len(sys.argv) > 1:
    questions = [" ".join(sys.argv[1:])]

for question in questions:
    print(f"\nQ: {question}")
    for hit in search(question, top_k=3):
        print(f"  {hit['distance']:.3f} | {hit['source']} > {hit['section']}")