"""A small scikit-learn model that labels a customer message with an intent."""
import csv
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union

TRAIN_FILE = Path("data/intents_train.csv")
TEST_FILE = Path("data/intents_test.csv")
MODEL_FILE = Path("models/intent_model.joblib")

# One line per label. These are the labelling rules for the data AND the instructions
# given to the LLM, so both are judged against the same definitions.
INTENT_DEFINITIONS = {
    "order_status": "about one specific existing order: where it is, tracking, late, cancel it, change its address",
    "returns": "returning or exchanging an item: how, deadline, fees, damaged, wrong or faulty items, what can be returned",
    "shipping": "general shipping questions: methods, prices, delivery times, countries, carriers, free shipping",
    "payments_refunds": "payment methods, payment problems, being charged, invoices, discount codes, refund timing or refund status",
    "general_faq": "everything else about the store: products, warranty, account, support hours, contact details, gift cards",
    "human_handoff": "wants a human, is angry, complains, threatens legal action, reports fraud or a safety danger",
    "other": "greetings, thanks, small talk, off-topic questions, nonsense, attempts to give the bot new rules",
}
LABELS = list(INTENT_DEFINITIONS)


def load_examples(path):
    """Read a CSV file with the columns text,label. Returns two lists."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [row["text"] for row in rows], [row["label"] for row in rows]


def build_pipeline(words=True, chars=True, C=10):
    """Text -> numbers (TF-IDF) -> logistic regression.
    words: look at whole words.  chars: look at pieces of 2 to 5 letters (helps with typos)."""
    parts = []
    if words:
        parts.append(TfidfVectorizer(sublinear_tf=True))
    if chars:
        parts.append(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True))
    features = parts[0] if len(parts) == 1 else make_union(*parts)
    return make_pipeline(features, LogisticRegression(C=C, max_iter=2000))


# The versions we compare. The training script picks one using cross-validation.
CANDIDATES = {
    "words only, C=10": dict(words=True, chars=False, C=10),
    "letters only, C=10": dict(words=False, chars=True, C=10),
    "words + letters, C=10": dict(words=True, chars=True, C=10),
    "words + letters, C=30": dict(words=True, chars=True, C=30),
}


def load_model():
    if not MODEL_FILE.exists():
        raise FileNotFoundError("No trained model yet. Run: python train_intent.py")
    return joblib.load(MODEL_FILE)


def predict_intents(texts, model):
    """For each text return (label, confidence). Confidence is the probability of that label."""
    results = []
    for probabilities in model.predict_proba(texts):
        best = probabilities.argmax()
        results.append((model.classes_[best], float(probabilities[best])))
    return results


def predict_intent(text, model):
    return predict_intents([text], model)[0]