"""Does more training data help? Trains on 20%, 40% ... 100% of the training file."""
from sklearn.model_selection import StratifiedKFold, learning_curve

from app.intent import CANDIDATES, TRAIN_FILE, build_pipeline, load_examples

texts, labels = load_examples(TRAIN_FILE)
settings = CANDIDATES["words + letters, C=30"]

sizes, train_scores, validation_scores = learning_curve(
    build_pipeline(**settings), texts, labels,
    train_sizes=[0.2, 0.4, 0.6, 0.8, 1.0],
    cv=StratifiedKFold(5, shuffle=True, random_state=42),
    shuffle=True, random_state=42,
)

print(f"{'training messages':>18s} {'accuracy on them':>18s} {'accuracy on new messages':>26s}")
for n, train, validation in zip(sizes, train_scores.mean(axis=1), validation_scores.mean(axis=1)):
    print(f"{n:18d} {train:18.3f} {validation:26.3f}")
print("\nIf the last number is still rising at 100%, more labelled messages would help.")