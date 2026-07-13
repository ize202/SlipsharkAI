from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Protocol

from slipshark.domain.models import ResearchQuery, SearchDecision, SourceDocument


class ProviderTimeoutError(Exception):
    pass


class ProviderUnavailableError(Exception):
    pass


class SearchProvider(Protocol):
    async def search(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]: ...


class AnswerProvider(Protocol):
    async def decide_search(
        self,
        query: ResearchQuery,
        *,
        now: datetime,
    ) -> SearchDecision: ...

    def stream_answer(
        self,
        query: ResearchQuery,
        *,
        sources: Sequence[SourceDocument],
        now: datetime,
    ) -> AsyncIterator[str]: ...
