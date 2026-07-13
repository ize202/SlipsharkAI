from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from slipshark.api.app import create_app
from slipshark.config import Environment, Settings
from slipshark.domain.models import ResearchQuery, SearchDecision, SourceDocument
from slipshark.security.rate_limit import InMemoryRateLimiter, RateLimitDecision

_API_KEY = "sk_v1_abcdefghijklmnopqrstuvwxyz123456"


class _FailIfCalledAnswerProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def decide_search(
        self,
        query: ResearchQuery,
        *,
        now: datetime,
    ) -> SearchDecision:
        self.calls += 1
        raise AssertionError("health checks must not call the answer provider")

    def stream_answer(
        self,
        query: ResearchQuery,
        *,
        sources: Sequence[SourceDocument],
        now: datetime,
    ) -> AsyncIterator[str]:
        self.calls += 1
        raise AssertionError("health checks must not call the answer provider")


class _FailIfCalledSearchProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]:
        self.calls += 1
        raise AssertionError("health checks must not call the search provider")


class _SharedLimiter:
    def __init__(self, *, ready: bool) -> None:
        self.is_ready = ready
        self.ready_calls = 0
        self.consume_calls = 0

    async def ready(self) -> bool:
        self.ready_calls += 1
        return self.is_ready

    async def consume(
        self,
        subject: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        self.consume_calls += 1
        raise AssertionError("health checks must not consume a rate-limit token")


@asynccontextmanager
async def _client_for(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def _local_settings() -> Settings:
    return Settings(environment=Environment.TEST, _env_file=None)


def _production_settings() -> Settings:
    return Settings(
        environment=Environment.PRODUCTION,
        openai_api_key="openai-production-placeholder",
        exa_api_key="exa-production-placeholder",
        api_keys={"ios-client": _API_KEY},
        redis_url="redis://redis.example.invalid:6379/0",
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_liveness_needs_no_provider_keys_or_paid_calls() -> None:
    answer = _FailIfCalledAnswerProvider()
    search = _FailIfCalledSearchProvider()
    app = create_app(
        settings=_local_settings(),
        answer_provider=answer,
        search_provider=search,
        rate_limiter=InMemoryRateLimiter(),
    )

    async with _client_for(app) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert answer.calls == 0
    assert search.calls == 0


@pytest.mark.asyncio
async def test_local_readiness_reports_redis_not_required_without_provider_calls() -> None:
    answer = _FailIfCalledAnswerProvider()
    search = _FailIfCalledSearchProvider()
    app = create_app(
        settings=_local_settings(),
        answer_provider=answer,
        search_provider=search,
        rate_limiter=InMemoryRateLimiter(),
    )

    async with _client_for(app) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "configuration": "ready",
        "redis": "not_required",
    }
    assert answer.calls == 0
    assert search.calls == 0


@pytest.mark.parametrize(
    ("redis_ready", "expected_status", "expected_body"),
    [
        (
            True,
            200,
            {"status": "ready", "configuration": "ready", "redis": "ready"},
        ),
        (
            False,
            503,
            {
                "status": "not_ready",
                "configuration": "ready",
                "redis": "unavailable",
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_production_readiness_uses_only_the_shared_limiter_probe(
    redis_ready: bool,
    expected_status: int,
    expected_body: dict[str, str],
) -> None:
    answer = _FailIfCalledAnswerProvider()
    search = _FailIfCalledSearchProvider()
    limiter = _SharedLimiter(ready=redis_ready)
    app = create_app(
        settings=_production_settings(),
        answer_provider=answer,
        search_provider=search,
        rate_limiter=limiter,
    )

    async with _client_for(app) as client:
        response = await client.get("/health/ready")

    assert response.status_code == expected_status
    assert response.json() == expected_body
    assert limiter.ready_calls == 1
    assert limiter.consume_calls == 0
    assert answer.calls == 0
    assert search.calls == 0
