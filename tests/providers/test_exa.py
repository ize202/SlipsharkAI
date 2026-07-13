from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from slipshark.providers.exa import ExaSearchProvider
from slipshark.providers.protocols import ProviderTimeoutError, ProviderUnavailableError


def _client(handler: httpx.AsyncBaseTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


@pytest.mark.asyncio
@pytest.mark.parametrize(("requested", "expected"), [(-5, 1), (4, 4), (99, 10)])
async def test_search_posts_once_with_auth_and_clamped_result_limit(
    requested: int,
    expected: int,
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"results": []})

    async with _client(httpx.MockTransport(handle)) as client:
        provider = ExaSearchProvider(client, api_key="test-exa-key")
        assert await provider.search("arsenal injuries", limit=requested) == ()

    [request] = requests
    assert request.method == "POST"
    assert request.url == httpx.URL("https://api.exa.ai/search")
    assert request.headers["x-api-key"] == "test-exa-key"
    payload = json.loads(request.content)
    assert payload["query"] == "arsenal injuries"
    assert payload["numResults"] == expected
    assert payload["contents"]["text"] == {"maxCharacters": 4_000}
    assert payload["contents"]["highlights"] == {"maxCharacters": 1_000}
    assert request.extensions["timeout"] == {
        "connect": 3.0,
        "read": 10.0,
        "write": 10.0,
        "pool": 10.0,
    }


@pytest.mark.asyncio
async def test_search_never_returns_more_than_the_clamped_limit() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": f"source-{index}",
                        "title": f"Source {index}",
                        "url": f"https://example.com/{index}",
                        "text": "body",
                    }
                    for index in range(12)
                ]
            },
        )

    async with _client(httpx.MockTransport(handle)) as client:
        documents = await ExaSearchProvider(client, api_key="test-key").search("query", limit=3)

    assert [document.source.id for document in documents] == [
        "source-0",
        "source-1",
        "source-2",
    ]


@pytest.mark.asyncio
async def test_search_parses_only_bounded_public_and_internal_fields() -> None:
    body = "x" * 5_000

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "source-1",
                        "title": "League report",
                        "url": "https://example.com/report",
                        "publishedDate": "2026-07-13T10:00:00Z",
                        "author": "must not cross the boundary",
                        "score": 0.98,
                        "text": body,
                        "highlights": ["Public snippet"],
                    }
                ]
            },
        )

    async with _client(httpx.MockTransport(handle)) as client:
        [document] = await ExaSearchProvider(
            client,
            api_key="test-key",
            max_text_chars=4_000,
        ).search("query", limit=5)

    assert document.text == body[:4_000]
    assert document.source.model_dump(mode="json") == {
        "id": "source-1",
        "title": "League report",
        "url": "https://example.com/report",
        "published_at": "2026-07-13T10:00:00Z",
        "snippet": "Public snippet",
    }
    assert "author" not in document.source.model_dump()
    assert "score" not in document.source.model_dump()


@pytest.mark.asyncio
async def test_search_deduplicates_normalized_urls_in_provider_order() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "first",
                        "title": "First",
                        "url": "HTTPS://EXAMPLE.COM/report#fragment",
                        "text": "first body",
                    },
                    {
                        "id": "duplicate",
                        "title": "Duplicate",
                        "url": "https://example.com/report",
                        "text": "duplicate body",
                    },
                    {
                        "id": "second",
                        "title": "Second",
                        "url": "https://example.com/other",
                        "text": "second body",
                    },
                ]
            },
        )

    async with _client(httpx.MockTransport(handle)) as client:
        documents = await ExaSearchProvider(client, api_key="test-key").search("query", limit=5)

    assert [document.source.id for document in documents] == ["first", "second"]


@pytest.mark.asyncio
async def test_malformed_results_are_skipped_without_stringifying_provider_objects() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"id": "missing-url", "title": "Bad", "text": "secret body"},
                    {"id": "bad-url", "title": "Bad", "url": "not-a-url", "text": "body"},
                    {
                        "id": "valid",
                        "title": "Valid",
                        "url": "https://example.com/valid",
                        "text": "body",
                    },
                ]
            },
        )

    async with _client(httpx.MockTransport(handle)) as client:
        documents = await ExaSearchProvider(client, api_key="test-key").search("query", limit=5)

    assert [document.source.id for document in documents] == ["valid"]


@pytest.mark.asyncio
async def test_all_malformed_results_fail_instead_of_looking_like_no_results() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [{"id": "bad", "title": "Bad", "url": "not-a-url"}]},
        )

    async with _client(httpx.MockTransport(handle)) as client:
        provider = ExaSearchProvider(client, api_key="test-key")
        with pytest.raises(ProviderUnavailableError):
            await provider.search("query", limit=5)


@pytest.mark.asyncio
async def test_malformed_response_envelope_is_unavailable() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": "private invalid payload"})

    async with _client(httpx.MockTransport(handle)) as client:
        provider = ExaSearchProvider(client, api_key="test-key")
        with pytest.raises(ProviderUnavailableError) as caught:
            await provider.search("query", limit=5)

    assert "private invalid payload" not in str(caught.value)


@pytest.mark.asyncio
async def test_malformed_optional_fields_are_sanitized_without_dropping_source() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "valid",
                        "title": "Valid",
                        "url": "https://example.com/valid",
                        "publishedDate": {"private": "invalid"},
                        "text": ["invalid"],
                        "highlights": [42, " usable snippet "],
                    }
                ]
            },
        )

    async with _client(httpx.MockTransport(handle)) as client:
        [document] = await ExaSearchProvider(client, api_key="test-key").search("query", limit=5)

    assert document.text == ""
    assert document.source.published_at is None
    assert document.source.snippet == "usable snippet"


@pytest.mark.asyncio
async def test_timeout_maps_to_stable_private_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private upstream detail", request=request)

    async with _client(httpx.MockTransport(handle)) as client:
        provider = ExaSearchProvider(client, api_key="test-key")
        with pytest.raises(ProviderTimeoutError) as caught:
            await provider.search("query", limit=5)

    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_non_success_response_maps_without_leaking_body() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="secret provider diagnostics")

    async with _client(httpx.MockTransport(handle)) as client:
        provider = ExaSearchProvider(client, api_key="test-key")
        with pytest.raises(ProviderUnavailableError) as caught:
            await provider.search("query", limit=5)

    assert "secret provider diagnostics" not in str(caught.value)


@pytest.mark.asyncio
async def test_base_request_error_maps_without_leaking_details() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.TooManyRedirects("private redirect detail", request=request)

    async with _client(httpx.MockTransport(handle)) as client:
        provider = ExaSearchProvider(client, api_key="test-key")
        with pytest.raises(ProviderUnavailableError) as caught:
            await provider.search("query", limit=5)

    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_search_cancellation_propagates() -> None:
    async def handle(_request: httpx.Request) -> httpx.Response:
        raise asyncio.CancelledError

    async with _client(httpx.MockTransport(handle)) as client:
        provider = ExaSearchProvider(client, api_key="test-key")
        with pytest.raises(asyncio.CancelledError):
            await provider.search("query", limit=5)
