from __future__ import annotations

import asyncio
import inspect

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from slipshark.api.dependencies import enforce_rate_limit
from slipshark.security.rate_limit import (
    InMemoryRateLimiter,
    RateLimitDecision,
    RateLimiter,
    RateLimitUnavailableError,
    RedisRateLimiter,
)

_UNSET = object()


class _Clock:
    def __init__(self) -> None:
        self.value = 1_000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


@pytest.mark.asyncio
async def test_in_memory_limiter_enforces_ten_requests_per_sixty_seconds() -> None:
    clock = _Clock()
    limiter: RateLimiter = InMemoryRateLimiter(clock=clock)

    decisions = [
        await limiter.consume("ios-client", limit=10, window_seconds=60) for _ in range(11)
    ]

    assert [decision.allowed for decision in decisions] == [True] * 10 + [False]
    assert [decision.remaining for decision in decisions[:10]] == list(range(9, -1, -1))
    assert decisions[-1].remaining == 0
    assert decisions[-1].retry_after_seconds == 60


@pytest.mark.asyncio
async def test_in_memory_limiter_is_per_principal_and_resets_on_window_boundary() -> None:
    clock = _Clock()
    limiter = InMemoryRateLimiter(clock=clock)

    for _ in range(10):
        assert (await limiter.consume("ios-client", limit=10, window_seconds=60)).allowed

    assert not (await limiter.consume("ios-client", limit=10, window_seconds=60)).allowed
    assert (await limiter.consume("automation", limit=10, window_seconds=60)).allowed

    clock.advance(60)
    reset = await limiter.consume("ios-client", limit=10, window_seconds=60)
    assert reset == RateLimitDecision(allowed=True, remaining=9, retry_after_seconds=0)


@pytest.mark.asyncio
async def test_in_memory_concurrent_consumption_never_exceeds_the_limit() -> None:
    limiter = InMemoryRateLimiter(clock=_Clock())

    decisions = await asyncio.gather(
        *(limiter.consume("ios-client", limit=10, window_seconds=60) for _ in range(25))
    )

    assert sum(decision.allowed for decision in decisions) == 10
    assert sum(not decision.allowed for decision in decisions) == 15


def test_in_memory_limiter_is_explicitly_not_production_safe() -> None:
    documentation = inspect.getdoc(InMemoryRateLimiter) or ""
    assert "not production-safe" in documentation.lower()


class _FakeRedis:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        result: object = _UNSET,
    ) -> None:
        self.error = error
        self.result = result
        self.calls: list[tuple[str, int, tuple[object, ...]]] = []
        self.counts: dict[str, int] = {}

    async def eval(self, script: str, numkeys: int, *args: object) -> object:
        self.calls.append((script, numkeys, args))
        if self.error is not None:
            raise self.error
        if self.result is not _UNSET:
            return self.result
        key = str(args[0])
        self.counts[key] = self.counts.get(key, 0) + 1
        return (self.counts[key], 60)


@pytest.mark.asyncio
async def test_redis_limiter_uses_one_atomic_increment_and_expiry_operation() -> None:
    redis = _FakeRedis()
    limiter = RedisRateLimiter(redis, key_prefix="slipshark:test")

    decision = await limiter.consume("ios-client", limit=10, window_seconds=60)

    assert decision == RateLimitDecision(allowed=True, remaining=9, retry_after_seconds=0)
    [(script, numkeys, args)] = redis.calls
    assert numkeys == 1
    assert "INCR" in script.upper()
    assert "EXPIRE" in script.upper()
    assert "TTL" in script.upper()
    assert "TTL < 0" in script.upper()
    assert args[0] == "slipshark:test:ios-client"
    assert args[1:] == (60,)


@pytest.mark.asyncio
async def test_redis_limiter_allows_at_limit_then_blocks_with_minimum_retry() -> None:
    redis = _FakeRedis(result=(10, 1))
    limiter = RedisRateLimiter(redis)

    allowed = await limiter.consume("ios-client", limit=10, window_seconds=60)
    assert allowed == RateLimitDecision(allowed=True, remaining=0, retry_after_seconds=0)

    redis.result = (11, 0)
    denied = await limiter.consume("ios-client", limit=10, window_seconds=60)
    assert denied == RateLimitDecision(allowed=False, remaining=0, retry_after_seconds=1)


