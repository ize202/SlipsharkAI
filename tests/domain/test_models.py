from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from slipshark.domain.models import (
    Platform,
    PublicSource,
    ResearchQuery,
    SearchDecision,
    SourceDocument,
)


def test_internal_source_text_is_not_part_of_the_public_source() -> None:
    public = PublicSource(
        id="league-report",
        title="League report",
        url="https://example.com/report",
        published_at=datetime(2026, 7, 13, tzinfo=UTC),
        snippet="Public summary",
    )
    document = SourceDocument(source=public, text="private provider body\nwith internal detail")

    assert document.source.model_dump(mode="json") == {
        "id": "league-report",
        "title": "League report",
        "url": "https://example.com/report",
        "published_at": "2026-07-13T00:00:00Z",
        "snippet": "Public summary",
    }
    assert "private provider body" not in document.source.model_dump_json()

    with pytest.raises(FrozenInstanceError):
        document.text = "changed"


def test_research_query_normalizes_outer_whitespace() -> None:
    query = ResearchQuery(
        query="  Who won?\nInclude the score.  ",
        platform=Platform.WEB,
        max_results=7,
    )

    assert query.query == "Who won?\nInclude the score."


@pytest.mark.parametrize(
    ("query", "max_results"),
    [(" ", 5), ("x" * 1001, 5), ("valid", 0), ("valid", 11)],
)
def test_research_query_rejects_invalid_invariants(query: str, max_results: int) -> None:
    with pytest.raises(ValueError):
        ResearchQuery(query=query, platform=Platform.MOBILE, max_results=max_results)


def test_search_decision_normalizes_the_single_search_query() -> None:
    decision = SearchDecision(
        requires_search=True,
        search_query="  Arsenal   injury\nupdates  ",
    )

    assert decision.search_query == "Arsenal injury updates"


@pytest.mark.parametrize(
    ("requires_search", "search_query"),
    [(True, None), (True, "  "), (False, "scores"), (True, "x" * 1001)],
)
def test_search_decision_rejects_contradictory_or_invalid_state(
    requires_search: bool,
    search_query: str | None,
) -> None:
    with pytest.raises(ValueError):
        SearchDecision(requires_search=requires_search, search_query=search_query)
