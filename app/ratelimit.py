"""A simple "at most N requests per minute per client" limiter, kept in memory."""
import threading
import time


class RateLimiter:
    def __init__(self, limit, window=60, clock=time.time):
        self.limit = limit
        self.window = window  # seconds
        self.clock = clock    # can be replaced in tests
        self.requests = {}    # client -> times of its recent requests
        self.lock = threading.Lock()

    def check(self, client):
        """Count this request. Returns (allowed, seconds_to_wait)."""
        now = self.clock()
        with self.lock:
            recent = [t for t in self.requests.get(client, []) if now - t < self.window]
            if len(recent) >= self.limit:
                self.requests[client] = recent
                return False, max(1, int(self.window - (now - recent[0])) + 1)
            recent.append(now)
            self.requests[client] = recent
            # Forget clients that have gone quiet, so the dictionary cannot grow forever
            if len(self.requests) > 10000:
                self.requests = {c: r for c, r in self.requests.items() if r and now - r[-1] < self.window}
            return True, 0