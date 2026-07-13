from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from starlette.types import Message, Scope

from slipshark.api.app import create_app
from slipshark.config import Environment, Settings
from slipshark.domain.models import (
    Platform,
    PublicSource,
    ResearchQuery,
    SearchDecision,
    SourceDocument,
)
from slipshark.providers.protocols import ProviderUnavailableError
from slipshark.security.rate_limit import RateLimitDecision

_API_KEY = "sk_v1_abcdefghijklmnopqrstuvwxyz123456"
_AUTH_HEADERS = {"X-API-Key": _API_KEY}


class _RecordingSearchProvider:
    def __init__(self, results: tuple[SourceDocument, ...] = ()) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]:
        self.calls.append((query, limit))
        return self.results


class _RecordingAnswerProvider:
    def __init__(
        self,
        *,
        decision: SearchDecision | None = None,
        deltas: tuple[str, ...] = (),
        stream_error: Exception | None = None,
    ) -> None:
        self.decision = decision or SearchDecision(requires_search=False)
        self.deltas = deltas
        self.stream_error = stream_error
        self.decision_calls: list[ResearchQuery] = []
        self.answer_calls: list[ResearchQuery] = []
        self.stream_closed = False

    async def decide_search(
        self,
        query: ResearchQuery,
        *,
        now: datetime,
    ) -> SearchDecision:
        self.decision_calls.append(query)
        return self.decision

    def stream_answer(
        self,
        query: ResearchQuery,
        *,
        sources: Sequence[SourceDocument],
        now: datetime,
    ) -> AsyncIterator[str]:
        self.answer_calls.append(query)

        async def generate() -> AsyncIterator[str]:
            try:
                if self.stream_error is not None:
                    raise self.stream_error
                for delta in self.deltas:
                    yield delta
            finally:
                self.stream_closed = True

        return generate()


class _BlockingAfterFirstDeltaAnswerProvider:
    def __init__(self) -> None:
        self.stream_closed = asyncio.Event()

    async def decide_search(
        self,
        query: ResearchQuery,
        *,
        now: datetime,
    ) -> SearchDecision:
        return SearchDecision(requires_search=False)

    def stream_answer(
        self,
        query: ResearchQuery,
        *,
        sources: Sequence[SourceDocument],
        now: datetime,
    ) -> AsyncIterator[str]:
        async def generate() -> AsyncIterator[str]:
            try:
                yield "first"
                await asyncio.Event().wait()
            finally:
                self.stream_closed.set()

        return generate()


class _RecordingLimiter:
    def __init__(self, decision: RateLimitDecision) -> None:
        self.decision = decision
        self.calls: list[tuple[str, int, int]] = []

    async def ready(self) -> bool:
        return True

    async def consume(
        self,
        subject: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        self.calls.append((subject, limit, window_seconds))
        return self.decision


type _AnswerProvider = _RecordingAnswerProvider | _BlockingAfterFirstDeltaAnswerProvider


@asynccontextmanager
async def _client_for(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def _settings() -> Settings:
    return Settings(
        environment=Environment.TEST,
        api_keys={"ios-client": _API_KEY},
        rate_limit_requests=3,
        rate_limit_window_seconds=17,
        _env_file=None,
    )


def _allowed_limiter() -> _RecordingLimiter:
    return _RecordingLimiter(RateLimitDecision(allowed=True, remaining=2, retry_after_seconds=0))


def _app(
    *,
    answer: _AnswerProvider | None = None,
    search: _RecordingSearchProvider | None = None,
    limiter: _RecordingLimiter | None = None,
    settings: Settings | None = None,
) -> tuple[FastAPI, _AnswerProvider, _RecordingSearchProvider, _RecordingLimiter]:
    answer_provider = answer or _RecordingAnswerProvider(deltas=("answer",))
    search_provider = search or _RecordingSearchProvider()
    rate_limiter = limiter or _allowed_limiter()
    app = create_app(
        settings=settings or _settings(),
        answer_provider=answer_provider,
        search_provider=search_provider,
        rate_limiter=rate_limiter,
    )
    return app, answer_provider, search_provider, rate_limiter


def _sse_payloads(response: Response) -> list[dict[str, object]]:
    frames = [frame for frame in response.content.split(b"\n\n") if frame]
    payloads: list[dict[str, object]] = []

    for frame in frames:
        event_line, data_line = frame.splitlines()
        event_type = event_line.removeprefix(b"event: ").decode("ascii")
        payload = json.loads(data_line.removeprefix(b"data: "))
        assert isinstance(payload, dict)
        assert payload["type"] == event_type
        payloads.append(payload)

    return payloads


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b'{"query":', "application/json"),
        (json.dumps({"query": "   "}).encode(), "application/json"),
        (json.dumps({"query": "x" * 1001}).encode(), "application/json"),
    ],
)
@pytest.mark.asyncio
async def test_invalid_json_and_queries_use_fastapi_validation_responses(
    content: bytes,
    content_type: str,
) -> None:
    app, _, _, _ = _app()

    async with _client_for(app) as client:
        response = await client.post(
            "/research",
            content=content,
            headers={**_AUTH_HEADERS, "Content-Type": content_type},
        )

    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], list)


