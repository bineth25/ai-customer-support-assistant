import chromadb
from app.chunking import load_all_chunks

DB_PATH = "chroma_db"
COLLECTION_NAME = "shoplite_docs"

def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(name=COLLECTION_NAME)

def build_index():
    client = chromadb.PersistentClient(path=DB_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(name=COLLECTION_NAME)

    chunks = load_all_chunks()
    collection.add(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[
            {"source": chunk["source"], "section": chunk["section"]}
            for chunk in chunks
        ],
    )
    return len(chunks)

def search(question, top_k=3):
    collection = get_collection()
    results = collection.query(query_texts=[question], n_results=top_k)

    hits =[]

    for i in range(len(results["ids"][0])):
        hits.append(
            {
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "section": results["metadatas"][0][i]["section"],
                "distance": results["distances"][0][i],
            }
        )
    return hits