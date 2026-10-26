from app.chunking import load_all_chunks

chunks = load_all_chunks()
print(f"Total chunks: {len(chunks)}")

word_counts = [len(chunk["text"].split()) for chunk in chunks]
print(f"Words per chunk: shortest {min(word_counts)}, longest {max(word_counts)}")

print("\n--- First chunk ---")
print(chunks[0]["text"])

print("\n--- A chunk with a list ---")
for chunk in chunks:
    if chunk["section"] == "Items that cannot be returned":
        print(chunk["text"])
        print(f"(id: {chunk['id']}, source: {chunk['source']})")
