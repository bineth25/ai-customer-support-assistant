"""The assistant as a web service.  Run it with:  uvicorn app.api:app --reload
Then open http://127.0.0.1:8000/docs to try it in the browser."""
import logging
import os
import secrets
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from app.prompts import TECH_PROBLEM_MESSAGE
from app.ratelimit import RateLimiter
from app.sessions import SessionStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("shoplite.api")

app = FastAPI(title="ShopLite Support Assistant", version="1.0")

store = SessionStore()  # all conversations that are open right now
limiter = RateLimiter(limit=int(os.getenv("RATE_LIMIT_PER_MINUTE", "20")))


# ---------- what goes in and out ----------

class ChatRequest(BaseModel):
    message: str = Field(max_length=4000)
    session_id: str | None = None  # leave out to start a new conversation

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[str]
    found: bool
    handoff: bool
    ticket_id: str | None = None


# ---------- protection: API key and rate limit ----------

def check_api_key(x_api_key: str | None = Header(default=None)):
    """If API_KEY is set in .env, every request must send it in the X-API-Key header."""
    expected = os.getenv("API_KEY")
    if expected and not (x_api_key and secrets.compare_digest(x_api_key.encode(), expected.encode())):
        raise HTTPException(status_code=401, detail="Missing or wrong API key.")


def check_rate_limit(request: Request):
    """At most RATE_LIMIT_PER_MINUTE requests per minute from one address."""
    client = request.client.host if request.client else "unknown"
    allowed, wait = limiter.check(client)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down.",
            headers={"Retry-After": str(wait)},
        )


protected = [Depends(check_api_key), Depends(check_rate_limit)]


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    milliseconds = (time.time() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{milliseconds:.0f}"
    logger.info("%s %s -> %s in %.0f ms", request.method, request.url.path, response.status_code, milliseconds)
    return response


# ---------- endpoints ----------
# These are plain "def" functions on purpose. The assistant waits for the LLM (a blocking
# call), and FastAPI runs "def" endpoints in worker threads, so one slow answer does not
# freeze the whole server. With "async def" it would.

@app.get("/health")
def health():
    """Is the service up and is the knowledge base loaded?"""
    chunks = None
    try:
        from app.vectorstore import get_collection
        chunks = get_collection().count()
    except Exception:  # a health check must never crash
        logger.exception("health check could not read the knowledge base")
    body = {"status": "ok" if chunks else "degraded", "knowledge_base_chunks": chunks,
            "active_sessions": len(store)}
    return JSONResponse(body, status_code=200 if chunks else 503)


@app.post("/chat", response_model=ChatResponse, dependencies=protected)
def chat(body: ChatRequest):
    """Send one customer message. Leave session_id out to start a new conversation."""
    is_new = body.session_id is None
    if is_new:
        session_id, session = store.create()
    else:
        session_id, session = body.session_id, store.get(body.session_id)
        if session is None:
            raise HTTPException(
                status_code=404,
                detail="Unknown or expired session. Start a new conversation by leaving session_id out.",
            )

    with session.lock:  # one message at a time inside one conversation
        result = session.assistant.reply(body.message)

    if result.get("error"):  # the LLM provider could not be reached
        if is_new:
            store.delete(session_id)
        raise HTTPException(status_code=503, detail=TECH_PROBLEM_MESSAGE)

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        sources=result["sources"],
        found=result["found"],
        handoff=result["handoff"],
        ticket_id=result.get("ticket_id"),
    )


@app.delete("/sessions/{session_id}", status_code=204, dependencies=protected)
def end_session(session_id: str):
    """Forget a conversation (the 'new chat' button)."""
    if not store.delete(session_id):
        raise HTTPException(status_code=404, detail="Unknown or expired session.")
    return Response(status_code=204)