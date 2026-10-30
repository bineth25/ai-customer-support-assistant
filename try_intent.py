"""Type a customer message, see which intent the model picks and how sure it is."""
from app.intent import load_model

model = load_model()
print("Type a message (or 'quit'):")
while True:
    text = input("> ").strip()
    if text.lower() in {"quit", "exit", ""}:
        break
    probabilities = model.predict_proba([text])[0]
    ranked = sorted(zip(model.classes_, probabilities), key=lambda pair: -pair[1])
    for label, probability in ranked[:3]:
        print(f"   {label:18s} {probability:.2f}")