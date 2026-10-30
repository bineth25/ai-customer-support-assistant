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

## Tools (order lookup and tickets)

The assistant can call two tools. The model decides when, the code runs them:

- `lookup_order`: needs the order number **and** the customer's email. Return deadlines, warranty and delays are computed in code, not by the model.
- `create_ticket`: saves a support ticket for a human (to `data/tickets.json`, not committed).

- Test the tools without an LLM: `python check_tools.py`
- Ask a question: `python try_tools.py "Where is my order SL-1003? My email is noah.patel@example.com"`
- Run the tool-calling checks: `python check_tool_agent.py`

## Chat assistant (documents, tools and memory)

One assistant answers from the policy documents, looks up orders and creates tickets. It remembers the conversation (the last 12 messages) and decides by itself which tool a question needs.

- Talk to it: `python chat.py`
- Run the multi-turn checks: `python check_conversations.py`

## Human handover

The assistant hands the conversation to a human agent when:
- the customer asks for one, or mentions legal action, fraud or a safety problem (rules in code, no LLM call)
- the customer is clearly angry (the model flags it)
- three messages in a row could not be answered

The agent gets a ticket with the conversation transcript. After a handover the bot stops answering.

- Test the handover rules (no API needed): `python check_handoff.py`

## Security: prompt injection and abuse

The assistant reads text it does not control (customer messages, order notes, policy text), so it is attacked on purpose and defended in layers. Rules that matter live in code, because a model can be talked out of a prompt rule.

| Attack | Defence |
|---|---|
| "Ignore your rules", fake system tags, role-play | Prompt rules 11, 13, 14 (model) |
| Extract the system prompt | Secret code in the prompt plus a copied-rules check on every answer (code) |
| Invented refunds ("$500 approved") | Every dollar amount in an answer must exist in this turn's data (code) |
| Other customers' orders | Order number and email must be typed by the customer in this conversation (code) |
| Guessing emails | 3 failed lookups hand the conversation to a human; the typed email is not saved as a contact (code) |
| Ticket spam | Max 2 tickets per conversation, only for orders looked up first (code) |
| Hostile text in order notes (indirect injection) | Notes that look like instructions are hidden before the model sees them (code) |
| Huge messages | Over 1,000 characters is not read (code) |

Tests: `python check_injection.py` (offline, 55 checks) and `python check_attacks.py` (13 attacks on the real model).

Known limits: the counters are per conversation, so an attacker can start a new one (rate limiting belongs in the API, Part 9). Phrase lists and the copied-rules check catch obvious attacks, not every paraphrase.