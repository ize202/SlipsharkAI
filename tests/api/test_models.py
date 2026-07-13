import pytest
from pydantic import ValidationError

from slipshark.api.models import Platform, ResearchRequest


def test_request_trims_query_and_uses_bounded_defaults() -> None:
    request = ResearchRequest(query="  Who won the final?  ")

    assert request.query == "Who won the final?"
    assert request.platform is Platform.MOBILE
    assert request.max_results == 5


@pytest.mark.parametrize("query", ["", "  \n\t  ", "x" * 1001])
def test_request_rejects_invalid_query(query: str) -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(query=query)


@pytest.mark.parametrize("max_results", [0, 11])
def test_request_rejects_out_of_range_result_limit(max_results: int) -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(query="Latest score", max_results=max_results)


@pytest.mark.parametrize("platform", [Platform.MOBILE, Platform.WEB, "mobile", "web"])
def test_request_accepts_supported_platforms(platform: Platform | str) -> None:
    request = ResearchRequest(query="Latest score", platform=platform)

    assert request.platform.value == platform


@pytest.mark.parametrize("extra", [{"stream": False}, {"unexpected": "value"}])
def test_request_rejects_unknown_fields(extra: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(query="Latest score", **extra)
