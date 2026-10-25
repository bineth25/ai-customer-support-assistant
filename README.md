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