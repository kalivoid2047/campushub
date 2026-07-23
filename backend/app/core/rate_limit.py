"""Login rate limiting (docs/08-security-design.md section 2).

In-process sliding-window limiter, keyed independently by (tenant, email)
and by client IP — credential stuffing against one account and distributed
guessing across many accounts from one source are different attack shapes,
so both need their own counter. In-process state is sufficient for the
single-instance deployment in docs/13-deployment-guide.md section 1; a
horizontally-scaled deployment would need a shared backend (e.g. Redis)
instead.
"""

import threading
import time
from collections import defaultdict


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int = 5,
        base_lockout_seconds: float = 1.0,
        max_lockout_seconds: float = 300.0,
        window_seconds: float = 900.0,
    ) -> None:
        self._max_attempts = max_attempts
        self._base = base_lockout_seconds
        self._cap = max_lockout_seconds
        self._window = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune_locked(self, key: str, now: float) -> None:
        attempts = self._failures[key]
        if attempts:
            self._failures[key] = [t for t in attempts if now - t < self._window]

    def seconds_until_allowed(self, *keys: str) -> float | None:
        """None if none of `keys` is currently locked out, else the number
        of seconds the caller must wait before retrying."""
        now = time.monotonic()
        with self._lock:
            wait = None
            for key in keys:
                self._prune_locked(key, now)
                attempts = self._failures[key]
                count = len(attempts)
                if count < self._max_attempts:
                    continue
                lockout = min(self._cap, self._base * (2 ** (count - self._max_attempts)))
                remaining = lockout - (now - attempts[-1])
                if remaining > 0:
                    wait = remaining if wait is None else max(wait, remaining)
            return wait

    def record_failure(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in keys:
                self._failures[key].append(now)

    def record_success(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


# Mutated in place (never reassigned) so modules that did
# `from app.core.rate_limit import login_rate_limiter` keep seeing a live
# reference — reset_rate_limiter_for_tests() clears it rather than
# replacing it.
login_rate_limiter = LoginRateLimiter()


def reset_rate_limiter_for_tests() -> None:
    login_rate_limiter.reset()
