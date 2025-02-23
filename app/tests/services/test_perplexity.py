import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from app.services.perplexity import PerplexityService, PerplexityResponse, Citation
from langfuse.decorators import observe
from app.tests.test_quick_research import SAMPLE_PERPLEXITY_RESPONSE
from app.tests.test_quick_research_integration import requires_api_keys
import json

# Mock API responses - reuse from existing tests
MOCK_QUICK_RESEARCH_RESPONSE = SAMPLE_PERPLEXITY_RESPONSE

MOCK_ANALYZE_QUERY_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": """{
                    "raw_query": "Should I bet on the Lakers tonight?",
                    "sport_type": "basketball",
                    "is_deep_research": true,
                    "confidence_score": 0.95,
                    "required_data_sources": ["team_stats", "injuries", "odds", "h2h"],
                    "teams": {
                        "primary": "Lakers",
                        "opponent": "Warriors",
                        "normalized_names": {
                            "primary": "Los Angeles Lakers",
                            "opponent": "Golden State Warriors"
                        }
                    }
                }"""
            }
        }
    ]
}

@pytest_asyncio.fixture
async def perplexity_service():
    """Fixture for PerplexityService with mocked client"""
    service = PerplexityService()
    service.client = AsyncMock()
    service.client.__aenter__.return_value = service.client
    return service

@pytest.mark.asyncio
@observe(name="test_perplexity_quick_research")
async def test_quick_research(perplexity_service):
    """Test quick research functionality with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_QUICK_RESEARCH_RESPONSE
    mock_response.headers = {}
    perplexity_service.client.post.return_value = mock_response

    # Call the method
    response = await perplexity_service.quick_research(
        query="Should I bet on the Lakers tonight?",
        search_recency="day"
    )

    # Verify the response
    assert response.content == "Analysis of Lakers betting odds"
    assert len(response.citations) == 1
    assert response.citations[0].url == "https://example.com"

@pytest.mark.asyncio
@observe(name="test_perplexity_analyze_query")
async def test_analyze_query(perplexity_service):
    """Test query analysis functionality with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_ANALYZE_QUERY_RESPONSE
    mock_response.headers = {}
    perplexity_service.client.post.return_value = mock_response

    # Call the method
    response = await perplexity_service.analyze_query(
        query="Should I bet on the Lakers tonight?",
        search_recency="day"
    )

    # Verify the response
    assert response.raw_query == "Should I bet on the Lakers tonight?"
    assert response.sport_type == "basketball"
    assert response.is_deep_research is True

@pytest.mark.asyncio
@observe(name="test_perplexity_custom_prompt")
async def test_custom_system_prompt(perplexity_service):
    """Test quick research with custom system prompt and Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_QUICK_RESEARCH_RESPONSE
    mock_response.headers = {}
    perplexity_service.client.post.return_value = mock_response

    # Custom system prompt
    custom_prompt = "You are a conservative sports betting analyst. Focus on risks."

    # Call the method
    response = await perplexity_service.quick_research(
        query="Should I bet on the Lakers tonight?",
        system_prompt=custom_prompt
    )

    # Verify the response
    assert response.content == "Analysis of Lakers betting odds"
    assert len(response.citations) == 1

@pytest.mark.asyncio
@observe(name="test_perplexity_error_handling")
async def test_error_handling(perplexity_service):
    """Test error handling in the service with Langfuse tracing"""
    # Mock an API error response
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = Exception("API Error")
    mock_response.headers = {}
    perplexity_service.client.post.return_value = mock_response

    # Test error handling
    with pytest.raises(Exception):
        await perplexity_service.quick_research("Test query")

@pytest.mark.asyncio
@observe(name="test_perplexity_recency_filter")
async def test_search_recency_filter(perplexity_service):
    """Test different search recency filters with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_QUICK_RESEARCH_RESPONSE
    mock_response.headers = {}
    perplexity_service.client.post.return_value = mock_response

    # Test different recency values
    recency_values = ["hour", "day", "week", "month"]
    for recency in recency_values:
        response = await perplexity_service.quick_research(
            query="Test query",
            search_recency=recency
        )
        assert response.content == "Analysis of Lakers betting odds"

@pytest.mark.asyncio
@requires_api_keys
@observe(name="test_perplexity_live_api")
async def test_live_api_call():
    """Test live API call with Langfuse tracing"""
    query = "What are the odds for the Lakers next game?"

    async with PerplexityService() as service:
        response = await service.quick_research(query)
        assert response.content is not None
        assert len(response.citations) > 0 