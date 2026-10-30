"""Trains the intent classifier. Picks the best version with cross-validation (training data only)."""
import joblib
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score

from app.intent import CANDIDATES, MODEL_FILE, TRAIN_FILE, build_pipeline, load_examples

texts, labels = load_examples(TRAIN_FILE)
print(f"{len(texts)} training messages\n")

# 5-fold cross-validation, repeated 3 times: train on 4/5 of the data, test on the other 1/5,
# 15 times in total, each time with different pieces. The test file is NOT used here.
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=42)

baseline = cross_val_score(DummyClassifier(strategy="most_frequent"), texts, labels, cv=cv)
print(f"{'version':26s} {'cross-validation accuracy':>26s}")
print(f"{'always guess one intent':26s} {baseline.mean():18.3f}")

results = {}
for name, settings in CANDIDATES.items():
    scores = cross_val_score(build_pipeline(**settings), texts, labels, cv=cv)
    results[name] = scores.mean()
    print(f"{name:26s} {scores.mean():10.3f} (+/- {scores.std():.3f})")

best_name = max(results, key=results.get)
print(f"\nBest version: {best_name}")

# Train the winner on ALL training data and save it
model = build_pipeline(**CANDIDATES[best_name])
model.fit(texts, labels)
train_accuracy = accuracy_score(labels, model.predict(texts))
print(f"Accuracy on the data it learned from: {train_accuracy:.3f}")
print(f"Accuracy on data it has not seen (cross-validation): {results[best_name]:.3f}")
print("A big gap between these two numbers means the model memorises instead of learning.")

MODEL_FILE.parent.mkdir(exist_ok=True)
joblib.dump(model, MODEL_FILE)
print(f"\nSaved to {MODEL_FILE}")