@pytest.mark.asyncio
async def test_redis_unavailability_fails_closed_with_private_typed_error() -> None:
    redis = _FakeRedis(error=RedisConnectionError("private redis address"))
    limiter = RedisRateLimiter(redis)

    with pytest.raises(RateLimitUnavailableError) as caught:
        await limiter.consume("ios-client", limit=10, window_seconds=60)

    assert "private redis address" not in str(caught.value)


class _ProbeRedis(_FakeRedis):
    def __init__(
        self,
        *,
        ready: bool = True,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.ready_value = ready
        self.probe_error = error
        self.ping_calls = 0

    async def ping(self) -> bool:
        self.ping_calls += 1
        if self.probe_error is not None:
            raise self.probe_error
        return self.ready_value


@pytest.mark.asyncio
async def test_redis_readiness_uses_a_bounded_non_mutating_ping() -> None:
    redis = _ProbeRedis(ready=True)
    limiter = RedisRateLimiter(redis)

    assert await limiter.ready() is True
    assert redis.ping_calls == 1
    assert redis.calls == []


@pytest.mark.asyncio
async def test_redis_readiness_returns_false_when_ping_is_unavailable() -> None:
    redis = _ProbeRedis(error=RedisConnectionError("private redis address"))
    limiter = RedisRateLimiter(redis)

    assert await limiter.ready() is False
    assert redis.ping_calls == 1


@pytest.mark.parametrize(
    "result",
    [
        None,
        (1,),
        ("1", 60),
        (1, -1),
        (0, 60),
        (True, 60),
    ],
)
@pytest.mark.asyncio
async def test_malformed_redis_results_fail_closed(result: object) -> None:
    redis = _FakeRedis(result=result)
    limiter = RedisRateLimiter(redis)

    with pytest.raises(RateLimitUnavailableError):
        await limiter.consume("ios-client", limit=10, window_seconds=60)


class _BlockingRedis:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def eval(self, script: str, numkeys: int, *args: object) -> object:
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_redis_timeout_fails_closed() -> None:
    redis = _BlockingRedis()
    limiter = RedisRateLimiter(redis, operation_timeout_seconds=0.001)

    with pytest.raises(RateLimitUnavailableError):
        await limiter.consume("ios-client", limit=10, window_seconds=60)


@pytest.mark.asyncio
async def test_redis_cancellation_propagates() -> None:
    redis = _BlockingRedis()
    limiter = RedisRateLimiter(redis, operation_timeout_seconds=60)
    task = asyncio.create_task(limiter.consume("ios-client", limit=10, window_seconds=60))
    await redis.started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


class _RecordingLimiter:
    def __init__(self, decision: RateLimitDecision | Exception) -> None:
        self.decision = decision
        self.calls: list[tuple[str, int, int]] = []

    async def consume(
        self,
        subject: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        self.calls.append((subject, limit, window_seconds))
        if isinstance(self.decision, Exception):
            raise self.decision
        return self.decision


@pytest.mark.asyncio
async def test_dependency_applies_ten_per_sixty_policy_and_returns_retry_after() -> None:
    limiter = _RecordingLimiter(
        RateLimitDecision(allowed=False, remaining=0, retry_after_seconds=17)
    )

    with pytest.raises(HTTPException) as caught:
        await enforce_rate_limit("ios-client", limiter=limiter)

    assert limiter.calls == [("ios-client", 10, 60)]
    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After": "17"}


@pytest.mark.asyncio
async def test_dependency_fails_closed_when_production_limiter_is_unavailable() -> None:
    limiter = _RecordingLimiter(RateLimitUnavailableError("private backend detail"))

    with pytest.raises(HTTPException) as caught:
        await enforce_rate_limit("ios-client", limiter=limiter)

    assert caught.value.status_code == 503
    assert "private backend detail" not in str(caught.value.detail)


@pytest.mark.asyncio
async def test_dependency_does_not_hide_unexpected_programming_errors() -> None:
    limiter = _RecordingLimiter(RuntimeError("implementation bug"))

    with pytest.raises(RuntimeError, match="implementation bug"):
        await enforce_rate_limit("ios-client", limiter=limiter)
