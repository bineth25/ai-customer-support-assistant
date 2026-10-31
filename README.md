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

## Intent classifier vs LLM

**Question:** can a small classic ML model replace the LLM for working out what a customer message is about?

**Setup:** 7 intents (order status, returns, shipping, payments/refunds, general FAQ, human handoff, other). 168 labelled training messages and 56 held-out test messages that the model never learns from. The classifier is TF-IDF (words + letter pieces) with logistic regression; settings were chosen by cross-validation on the training data only. The LLM got the same label definitions and the same 56 messages.

| | Classifier | LLM |
|---|---|---|
| Accuracy on the test set | 0.804 (45/56) | 0.982 (55/56) |
| Macro F1 | 0.801 | 0.982 |
| Time per message | 0.37 ms | 1.73 s |
| Tokens per message | 0 | 235 |

**Hybrid router** (use the classifier when its confidence is at least the threshold, otherwise ask the LLM):

| Threshold | Accuracy | Messages sent to the LLM |
|---|---|---|
| 0.0 (classifier only) | 0.804 | 0 of 56 |
| 0.5 | 0.946 | 16 of 56 |
| 0.7 | 0.964 | 23 of 56 |
| 0.9 | 0.982 | 47 of 56 |

**What I learned**
- The LLM understands wording it has never seen. 11 of the classifier's mistakes were things like "Germany", "SwiftPost", "locker" or "Google Pay", which are missing from 168 training messages.
- The classifier knows when it is unsure: 8 of its 11 mistakes had confidence below 0.5. That is what makes a confidence threshold useful.
- The learning curve was still rising at 100% of the training data, so more labelled messages would help (high variance, not high bias).
- Some labels are debatable ("VAT included?", "gift card"), so a few points of difference are label noise.

**Decision**
- The LLM stays the brain of the assistant. It is clearly more accurate (98% vs 80%).
- The classifier is not in the request path. The agent already picks its tools inside the same LLM call, so a separate intent step would add work instead of saving it.
- Where the classifier does earn a place: a free intent label per message for monitoring (Part 12), a fallback when the LLM is rate-limited or down (the free tier allows only 15 requests per minute), and a hybrid router if traffic grows (threshold 0.7 keeps 96% accuracy with 41% of the LLM calls).

**Limits:** only 56 test messages (one message = 1.8 points), and I wrote both the data and the labels. Real conversation logs would be a better test.

## Web API (Part 9)

```
uvicorn app.api:app --reload      # then open http://127.0.0.1:8000/docs
```

| Endpoint | What it does |
|---|---|
| `POST /chat` | `{"message": "...", "session_id": "..."}`. Leave `session_id` out to start a conversation. Returns the answer, sources, `found`, `handoff` and `ticket_id` |
| `DELETE /sessions/{id}` | Ends a conversation |
| `GET /health` | `ok` (200) when the knowledge base is loaded, otherwise `degraded` (503) |

Status codes: 401 wrong or missing API key, 404 unknown or expired session, 422 invalid input, 429 too many requests (with `Retry-After`), 503 the LLM provider is unreachable.

Settings in `.env` (all optional): `API_KEY` (clients must send `X-API-Key`), `RATE_LIMIT_PER_MINUTE` (default 20 per address).

Design choices
- One `Assistant` per session, kept in memory for 30 minutes of inactivity (max 500 sessions). One message at a time per conversation (lock), several conversations in parallel.
- Endpoints are plain `def`, so FastAPI runs the blocking LLM calls in worker threads and the server stays responsive.
- Ticket numbers are protected by a lock, tested with 60 parallel saves.

Known limits: sessions and rate-limit counters live in one process's memory, so they are lost on restart and not shared between several server copies. Behind a proxy the rate limiter would see the proxy's address (fix: use the forwarded address, planned for deployment).

Tests: `python check_api.py` (45 offline checks).