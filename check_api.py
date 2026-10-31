"""Tests the web service without a real LLM: instant, free, always the same."""
import json
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import tools
import app.api as api
import app.assistant as assistant_module
from app.llm import LLMUnavailable
from app.prompts import TECH_PROBLEM_MESSAGE
from app.ratelimit import RateLimiter
from app.sessions import SessionStore

tools.TICKETS_FILE = Path(tempfile.mkdtemp()) / "tickets.json"
os.environ.pop("API_KEY", None)

failures = []
llm_calls = []


def check(name, condition):
    print(f"{'PASS' if condition else 'FAIL'} | {name}")
    if not condition:
        failures.append(name)


def fake_llm(text="Hello! How can I help?"):
    """Replace the real LLM with one that always answers the same."""
    def fake(messages, tool_list, temperature=0.2):
        llm_calls.append(json.loads(json.dumps(messages)))
        return SimpleNamespace(content=text, tool_calls=None)
    assistant_module.ask_llm_with_tools = fake


def fresh_service(limit=1000):
    api.store = SessionStore()
    api.limiter = RateLimiter(limit=limit)
    return TestClient(api.app)


# --- 1. Health ---
print("\n1. Health")
client = fresh_service()
r = client.get("/health")
check("/health answers", r.status_code in (200, 503) and "status" in r.json())
check("/health reports the number of open conversations", r.json()["active_sessions"] == 0)

# --- 2. Chat and sessions ---
print("\n2. Chat and sessions")
fake_llm()
llm_calls.clear()
r = client.post("/chat", json={"message": "Hi"})
body = r.json()
check("a first message starts a conversation", r.status_code == 200 and len(body["session_id"]) == 32)
check("the answer has the expected fields",
      set(body) == {"session_id", "answer", "sources", "found", "handoff", "ticket_id"} and body["answer"] == "Hello! How can I help?")
sid = body["session_id"]

r = client.post("/chat", json={"message": "And a second question", "session_id": sid})
check("a second message in the same session works", r.status_code == 200 and r.json()["session_id"] == sid)
sent = json.dumps(llm_calls[-1])
check("the assistant remembers the first message (memory per session)", '"Hi"' in sent)

r2 = client.post("/chat", json={"message": "I am someone else"})
other = r2.json()["session_id"]
check("a new conversation gets a different id", other != sid)
check("conversations do not share memory", "second question" not in json.dumps(llm_calls[-1]) and "Hi" not in json.dumps(llm_calls[-1][1:-1]))

r = client.post("/chat", json={"message": "Hello", "session_id": "does-not-exist"})
check("an unknown session id gets 404", r.status_code == 404)

r = client.delete(f"/sessions/{sid}")
check("DELETE ends a session", r.status_code == 204)
check("a deleted session is gone", client.post("/chat", json={"message": "x", "session_id": sid}).status_code == 404)
check("deleting twice gives 404", client.delete(f"/sessions/{sid}").status_code == 404)

# --- 3. Bad input ---
print("\n3. Bad input")
check("missing message -> 422", client.post("/chat", json={}).status_code == 422)
check("empty message -> 422", client.post("/chat", json={"message": ""}).status_code == 422)
check("blank message -> 422", client.post("/chat", json={"message": "    "}).status_code == 422)
check("huge message -> 422", client.post("/chat", json={"message": "a" * 4001}).status_code == 422)
check("message that is not text -> 422", client.post("/chat", json={"message": 123}).status_code == 422)
check("body that is not JSON -> 422", client.post("/chat", content="hello").status_code == 422)

# --- 4. Handover and errors ---
print("\n4. Handover and errors")
r = client.post("/chat", json={"message": "I want to talk to a human"})
check("a handover is a normal answer with handoff=true and a ticket id",
      r.status_code == 200 and r.json()["handoff"] is True and r.json()["ticket_id"] == "TK-0001")


def unavailable(messages, tool_list, temperature=0.2):
    raise LLMUnavailable("down")


assistant_module.ask_llm_with_tools = unavailable
before = len(api.store)
r = client.post("/chat", json={"message": "Where is my order?"})
check("LLM down -> 503 with the friendly message", r.status_code == 503 and r.json()["detail"] == TECH_PROBLEM_MESSAGE)
check("a failed first message does not leave a session behind", len(api.store) == before)
fake_llm()

