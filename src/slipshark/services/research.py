import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, TypeVar, runtime_checkable
from uuid import UUID

from slipshark.domain.models import (
    DeltaEvent,
    DoneEvent,
    ResearchQuery,
    SourceDocument,
    SourcesEvent,
    StreamEvent,
)
from slipshark.providers.protocols import (
    AnswerProvider,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SearchProvider,
)

_Result = TypeVar("_Result")


class ResearchTimeoutError(Exception):
    pass


class ResearchUnavailableError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ResearchLimits:
    planner_timeout_seconds: float = 10
    search_timeout_seconds: float = 10
    answer_timeout_seconds: float = 30
    request_timeout_seconds: float = 45
    per_source_char_limit: int = 4_000
    total_source_char_limit: int = 16_000
    answer_char_limit: int = 12_000

    def __post_init__(self) -> None:
        values = (
            self.planner_timeout_seconds,
            self.search_timeout_seconds,
            self.answer_timeout_seconds,
            self.request_timeout_seconds,
            self.per_source_char_limit,
            self.total_source_char_limit,
            self.answer_char_limit,
        )
        if any(value <= 0 for value in values):
            raise ValueError("research limits must be positive")
        if self.per_source_char_limit > self.total_source_char_limit:
            raise ValueError("per-source limit cannot exceed the total source limit")


@runtime_checkable
class _ClosableAsyncIterator(Protocol):
    async def aclose(self) -> None: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ResearchService:
    def __init__(
        self,
        search_provider: SearchProvider,
        answer_provider: AnswerProvider,
        *,
        clock: Callable[[], datetime] = _utc_now,
        limits: ResearchLimits | None = None,
    ) -> None:
        self._search_provider = search_provider
        self._answer_provider = answer_provider
        self._clock = clock
        self._limits = limits if limits is not None else ResearchLimits()

    async def stream(
        self,
        query: ResearchQuery,
        request_id: UUID,
    ) -> AsyncIterator[StreamEvent]:
        loop = asyncio.get_running_loop()
        request_deadline = loop.time() + self._limits.request_timeout_seconds
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("research clock must return a timezone-aware datetime")

        decision = await self._await_provider(
            lambda: self._answer_provider.decide_search(query, now=now),
            deadline=min(
                loop.time() + self._limits.planner_timeout_seconds,
                request_deadline,
            ),
        )

        sources: tuple[SourceDocument, ...] = ()
        if decision.requires_search:
            search_query = decision.search_query
            if search_query is None:
                raise ValueError("search decision is missing its query")
            sources = await self._await_provider(
                lambda: self._search_provider.search(
                    search_query,
                    limit=query.max_results,
                ),
                deadline=min(
                    loop.time() + self._limits.search_timeout_seconds,
                    request_deadline,
                ),
            )

        bounded_sources = self._bound_sources(sources)
        answer_stream = self._start_answer_stream(query, bounded_sources, now)
        answer_deadline = min(
            loop.time() + self._limits.answer_timeout_seconds,
            request_deadline,
        )
        emitted_characters = 0

        try:
            while emitted_characters < self._limits.answer_char_limit:
                try:
                    self._raise_if_expired(loop.time(), answer_deadline)
                    async with asyncio.timeout_at(answer_deadline):
                        chunk = await anext(answer_stream)
                except StopAsyncIteration:
                    break
                except (TimeoutError, ProviderTimeoutError) as error:
                    raise ResearchTimeoutError("research provider timed out") from error
                except ProviderUnavailableError as error:
                    raise ResearchUnavailableError("research provider unavailable") from error

                if not chunk:
                    continue
                remaining = self._limits.answer_char_limit - emitted_characters
                delta = chunk[:remaining]
                emitted_characters += len(delta)
                if delta:
                    yield DeltaEvent(request_id=request_id, text=delta)
        finally:
            if isinstance(answer_stream, _ClosableAsyncIterator):
                await answer_stream.aclose()

        self._raise_if_expired(loop.time(), request_deadline)
        yield SourcesEvent(
            request_id=request_id,
            sources=tuple(document.source for document in sources),
        )
        self._raise_if_expired(loop.time(), request_deadline)
        yield DoneEvent(request_id=request_id)

    async def _await_provider(
        self,
        operation: Callable[[], Awaitable[_Result]],
        *,
        deadline: float,
    ) -> _Result:
        try:
            self._raise_if_expired(asyncio.get_running_loop().time(), deadline)
            async with asyncio.timeout_at(deadline):
                return await operation()
        except (TimeoutError, ProviderTimeoutError) as error:
            raise ResearchTimeoutError("research provider timed out") from error
        except ProviderUnavailableError as error:
            raise ResearchUnavailableError("research provider unavailable") from error

    def _start_answer_stream(
        self,
        query: ResearchQuery,
        sources: tuple[SourceDocument, ...],
        now: datetime,
    ) -> AsyncIterator[str]:
        try:
            return self._answer_provider.stream_answer(query, sources=sources, now=now)
        except (TimeoutError, ProviderTimeoutError) as error:
            raise ResearchTimeoutError("research provider timed out") from error
        except ProviderUnavailableError as error:
            raise ResearchUnavailableError("research provider unavailable") from error

    def _bound_sources(
        self,
        sources: tuple[SourceDocument, ...],
    ) -> tuple[SourceDocument, ...]:
        remaining = self._limits.total_source_char_limit
        bounded: list[SourceDocument] = []

        for document in sources:
            char_limit = min(self._limits.per_source_char_limit, remaining)
            text = document.text[:char_limit]
            bounded.append(SourceDocument(source=document.source, text=text))
            remaining -= len(text)

        return tuple(bounded)

    @staticmethod
    def _raise_if_expired(now: float, deadline: float) -> None:
        if now >= deadline:
            raise ResearchTimeoutError("research provider timed out")
