from app.vectorstore import search

in_scope = [
    "How long do I have to return an item?",
    "Can I return earbuds I already opened?",
    "How much does express shipping to Canada cost?",
    "Do you deliver to Mexico?",
    "How do I start a return?",
    "When will I get my refund?",
    "Can I cancel my order?",
    "What payment methods do you accept?",
    "I forgot my password",
    "Is there a warranty on electronics?",
    "my parcel is lost, wheres my stuff",
    "Can I use two promo codes?",
]

near_miss = [  # shop-related, but our documents do not cover them
    "Do you offer price matching?",
    "Do you sell gift cards?",
    "How many loyalty points do I earn per dollar?",
    "Do you give bulk discounts for businesses?",
    "Can you recommend a good laptop?",
]

unrelated = [
    "What is the weather in Colombo today?",
    "How do I bake bread?",
    "Who won the last cricket world cup?",
    "Write me a poem about shoes",
]

def best_distance(question):
    return search(question, top_k=1)[0]["distance"]

def show(title, questions):
    print(f"\n{title}")
    distances = []
    for question in questions:
        distance = best_distance(question)
        distances.append(distance)
        print(f" {distance:.3f} | {question}")
    return distances

in_scores = show("IN SCOPE (documents answer these)", in_scope)
near_scores = show("NEAR MISS (related, but not in documents)", near_miss)
off_scores = show("UNRELATED", unrelated)

print(f"\nHighest in-scope distance: {max(in_scores):.3f}")
print(f"Lowest near-miss distance: {min(near_scores):.3f}")
print(f"Lowest unrelated distance: {min(off_scores):.3f}")
