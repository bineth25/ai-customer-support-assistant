# AI Customer Support Assistant

An AI assistant for a fictional online store (ShopLite). It answers policy
questions from documents, looks up orders, creates support tickets and
hands over to a human when needed.

**Status:** work in progress (Project 1)

## Setup

1. Clone the repo
2. Create and activate a virtual environment: `python -m venv .venv`
3. Install packages: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and add your API key and model name
5. Test it: `python try_llm.py`

## Data

The assistant works with fictional ShopLite data in the `data/` folder:

- `data/docs/`: returns policy, shipping policy, payments and refunds, and FAQ (Markdown)
- `data/orders.json`: 11 fake orders covering different situations (late package, expired return window, warranty and so on)

Check that the data is consistent: `python check_data.py`

## Search (RAG retrieval)

Documents are cut into chunks (one per `##` section), embedded, and stored in a local Chroma database. A question is embedded the same way and the closest chunks are returned.

1. Build the index: `python build_index.py`
2. Try a search: `python try_search.py "How long do I have to return an item?"`

## Ask questions (RAG)

Answers come only from the documents, with the source section named. If the documents do not cover a question, the assistant says so instead of guessing.

- Ask one question: `python try_rag.py "How long do I have to return an item?"`
- Run the automatic checks: `python check_rag.py`