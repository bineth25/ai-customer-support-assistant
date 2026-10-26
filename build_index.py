from app.vectorstore import build_index

count = build_index()
print(f"Indexed {count} chunks into the 'chroma_db' folder.")