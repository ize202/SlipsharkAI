from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from slipshark.api.app import create_app
from slipshark.config import Environment, Settings
from slipshark.domain.models import (
    STREAM_EVENT_ADAPTER,
    DeltaEvent,
    DoneEvent,
    Platform,
    PublicSource,
    ResearchQuery,
    SearchDecision,
    SourceDocument,
    SourcesEvent,
    StreamEvent,
)
from slipshark.security.rate_limit import InMemoryRateLimiter

FIXED_QUERY = "How can a basketball team improve its late-game offense?"

_API_KEY = "local_simulation_key_0000000000000001"
_AUTH_HEADERS = {"X-API-Key": _API_KEY}
_MAX_RESULTS = 2
_SEARCH_QUERY = "basketball late-game offense spacing decision making"
_ANSWER_DELTAS = (
    "Late-game offense improves when spacing stays wide, ",
    "the first action starts early, and each player has a simple read.",
)

_SOURCE_DOCUMENTS = (
    SourceDocument(
        source=PublicSource(
            id="local-spacing-note",
            title="Spacing and late-game possessions",
            url=AnyHttpUrl("https://example.com/basketball/spacing"),
            published_at=datetime(2024, 6, 1, tzinfo=UTC),
            snippet="A local fixture about keeping driving and passing lanes open.",
        ),
        text="Keep the corners occupied and avoid bringing a second defender to the ball.",
    ),
    SourceDocument(
        source=PublicSource(
            id="local-decision-note",
            title="Simple reads under pressure",
            url=AnyHttpUrl("https://example.com/basketball/decisions"),
            published_at=datetime(2024, 6, 2, tzinfo=UTC),
            snippet="A local fixture about making the first useful read quickly.",
        ),
        text="Begin the action early enough to preserve time for a second decision.",
    ),
)


class SmokeFailure(RuntimeError):
    pass


