"""How much can we trust the classifier when it is confident? Uses only the TRAINING data.
Every prediction here comes from a model that did not see that message (cross-validation),
so this is the honest way to pick a confidence threshold without touching the test set."""
import numpy as np
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from app.intent import CANDIDATES, TRAIN_FILE, build_pipeline, load_examples

texts, labels = load_examples(TRAIN_FILE)
labels = np.array(labels)
model = build_pipeline(**CANDIDATES["words + letters, C=30"])

probabilities = cross_val_predict(
    model, texts, labels, cv=StratifiedKFold(5, shuffle=True, random_state=42), method="predict_proba"
)
classes = np.array(sorted(set(labels)))
predicted = classes[probabilities.argmax(axis=1)]
confidence = probabilities.max(axis=1)

print(f"{'threshold':>10s} {'classifier handles':>20s} {'accuracy on those':>20s}")
for threshold in [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
    handled = confidence >= threshold
    if handled.sum() == 0:
        continue
    accuracy = (predicted[handled] == labels[handled]).mean()
    print(f"{threshold:10.1f} {handled.mean():20.0%} {accuracy:20.3f}")
print("\nPick the lowest threshold where 'accuracy on those' is high enough for you.")