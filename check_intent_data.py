"""Checks the intent data files: right labels, enough examples, no train/test overlap."""
import csv
import sys
from collections import Counter

from app.intent import LABELS, TEST_FILE, TRAIN_FILE

failures = []


def check(name, condition):
    print(f"{'PASS' if condition else 'FAIL'} | {name}")
    if not condition:
        failures.append(name)


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


train, test = read(TRAIN_FILE), read(TEST_FILE)

for name, rows in [("train", train), ("test", test)]:
    check(f"{name}: every row has text and a label", all(r["text"] and r["text"].strip() and r["label"] for r in rows))
    check(f"{name}: every label is one of the {len(LABELS)} known intents", all(r["label"] in LABELS for r in rows))
    texts = [r["text"].strip().lower() for r in rows]
    check(f"{name}: no message appears twice", len(texts) == len(set(texts)))

train_counts, test_counts = Counter(r["label"] for r in train), Counter(r["label"] for r in test)
check("train: at least 20 examples for every intent", all(train_counts[l] >= 20 for l in LABELS))
check("test: at least 6 examples for every intent", all(test_counts[l] >= 6 for l in LABELS))
check("train: no intent has more than twice as many examples as another",
      max(train_counts.values()) <= 2 * min(train_counts.values()))

train_texts = {r["text"].strip().lower() for r in train}
leaked = [r["text"] for r in test if r["text"].strip().lower() in train_texts]
check("no test message is also in the training data", leaked == [])

print("\nExamples per intent (train / test):")
for label in LABELS:
    print(f"  {label:18s} {train_counts[label]:3d} / {test_counts[label]:2d}")

print(f"\n{len(failures)} check(s) failed" if failures else "\nAll intent data checks passed.")
sys.exit(1 if failures else 0)