class _OfflineSettings(Settings):
    """Settings variant whose only input is the constructor used below."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del cls, settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


class _OfflineSearchProvider:
    async def search(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]:
        if query != _SEARCH_QUERY:
            raise SmokeFailure(f"unexpected search query: {query!r}")
        if limit != _MAX_RESULTS:
            raise SmokeFailure(f"unexpected search result limit: {limit}")
        return _SOURCE_DOCUMENTS


class _OfflineAnswerProvider:
    async def decide_search(
        self,
        query: ResearchQuery,
        *,
        now: datetime,
    ) -> SearchDecision:
        del now
        if query.query != FIXED_QUERY:
            raise SmokeFailure(f"unexpected research query: {query.query!r}")
        if query.platform is not Platform.MOBILE or query.max_results != _MAX_RESULTS:
            raise SmokeFailure("unexpected research request options")
        return SearchDecision(requires_search=True, search_query=_SEARCH_QUERY)

    def stream_answer(
        self,
        query: ResearchQuery,
        *,
        sources: Sequence[SourceDocument],
        now: datetime,
    ) -> AsyncIterator[str]:
        del query, now
        if tuple(sources) != _SOURCE_DOCUMENTS:
            raise SmokeFailure("research service did not pass the local source fixtures")

        async def generate() -> AsyncIterator[str]:
            for delta in _ANSWER_DELTAS:
                yield delta

        return generate()


def build_offline_app() -> FastAPI:
    settings = _OfflineSettings(
        environment=Environment.TEST,
        openai_api_key=None,
        exa_api_key=None,
        api_keys={"local-simulation": SecretStr(_API_KEY)},
        redis_url=None,
        max_results=_MAX_RESULTS,
    )
    return create_app(
        settings=settings,
        answer_provider=_OfflineAnswerProvider(),
        search_provider=_OfflineSearchProvider(),
        rate_limiter=InMemoryRateLimiter(),
    )


@asynccontextmanager
async def _client_for(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://local-simulation") as client:
            yield client


def _require_response(
    response: Response,
    *,
    label: str,
    status_code: int,
    body: object | None = None,
) -> None:
    if response.status_code != status_code:
        raise SmokeFailure(
            f"{label} returned {response.status_code}, expected {status_code}: {response.text}"
        )
    if body is not None and response.json() != body:
        raise SmokeFailure(f"{label} returned an unexpected body: {response.text}")


def validate_sse_transcript(payload: bytes) -> tuple[StreamEvent, ...]:
    if not payload or not payload.endswith(b"\n\n"):
        raise SmokeFailure("SSE transcript is empty or missing its final frame boundary")

    frames = payload[:-2].split(b"\n\n")
    events: list[StreamEvent] = []
    for index, frame in enumerate(frames, start=1):
        lines = frame.splitlines()
        if len(lines) != 2:
            raise SmokeFailure(f"SSE frame {index} does not contain exactly two lines")
        event_line, data_line = lines
        if not event_line.startswith(b"event: ") or not data_line.startswith(b"data: "):
            raise SmokeFailure(f"SSE frame {index} is missing its event or data field")

        try:
            event_name = event_line.removeprefix(b"event: ").decode("ascii")
            event = STREAM_EVENT_ADAPTER.validate_json(data_line.removeprefix(b"data: "))
        except (UnicodeDecodeError, ValueError) as error:
            raise SmokeFailure(f"SSE frame {index} contains invalid JSON event data") from error

        if event.type != event_name:
            raise SmokeFailure(
                f"SSE frame {index} labels {event_name!r} but contains {event.type!r} JSON"
            )
        events.append(event)

    return tuple(events)


def validate_expected_research(events: tuple[StreamEvent, ...]) -> None:
    expected_types = ("delta", "delta", "sources", "done")
    actual_types = tuple(event.type for event in events)
    if actual_types != expected_types:
        raise SmokeFailure(f"unexpected research event sequence: {actual_types}")

    first_delta, second_delta, sources, done = events
    if not isinstance(first_delta, DeltaEvent) or first_delta.text != _ANSWER_DELTAS[0]:
        raise SmokeFailure("the first delta event does not match the local fixture")
    if not isinstance(second_delta, DeltaEvent) or second_delta.text != _ANSWER_DELTAS[1]:
        raise SmokeFailure("the second delta event does not match the local fixture")
    if not isinstance(sources, SourcesEvent):
        raise SmokeFailure("the research stream is missing its sources event")
    if sources.sources != tuple(document.source for document in _SOURCE_DOCUMENTS):
        raise SmokeFailure("the sources event does not match the local fixtures")
    if not isinstance(done, DoneEvent):
        raise SmokeFailure("the research stream is missing its done event")

    request_ids = {event.request_id for event in events}
    if len(request_ids) != 1:
        raise SmokeFailure("research events do not share one request ID")


async def collect_research_transcript(app: FastAPI | None = None) -> bytes:
    offline_app = app if app is not None else build_offline_app()
    async with _client_for(offline_app) as client:
        return await _collect_research_transcript(client)


async def _collect_research_transcript(client: AsyncClient) -> bytes:
    response = await client.post(
        "/research",
        headers=_AUTH_HEADERS,
        json={
            "query": FIXED_QUERY,
            "platform": Platform.MOBILE,
            "max_results": _MAX_RESULTS,
        },
    )
    _require_response(response, label="POST /research", status_code=200)
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("text/event-stream"):
        raise SmokeFailure(f"POST /research returned an unexpected content type: {content_type!r}")
    for document in _SOURCE_DOCUMENTS:
        if document.text.encode() in response.content:
            raise SmokeFailure("the research stream leaked a private source body")
    events = validate_sse_transcript(response.content)
    validate_expected_research(events)
    return response.content


async def run_smoke() -> None:
    app = build_offline_app()
    async with _client_for(app) as client:
        live = await client.get("/health/live")
        _require_response(live, label="GET /health/live", status_code=200, body={"status": "ok"})
        print("PASS GET /health/live")

        ready = await client.get("/health/ready")
        _require_response(
            ready,
            label="GET /health/ready",
            status_code=200,
            body={
                "status": "ready",
                "configuration": "ready",
                "redis": "not_required",
            },
        )
        print("PASS GET /health/ready")

        await _collect_research_transcript(client)
    print("PASS POST /research (delta, delta, sources, done)")
    print("Slipshark offline smoke passed")


def main() -> int:
    try:
        asyncio.run(run_smoke())
    except Exception as error:
        print(f"Slipshark offline smoke failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
