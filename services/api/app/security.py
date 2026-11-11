"""Owner tokens and rate limits: what keeps a public demo from being abused.

An owner token is a capability. Whoever starts a match receives one, and it is required to move money
in the Shield. Spectators can watch any match but cannot act on it. Only a hash is ever stored.
"""

import hashlib
import hmac
import logging
import secrets
import time
from typing import Protocol

logger = logging.getLogger(__name__)


def new_token() -> str:
    return secrets.token_urlsafe(24)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(token: str | None, stored_hash: str | None) -> bool:
    if not token or not stored_hash:
        return False
    return hmac.compare_digest(hash_token(token), stored_hash)


class Counter(Protocol):
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> object: ...


async def within_limit(redis: Counter, key: str, limit: int, window_seconds: int) -> bool:
    """A fixed-window counter. If the counter store is down it allows the request: a limit
    should never take the whole demo down with it."""
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        return count <= limit
    except Exception:
        logger.warning("rate limit store unavailable; allowing the request", exc_info=True)
        return True


def window(seconds: int) -> int:
    """The index of the current fixed window, so a key changes when the window rolls over."""
    return int(time.time() // seconds)
