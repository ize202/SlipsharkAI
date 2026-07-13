import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from slipshark.domain.models import (
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
from slipshark.providers.protocols import ProviderUnavailableError
from slipshark.services.research import (
    ResearchLimits,
    ResearchService,
    ResearchTimeoutError,
    ResearchUnavailableError,
)


class FakeSearchProvider:
    def __init__(
        self,
        results: tuple[SourceDocument, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.results = results
        self.error = error
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]:
        self.calls.append((query, limit))
        if self.error is not None:
            raise self.error
        return self.results


class FakeAnswerProvider:
    def __init__(
        self,
        decision: SearchDecision,
        deltas: tuple[str, ...] = (),
        decision_error: Exception | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        self.decision = decision
        self.deltas = deltas
        self.decision_error = decision_error
        self.stream_error = stream_error
        self.decision_calls: list[tuple[ResearchQuery, datetime]] = []
        self.answer_calls: list[tuple[ResearchQuery, tuple[SourceDocument, ...], datetime]] = []
        self.stream_closed = False

    async def decide_search(self, query: ResearchQuery, *, now: datetime) -> SearchDecision:
        self.decision_calls.append((query, now))
        if self.decision_error is not None:
            raise self.decision_error
        return self.decision

    def stream_answer(
        self,
        query: ResearchQuery,
        *,
        sources: Sequence[SourceDocument],
        now: datetime,
    ) -> AsyncIterator[str]:
        self.answer_calls.append((query, tuple(sources), now))

        async def generate() -> AsyncIterator[str]:
            try:
                if self.stream_error is not None:
                    raise self.stream_error
                for delta in self.deltas:
                    yield delta
            finally:
                self.stream_closed = True

        return generate()


class BlockingAnswerProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def decide_search(self, query: ResearchQuery, *, now: datetime) -> SearchDecision:
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    def stream_answer(
        self,
        query: ResearchQuery,
        *,
        sources: Sequence[SourceDocument],
        now: datetime,
    ) -> AsyncIterator[str]:
        raise AssertionError("answer streaming must not start")


def make_query(*, max_results: int = 5) -> ResearchQuery:
    return ResearchQuery(
        query="Who won the final?",
        platform=Platform.MOBILE,
        max_results=max_results,
    )


def make_document(index: int, text: str) -> SourceDocument:
    return SourceDocument(
        source=PublicSource(
            id=f"source-{index}",
            title=f"Source {index}",
            url=f"https://example.com/{index}",
        ),
        text=text,
    )


async def collect(stream: AsyncIterator[StreamEvent]) -> list[StreamEvent]:
    return [event async for event in stream]


def test_default_limits_match_the_service_contract() -> None:
    limits = ResearchLimits()

    assert limits.planner_timeout_seconds == 10
    assert limits.search_timeout_seconds == 10
    assert limits.answer_timeout_seconds == 30
    assert limits.request_timeout_seconds == 45
    assert limits.per_source_char_limit == 4_000
    assert limits.total_source_char_limit == 16_000
    assert limits.answer_char_limit == 12_000


@pytest.mark.asyncio
async def test_no_search_path_never_calls_search_and_finishes_in_order() -> None:
    search = FakeSearchProvider()
    answer = FakeAnswerProvider(SearchDecision(requires_search=False), deltas=("Answer",))
    service = ResearchService(search, answer)

    events = await collect(service.stream(make_query(), uuid4()))

    assert search.calls == []
    assert [event.type for event in events] == ["delta", "sources", "done"]
    assert isinstance(events[0], DeltaEvent)
    assert isinstance(events[1], SourcesEvent)
    assert events[1].sources == ()
    assert isinstance(events[2], DoneEvent)


@pytest.mark.asyncio
async def test_search_runs_once_and_bounded_source_bodies_reach_answer_provider() -> None:
    documents = tuple(make_document(index, str(index) * 5_000) for index in range(5))
    search = FakeSearchProvider(documents)
    answer = FakeAnswerProvider(
        SearchDecision(requires_search=True, search_query="  final   score  ")
    )
    service = ResearchService(search, answer)

    events = await collect(service.stream(make_query(max_results=7), uuid4()))

    assert search.calls == [("final score", 7)]
    bounded_sources = answer.answer_calls[0][1]
    assert [len(document.text) for document in bounded_sources] == [4_000, 4_000, 4_000, 4_000, 0]
    assert sum(len(document.text) for document in bounded_sources) == 16_000
    sources_event = next(event for event in events if isinstance(event, SourcesEvent))
    assert sources_event.sources == tuple(document.source for document in documents)


@pytest.mark.asyncio
async def test_zero_answer_deltas_still_emit_one_sources_event_and_one_done_event() -> None:
    answer = FakeAnswerProvider(SearchDecision(requires_search=False))
    service = ResearchService(FakeSearchProvider(), answer)

    events = await collect(service.stream(make_query(), uuid4()))

    assert [event.type for event in events] == ["sources", "done"]


@pytest.mark.asyncio
async def test_answer_output_is_capped_and_upstream_stream_is_closed() -> None:
    answer = FakeAnswerProvider(
        SearchDecision(requires_search=False),
        deltas=("a" * 7_000, "b" * 7_000, "unreachable"),
    )
    service = ResearchService(FakeSearchProvider(), answer)

    events = await collect(service.stream(make_query(), uuid4()))

    emitted_text = "".join(event.text for event in events if isinstance(event, DeltaEvent))
    assert emitted_text == "a" * 7_000 + "b" * 5_000
    assert [event.type for event in events[-2:]] == ["sources", "done"]
    assert answer.stream_closed is True


@pytest.mark.asyncio
async def test_planner_deadline_becomes_typed_timeout() -> None:
    answer = BlockingAnswerProvider()
    limits = ResearchLimits(planner_timeout_seconds=0.01, request_timeout_seconds=0.1)
    service = ResearchService(FakeSearchProvider(), answer, limits=limits)

    with pytest.raises(ResearchTimeoutError):
        await collect(service.stream(make_query(), uuid4()))


@pytest.mark.asyncio
async def test_provider_failure_becomes_typed_unavailable_error() -> None:
    search = FakeSearchProvider(error=ProviderUnavailableError("provider detail"))
    answer = FakeAnswerProvider(SearchDecision(requires_search=True, search_query="score"))
    service = ResearchService(search, answer)

    with pytest.raises(ResearchUnavailableError, match="provider unavailable"):
        await collect(service.stream(make_query(), uuid4()))


@pytest.mark.asyncio
async def test_unexpected_provider_bug_is_not_mislabeled() -> None:
    search = FakeSearchProvider(error=RuntimeError("adapter bug"))
    answer = FakeAnswerProvider(SearchDecision(requires_search=True, search_query="score"))
    service = ResearchService(search, answer)

    with pytest.raises(RuntimeError, match="adapter bug"):
        await collect(service.stream(make_query(), uuid4()))


@pytest.mark.asyncio
async def test_expired_answer_deadline_rejects_an_immediately_ready_delta() -> None:
    answer = FakeAnswerProvider(
        SearchDecision(requires_search=False),
        deltas=("first", "second"),
    )
    limits = ResearchLimits(answer_timeout_seconds=0.01, request_timeout_seconds=0.1)
    service = ResearchService(FakeSearchProvider(), answer, limits=limits)
    stream = service.stream(make_query(), uuid4())

    first = await anext(stream)
    assert isinstance(first, DeltaEvent)
    await asyncio.sleep(0.02)

    with pytest.raises(ResearchTimeoutError):
        await anext(stream)


@pytest.mark.asyncio
async def test_cancellation_propagates_without_public_error_event() -> None:
    answer = BlockingAnswerProvider()
    service = ResearchService(FakeSearchProvider(), answer)
    task = asyncio.create_task(collect(service.stream(make_query(), uuid4())))
    await answer.started.wait()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_one_aware_timestamp_is_reused_for_planning_and_answering() -> None:
    now = datetime(2026, 7, 13, 12, 30, tzinfo=UTC)
    answer = FakeAnswerProvider(SearchDecision(requires_search=False))
    service = ResearchService(FakeSearchProvider(), answer, clock=lambda: now)

    await collect(service.stream(make_query(), uuid4()))

    assert answer.decision_calls[0][1] is now
    assert answer.answer_calls[0][2] is now
    assert answer.answer_calls[0][2].utcoffset() is not None
