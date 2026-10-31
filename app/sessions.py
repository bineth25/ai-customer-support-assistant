"""Keeps one Assistant (one conversation) per session id, in memory."""
import threading
import time
import uuid

from app.assistant import Assistant

SESSION_TTL_SECONDS = 30 * 60  # a conversation nobody touches for 30 minutes is forgotten
MAX_SESSIONS = 500             # the most conversations kept at once


class Session:
    def __init__(self, now):
        self.assistant = Assistant()
        self.lock = threading.Lock()  # one message at a time per conversation
        self.last_used = now


class SessionStore:
    def __init__(self, ttl=SESSION_TTL_SECONDS, max_sessions=MAX_SESSIONS, clock=time.time):
        self.ttl = ttl
        self.max_sessions = max_sessions
        self.clock = clock  # can be replaced in tests
        self.sessions = {}
        self.lock = threading.Lock()  # protects the dictionary itself

    def purge(self):
        """Forget conversations that have been idle too long. Called with self.lock held."""
        now = self.clock()
        for session_id in [i for i, s in self.sessions.items() if now - s.last_used > self.ttl]:
            del self.sessions[session_id]

    def create(self):
        """Start a new conversation. Returns (session_id, session)."""
        with self.lock:
            self.purge()
            if len(self.sessions) >= self.max_sessions:
                # Make room by dropping the conversation that was used longest ago
                oldest = min(self.sessions, key=lambda i: self.sessions[i].last_used)
                del self.sessions[oldest]
            session_id = uuid.uuid4().hex
            self.sessions[session_id] = Session(self.clock())
            return session_id, self.sessions[session_id]

    def get(self, session_id):
        """Return the session, or None if it never existed or has expired."""
        with self.lock:
            self.purge()
            session = self.sessions.get(session_id)
            if session:
                session.last_used = self.clock()
            return session

    def delete(self, session_id):
        """Remove a session. Returns True if it existed."""
        with self.lock:
            return self.sessions.pop(session_id, None) is not None

    def __len__(self):
        return len(self.sessions)