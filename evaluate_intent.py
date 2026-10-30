"""Scores the saved model on the TEST file. Run it rarely: every look at the test set
makes it a little less honest."""
import sys

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from app.intent import LABELS, TEST_FILE, load_examples, load_model, predict_intents

MIN_TEST_ACCURACY = 0.70  # below this the script exits with an error (useful for CI later)

texts, true_labels = load_examples(TEST_FILE)
model = load_model()
predictions = predict_intents(texts, model)
predicted_labels = [label for label, _ in predictions]

accuracy = accuracy_score(true_labels, predicted_labels)
print(f"Test accuracy: {accuracy:.3f} ({sum(t == p for t, p in zip(true_labels, predicted_labels))} of {len(texts)})\n")
print(classification_report(true_labels, predicted_labels, labels=LABELS, zero_division=0))

print("Confusion matrix (rows = true intent, columns = what the model said):")
matrix = confusion_matrix(true_labels, predicted_labels, labels=LABELS)
print(" " * 20 + "".join(f"{i + 1:>4d}" for i in range(len(LABELS))))
for i, label in enumerate(LABELS):
    print(f"{i + 1}. {label:17s}" + "".join(f"{count:4d}" for count in matrix[i]))

mistakes = [(t, y, p, c) for t, y, (p, c) in zip(texts, true_labels, predictions) if y != p]
print(f"\nMistakes ({len(mistakes)}):")
for text, true, predicted, confidence in mistakes:
    print(f"  '{text}'\n      true: {true} | model: {predicted} ({confidence:.2f})")

ok = accuracy >= MIN_TEST_ACCURACY
print(f"\n{'PASS' if ok else 'FAIL'} | test accuracy {accuracy:.3f} (minimum {MIN_TEST_ACCURACY})")
sys.exit(0 if ok else 1)