from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import UUID4, AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter


class Platform(StrEnum):
    MOBILE = "mobile"
    WEB = "web"


class PublicSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    url: AnyHttpUrl
    published_at: datetime | None = None
    snippet: str | None = None


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source: PublicSource
    text: str


@dataclass(frozen=True, slots=True)
class ResearchQuery:
    query: str
    platform: Platform
    max_results: int

    def __post_init__(self) -> None:
        query = self.query.strip()
        if not 1 <= len(query) <= 1000:
            raise ValueError("query must contain between 1 and 1000 characters")
        if not 1 <= self.max_results <= 10:
            raise ValueError("max_results must be between 1 and 10")
        object.__setattr__(self, "query", query)


@dataclass(frozen=True, slots=True)
class SearchDecision:
    requires_search: bool
    search_query: str | None = None

    def __post_init__(self) -> None:
        if self.search_query is None:
            normalized_query = None
        else:
            normalized_query = " ".join(self.search_query.split())
            if not normalized_query:
                raise ValueError("search_query must not be blank")
            if len(normalized_query) > 1000:
                raise ValueError("search_query must not exceed 1000 characters")

        if self.requires_search != (normalized_query is not None):
            raise ValueError("search_query must be present exactly when search is required")

        object.__setattr__(self, "search_query", normalized_query)


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID4


class DeltaEvent(_Event):
    type: Literal["delta"] = "delta"
    text: str


class SourcesEvent(_Event):
    type: Literal["sources"] = "sources"
    sources: tuple[PublicSource, ...]


class DoneEvent(_Event):
    type: Literal["done"] = "done"


class ErrorCode(StrEnum):
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INTERNAL_ERROR = "internal_error"


class ErrorEvent(_Event):
    type: Literal["error"] = "error"
    code: ErrorCode
    message: Literal["Unable to complete the research request."] = (
        "Unable to complete the research request."
    )


type StreamEvent = Annotated[
    DeltaEvent | SourcesEvent | DoneEvent | ErrorEvent,
    Field(discriminator="type"),
]

STREAM_EVENT_ADAPTER: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)
