from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictStr,
    ValidationError,
)

from slipshark.domain.models import PublicSource, SourceDocument
from slipshark.providers.protocols import ProviderTimeoutError, ProviderUnavailableError

# Raw Search API JSON nests bounded text and highlight options under `contents`.
# https://exa.ai/docs/reference/search
_EXA_SEARCH_URL = "https://api.exa.ai/search"
_DEFAULT_TOTAL_TIMEOUT_SECONDS = 10.0
_DEFAULT_CONNECT_TIMEOUT_SECONDS = 3.0
_MAX_SOURCE_TEXT_CHARS = 4_000
_MAX_SOURCE_ID_CHARS = 500
_MAX_TITLE_CHARS = 300
_MAX_SNIPPET_CHARS = 1_000


class _ExaEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    results: tuple[JsonValue, ...]


class _ExaResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: StrictStr
    title: StrictStr
    url: AnyHttpUrl
    published_date_value: JsonValue = Field(default=None, validation_alias="publishedDate")
    snippet_value: JsonValue = Field(default=None, validation_alias="snippet")
    highlights_value: JsonValue = Field(default=None, validation_alias="highlights")
    text_value: JsonValue = Field(default=None, validation_alias="text")


class ExaSearchProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        max_text_chars: int = _MAX_SOURCE_TEXT_CHARS,
        total_timeout_seconds: float = _DEFAULT_TOTAL_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = _DEFAULT_CONNECT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Exa API key must not be blank")
        if not 1 <= max_text_chars <= _MAX_SOURCE_TEXT_CHARS:
            raise ValueError("Exa text limit must be between 1 and 4000 characters")
        if total_timeout_seconds <= 0 or connect_timeout_seconds <= 0:
            raise ValueError("Exa timeouts must be positive")

        self._client = client
        self._api_key = api_key
        self._max_text_chars = max_text_chars
        self._timeout = httpx.Timeout(
            total_timeout_seconds,
            connect=connect_timeout_seconds,
        )

    async def search(self, query: str, *, limit: int) -> tuple[SourceDocument, ...]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise ValueError("Exa search query must not be blank")

        result_limit = min(max(limit, 1), 10)
        try:
            response = await self._client.post(
                _EXA_SEARCH_URL,
                headers={"x-api-key": self._api_key},
                json={
                    "query": normalized_query,
                    "numResults": result_limit,
                    "contents": {
                        "text": {"maxCharacters": self._max_text_chars},
                        "highlights": {"maxCharacters": _MAX_SNIPPET_CHARS},
                    },
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError("Exa request timed out.") from error
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            raise ProviderUnavailableError("Exa is unavailable.") from error

        try:
            envelope = _ExaEnvelope.model_validate_json(response.content)
        except ValidationError as error:
            raise ProviderUnavailableError("Exa returned an invalid response.") from error

        documents: list[SourceDocument] = []
        seen_urls: set[str] = set()
        for raw_result in envelope.results:
            try:
                result = _ExaResult.model_validate(raw_result)
                canonical_url = self._canonical_url(result.url)
                source_id = self._bounded_required(result.id, _MAX_SOURCE_ID_CHARS)
                title = self._bounded_required(result.title, _MAX_TITLE_CHARS)
            except (ValidationError, ValueError):
                continue

            canonical_key = str(canonical_url)
            if canonical_key in seen_urls:
                continue
            seen_urls.add(canonical_key)

            source = PublicSource(
                id=source_id,
                title=title,
                url=canonical_url,
                published_at=self._parse_published_at(result.published_date_value),
                snippet=self._parse_snippet(result),
            )
            documents.append(
                SourceDocument(
                    source=source,
                    text=self._parse_text(result.text_value),
                )
            )
            if len(documents) >= result_limit:
                break

        if envelope.results and not documents:
            raise ProviderUnavailableError("Exa returned an invalid response.")

        return tuple(documents)

    @staticmethod
    def _bounded_required(value: str, limit: int) -> str:
        bounded = value.strip()[:limit]
        if not bounded:
            raise ValueError("Exa result field must not be blank")
        return bounded

    def _parse_text(self, value: JsonValue) -> str:
        if not isinstance(value, str):
            return ""
        return value[: self._max_text_chars]

    @staticmethod
    def _parse_snippet(result: _ExaResult) -> str | None:
        candidates: list[JsonValue] = [result.snippet_value]
        if isinstance(result.highlights_value, list):
            candidates.extend(result.highlights_value)

        for candidate in candidates:
            if isinstance(candidate, str):
                snippet = candidate.strip()[:_MAX_SNIPPET_CHARS]
                if snippet:
                    return snippet
        return None

    @staticmethod
    def _parse_published_at(value: JsonValue) -> datetime | None:
        if not isinstance(value, str) or len(value) > 64:
            return None
        try:
            published_at = datetime.fromisoformat(value)
        except ValueError:
            return None

        if published_at.tzinfo is None or published_at.utcoffset() is None:
            return published_at.replace(tzinfo=UTC)
        return published_at

    @staticmethod
    def _canonical_url(url: AnyHttpUrl) -> AnyHttpUrl:
        parsed = urlsplit(str(url))
        return AnyHttpUrl(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")))
