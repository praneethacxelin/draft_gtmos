"""In-process token-bucket rate limiter for free-tier protection.

Each integration gets its own bucket; exceeding the bucket raises
``RateLimitExceeded`` which the route layer turns into a 429 response.

Buckets live in process memory (single-replica deployment), so they
reset on restart — that is intentional for a free-tier showcase: the
limiter exists to avoid burning through optional third-party quotas
or the Replit AI proxy budget, not to enforce hard SaaS-tier billing.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass


class RateLimitExceeded(Exception):
    """Raised when a token bucket has no capacity left."""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = max(1.0, float(retry_after))
        super().__init__(
            f"Free-tier rate limit hit for {name}. "
            f"Try again in ~{self.retry_after:.0f}s."
        )


@dataclass
class _Bucket:
    capacity: float
    refill_per_sec: float
    tokens: float
    last_refill: float


# name -> (capacity, refill_per_minute)
_LIMITS: dict[str, tuple[float, float]] = {
    "openai": (60, 60),
    "serpapi": (20, 20),
    "apollo": (30, 30),
    "instantly": (10, 10),
    "clay": (20, 20),
}

_BUCKETS: dict[str, _Bucket] = {}
_LOCK = threading.Lock()


def _bucket(name: str) -> _Bucket:
    cap, per_min = _LIMITS.get(name, (60, 60))
    b = _BUCKETS.get(name)
    if b is None:
        b = _Bucket(
            capacity=cap,
            refill_per_sec=per_min / 60.0,
            tokens=cap,
            last_refill=time.monotonic(),
        )
        _BUCKETS[name] = b
    return b


def consume(name: str, cost: float = 1.0) -> None:
    """Atomically deduct ``cost`` tokens; raise if insufficient."""
    with _LOCK:
        b = _bucket(name)
        now = time.monotonic()
        elapsed = now - b.last_refill
        b.tokens = min(b.capacity, b.tokens + elapsed * b.refill_per_sec)
        b.last_refill = now
        if b.tokens < cost:
            needed = cost - b.tokens
            retry = needed / b.refill_per_sec if b.refill_per_sec else 60.0
            raise RateLimitExceeded(name, retry)
        b.tokens -= cost


def status() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with _LOCK:
        now = time.monotonic()
        for name, (cap, per_min) in _LIMITS.items():
            b = _bucket(name)
            elapsed = now - b.last_refill
            current = min(b.capacity, b.tokens + elapsed * b.refill_per_sec)
            out[name] = {
                "capacity": cap,
                "per_minute": per_min,
                "available": round(current, 1),
            }
    return out
