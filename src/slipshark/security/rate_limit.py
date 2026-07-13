from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from redis.exceptions import RedisError

_SUBJECT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")

_FIXED_WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if count == 1 or ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = redis.call('TTL', KEYS[1])
end
return {count, ttl}
""".strip()


class RateLimitUnavailableError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int

    def __post_init__(self) -> None:
        if self.remaining < 0 or self.retry_after_seconds < 0:
            raise ValueError("rate-limit decision values must not be negative")
        if self.allowed and self.retry_after_seconds != 0:
            raise ValueError("allowed decisions cannot include a retry delay")
        if not self.allowed and self.retry_after_seconds < 1:
            raise ValueError("denied decisions require a positive retry delay")


class RateLimiter(Protocol):
    async def consume(
        self,
        subject: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision: ...


@dataclass(slots=True)
class _Window:
    started_at: float
    window_seconds: int
    count: int


class InMemoryRateLimiter:
    """Deterministic local/test limiter; this implementation is not production-safe."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._windows: dict[str, _Window] = {}
        self._lock = asyncio.Lock()

    async def consume(
        self,
        subject: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        _validate_request(subject, limit=limit, window_seconds=window_seconds)
        async with self._lock:
            now = self._clock()
            window = self._windows.get(subject)
            if (
                window is None
                or window.window_seconds != window_seconds
                or now < window.started_at
                or now >= window.started_at + window_seconds
            ):
                window = _Window(started_at=now, window_seconds=window_seconds, count=0)
                self._windows[subject] = window

            window.count += 1
            allowed = window.count <= limit
            remaining = max(limit - window.count, 0)
            retry_after = 0
            if not allowed:
                retry_after = max(
                    1,
                    math.ceil(window.started_at + window_seconds - now),
                )
            return RateLimitDecision(
                allowed=allowed,
                remaining=remaining,
                retry_after_seconds=retry_after,
            )


class _RedisEvalClient(Protocol):
    async def eval(self, script: str, numkeys: int, *args: object) -> object: ...


class RedisRateLimiter:
    def __init__(
        self,
        redis: _RedisEvalClient,
        *,
        key_prefix: str = "slipshark:rate_limit",
        operation_timeout_seconds: float = 2,
    ) -> None:
        normalized_prefix = key_prefix.strip(": ")
        if not normalized_prefix:
            raise ValueError("Redis rate-limit key prefix must not be blank")
        if not math.isfinite(operation_timeout_seconds) or operation_timeout_seconds <= 0:
            raise ValueError("Redis rate-limit operation timeout must be positive and finite")
        self._redis = redis
        self._key_prefix = normalized_prefix
        self._operation_timeout_seconds = operation_timeout_seconds

    async def consume(
        self,
        subject: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        _validate_request(subject, limit=limit, window_seconds=window_seconds)
        key = f"{self._key_prefix}:{subject}"
        try:
            async with asyncio.timeout(self._operation_timeout_seconds):
                raw_result = await self._redis.eval(
                    _FIXED_WINDOW_SCRIPT,
                    1,
                    key,
                    window_seconds,
                )
            count, ttl = self._parse_result(raw_result)
        except (RedisError, TimeoutError) as error:
            raise RateLimitUnavailableError("Redis rate limiter is unavailable.") from error
        except (TypeError, ValueError) as error:
            raise RateLimitUnavailableError(
                "Redis rate limiter returned an invalid result."
            ) from error

        allowed = count <= limit
        return RateLimitDecision(
            allowed=allowed,
            remaining=max(limit - count, 0),
            retry_after_seconds=0 if allowed else max(ttl, 1),
        )

    @classmethod
    def _parse_result(cls, result: object) -> tuple[int, int]:
        if not isinstance(result, (list, tuple)) or len(result) != 2:
            raise ValueError("Redis rate-limit result must contain count and TTL")
        count, ttl = result
        if type(count) is not int or type(ttl) is not int:
            raise TypeError("Redis rate-limit result values must be integers")
        if count < 1 or ttl < 0:
            raise ValueError("Redis rate-limit result values are invalid")
        return count, ttl


def _validate_request(subject: str, *, limit: int, window_seconds: int) -> None:
    if _SUBJECT_PATTERN.fullmatch(subject) is None:
        raise ValueError("rate-limit subject is invalid")
    if limit <= 0 or window_seconds <= 0:
        raise ValueError("rate-limit policy values must be positive")