# --- 5. API key ---
print("\n5. API key")
os.environ["API_KEY"] = "secret-123"
check("no key -> 401", client.post("/chat", json={"message": "Hi"}).status_code == 401)
check("wrong key -> 401", client.post("/chat", json={"message": "Hi"}, headers={"X-API-Key": "nope"}).status_code == 401)
check("non-ASCII key does not crash -> 401", client.post("/chat", json={"message": "Hi"}, headers={"X-API-Key": b"\xe9"}).status_code == 401)
check("right key -> 200", client.post("/chat", json={"message": "Hi"}, headers={"X-API-Key": "secret-123"}).status_code == 200)
check("/health needs no key", client.get("/health").status_code in (200, 503))
del os.environ["API_KEY"]
check("without API_KEY set, no key is needed", client.post("/chat", json={"message": "Hi"}).status_code == 200)

# --- 6. Rate limit ---
print("\n6. Rate limit")
client = fresh_service(limit=3)
codes = [client.post("/chat", json={"message": "Hi"}).status_code for _ in range(5)]
check("requests over the limit get 429", codes == [200, 200, 200, 429, 429])
r = client.post("/chat", json={"message": "Hi"})
check("429 tells the client when to retry", int(r.headers["Retry-After"]) >= 1)
check("/health is not rate limited", client.get("/health").status_code in (200, 503))

now = [1000.0]
limiter = RateLimiter(limit=2, clock=lambda: now[0])
check("limiter: first two allowed", limiter.check("a")[0] and limiter.check("a")[0])
check("limiter: third refused", limiter.check("a")[0] is False)
check("limiter: another client is not affected", limiter.check("b")[0] is True)
now[0] += 61
check("limiter: allowed again after the window", limiter.check("a")[0] is True)

# --- 7. Session store ---
print("\n7. Session store")
now = [0.0]
store = SessionStore(ttl=100, max_sessions=3, clock=lambda: now[0])
a, _ = store.create(); now[0] += 10
b, _ = store.create(); now[0] += 10
check("sessions can be found", store.get(a) is not None and store.get(b) is not None)
now[0] += 95  # a was last used at 20 (get above), b at 20 -> both expire at 120
now[0] += 10
check("idle sessions expire", store.get(a) is None and store.get(b) is None)
now[0] = 0
ids = []
for _ in range(4):
    now[0] += 1
    ids.append(store.create()[0])
check("at most max_sessions are kept", len(store) == 3)
check("the one used longest ago was dropped", store.get(ids[0]) is None and store.get(ids[3]) is not None)

# --- 8. Many things at once ---
print("\n8. Concurrency")
fake_llm()
client = fresh_service()
sid = client.post("/chat", json={"message": "start"}).json()["session_id"]


running = {"now": 0, "most": 0}
running_lock = threading.Lock()


def slow_llm(messages, tool_list, temperature=0.2):
    """Takes a moment, and notes how many calls run at the same time."""
    with running_lock:
        running["now"] += 1
        running["most"] = max(running["most"], running["now"])
    time.sleep(0.01)
    with running_lock:
        running["now"] -= 1
    return SimpleNamespace(content="ok", tool_calls=None)


assistant_module.ask_llm_with_tools = slow_llm


def send(i):
    return client.post("/chat", json={"message": f"message {i}", "session_id": sid}).status_code


with ThreadPoolExecutor(max_workers=8) as pool:
    codes = list(pool.map(send, range(40)))
history = api.store.get(sid).assistant.history
check("40 parallel messages in one session all succeed", codes == [200] * 40)
check("none of them was lost or mixed up in the history", len(history) == 2 * 41)
check("messages of one conversation are handled one at a time", running["most"] == 1)
fake_llm()

tools.TICKETS_FILE = Path(tempfile.mkdtemp()) / "tickets.json"


def slow_loads(text):
    """Reading the ticket file takes a moment, so that an unprotected race shows up."""
    time.sleep(0.002)
    return json.loads(text)


real_json = tools.json
tools.json = SimpleNamespace(loads=slow_loads, dumps=json.dumps)
try:
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda i: tools.save_ticket("other", f"t{i}")["ticket_id"], range(60)))
finally:
    tools.json = real_json
check("60 tickets saved at the same moment all get different numbers", len(set(ids)) == 60)
saved = json.loads(tools.TICKETS_FILE.read_text(encoding="utf-8"))
check("and all 60 are in the file", len(saved) == 60)

# --- 9. Extras ---
print("\n9. Extras")
r = client.get("/health")
check("every response carries its processing time", "x-process-time-ms" in r.headers)
check("the interactive docs page exists", client.get("/docs").status_code == 200)

print(f"\n{len(failures)} check(s) failed" if failures else "\nAll API checks passed.")
sys.exit(1 if failures else 0)