@pytest.mark.asyncio
async def test_authentication_and_rate_limit_finish_before_research_starts() -> None:
    answer = _RecordingAnswerProvider(deltas=("must not run",))
    search = _RecordingSearchProvider()
    limiter = _RecordingLimiter(
        RateLimitDecision(allowed=False, remaining=0, retry_after_seconds=9)
    )
    app, _, _, _ = _app(answer=answer, search=search, limiter=limiter)

    async with _client_for(app) as client:
        missing = await client.post("/research", json={"query": "latest score"})
        unknown = await client.post(
            "/research",
            json={"query": "latest score"},
            headers={"X-API-Key": "x" * 32},
        )

        assert limiter.calls == []
        assert answer.decision_calls == []
        assert search.calls == []

        denied = await client.post(
            "/research",
            json={"query": "latest score"},
            headers=_AUTH_HEADERS,
        )

    assert missing.status_code == unknown.status_code == 401
    assert missing.json() == unknown.json() == {"detail": "Not authenticated"}
    assert denied.status_code == 429
    assert denied.headers["retry-after"] == "9"
    assert limiter.calls == [("ios-client", 3, 17)]
    assert answer.decision_calls == []
    assert answer.answer_calls == []
    assert search.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "sixsix", "max_results": 2},
        {"query": "valid", "max_results": 3},
    ],
)
@pytest.mark.asyncio
async def test_runtime_settings_can_tighten_request_limits_without_starting_research(
    payload: dict[str, object],
) -> None:
    settings = Settings(
        environment=Environment.TEST,
        api_keys={"ios-client": _API_KEY},
        max_query_chars=5,
        max_results=2,
        _env_file=None,
    )
    answer = _RecordingAnswerProvider(deltas=("must not run",))
    limiter = _allowed_limiter()
    app, _, search, _ = _app(answer=answer, limiter=limiter, settings=settings)

    async with _client_for(app) as client:
        response = await client.post("/research", json=payload, headers=_AUTH_HEADERS)

    assert response.status_code == 422
    assert response.json() == {"detail": "Research request exceeds the configured limits."}
    assert limiter.calls == []
    assert answer.decision_calls == []
    assert answer.answer_calls == []
    assert search.calls == []


@pytest.mark.asyncio
async def test_successful_research_stream_has_json_events_sources_and_transport_headers() -> None:
    source = SourceDocument(
        source=PublicSource(
            id="league",
            title="League source",
            url="https://example.com/league",
            snippet="Final score and match report.",
        ),
        text="Full source body remains server-side.",
    )
    search = _RecordingSearchProvider((source,))
    answer = _RecordingAnswerProvider(
        decision=SearchDecision(requires_search=True, search_query="final score"),
        deltas=("The final ", "ended 2-1."),
    )
    app, _, _, limiter = _app(answer=answer, search=search)

    async with _client_for(app) as client:
        response = await client.post(
            "/research",
            json={"query": "Who won?", "platform": "web", "max_results": 4},
            headers=_AUTH_HEADERS,
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert "connection" not in response.headers
    assert "transfer-encoding" not in response.headers

    payloads = _sse_payloads(response)
    assert [payload["type"] for payload in payloads] == [
        "delta",
        "delta",
        "sources",
        "done",
    ]
    request_ids = {UUID(str(payload["request_id"])) for payload in payloads}
    assert len(request_ids) == 1
    assert payloads[2]["sources"] == [
        {
            "id": "league",
            "title": "League source",
            "url": "https://example.com/league",
            "published_at": None,
            "snippet": "Final score and match report.",
        }
    ]
    assert search.calls == [("final score", 4)]
    assert answer.decision_calls == [
        ResearchQuery(query="Who won?", platform=Platform.WEB, max_results=4)
    ]
    assert limiter.calls == [("ios-client", 3, 17)]
    assert answer.stream_closed is True


@pytest.mark.asyncio
async def test_typed_stream_failure_is_logged_once_and_becomes_one_safe_error_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_detail = "private upstream trace marker"
    answer = _RecordingAnswerProvider(stream_error=ProviderUnavailableError(private_detail))
    app, _, _, _ = _app(answer=answer)

    with caplog.at_level(logging.ERROR):
        async with _client_for(app) as client:
            response = await client.post(
                "/research",
                json={"query": "latest score"},
                headers=_AUTH_HEADERS,
            )

    assert response.status_code == 200
    payloads = _sse_payloads(response)
    assert [payload["type"] for payload in payloads] == ["error"]
    [payload] = payloads
    assert payload["code"] == "provider_unavailable"
    assert payload["message"] == "Unable to complete the research request."
    assert private_detail not in response.text

    error_records = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(error_records) == 1
    [record] = error_records
    request_id = UUID(str(payload["request_id"]))
    assert str(request_id) in record.getMessage() or getattr(record, "request_id", None) == str(
        request_id
    )
    assert record.exc_info is not None
    assert private_detail in caplog.text
    assert answer.stream_closed is True


@pytest.mark.asyncio
async def test_http_disconnect_cancels_and_closes_the_provider_stream() -> None:
    answer = _BlockingAfterFirstDeltaAnswerProvider()
    app, _, _, limiter = _app(answer=answer)
    first_body_sent = asyncio.Event()
    request_sent = False
    sent_messages: list[Message] = []
    request_body = json.dumps({"query": "latest score"}).encode()

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/research",
        "raw_path": b"/research",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"content-type", b"application/json"),
            (b"x-api-key", _API_KEY.encode()),
        ],
        "client": ("127.0.0.1", 54321),
        "server": ("test", 80),
    }

    async def receive() -> Message:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": request_body, "more_body": False}
        await first_body_sent.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent_messages.append(message)
        if message["type"] == "http.response.body" and message.get("more_body", False):
            first_body_sent.set()

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(app(scope, receive, send), timeout=1)

    await asyncio.wait_for(answer.stream_closed.wait(), timeout=1)
    assert first_body_sent.is_set()
    assert answer.stream_closed.is_set()
    assert limiter.calls == [("ios-client", 3, 17)]
    assert any(message["type"] == "http.response.start" for message in sent_messages)
