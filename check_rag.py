import sys
import time
from app.rag import answer_question

# (question, should it be answerable?, text the cited source must contain,
#  the answer must contain at least one of these words)
CASES = [
    ("How long do I have to return an item?", True, "Return window", ["21"]),
    ("Can I return earbuds I already opened?", True, "cannot be returned", None),
    ("How much does express shipping to Canada cost?", True, "Canada shipping", ["19.99"]),
    ("Do you deliver to Mexico?", True, "Where ShopLite ships", ["Canada"]),
    ("How much is the return label fee if I change my mind?", True, "Return shipping fee", ["4.99"]),
    ("How long do refunds take?", True, "Refund timing", ["5 to 7", "5-7"]),
    ("How long is the warranty on electronics?", True, "Warranty", ["12"]),
    ("What are the hours of human support?", True, "contact ShopLite support", ["9"]),
    ("Can I exchange an item for a different size?", True, "Exchanges", None),
    ("Do you offer price matching?", False, None, None),
    ("Do you sell gift cards?", False, None, None),
    ("How many loyalty points do I earn per dollar?", False, None, None),
    ("What is the capital of France?", False, None, None),
]

passed = 0
for question, should_be_found, source_part, any_of in CASES:
    result = answer_question(question)
    problems = []

    if result["found"] != should_be_found:
        problems.append(f"found={result['found']}, expected {should_be_found}")

    if should_be_found and result["found"]:
        if source_part and not any(source_part in s for s in result["sources"]):
            problems.append(f"no cited source contains '{source_part}': {result['sources']}")
        if any_of and not any(w.lower() in result["answer"].lower() for w in any_of):
            problems.append(f"answer should mention one of {any_of}")

    if problems:
        print(f"FAIL | {question}")
        for problem in problems:
            print(f"       - {problem}")
        print(f"       answer: {result['answer']}")
    else:
        print(f"PASS | {question}")
        passed += 1

    time.sleep(3)  # be gentle with free-tier rate limits

print(f"\n{passed} of {len(CASES)} checks passed")
sys.exit(0 if passed == len(CASES) else 1)