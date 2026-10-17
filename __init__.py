"""ratelib 2.1.0 - token bucket rate limiter. Upstream package."""
import time


class RateLimiter:
    def __init__(self, capacity, refill_per_sec):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._tokens = float(capacity)
        self._last = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.refill_per_sec)
        self._last = now

    def allow(self):
        self._refill()
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False

    def tokens(self):
        self._refill()
        return self._tokens
