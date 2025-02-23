import pytest
from unittest.mock import patch, AsyncMock
from app.services.perplexity import PerplexityService, PerplexityResponse, Citation
from langfuse.decorators import observe

# Import existing test data
from ..test_quick_research import SAMPLE_PERPLEXITY_RESPONSE
from ..test_quick_research_integration import requires_api_keys

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

@pytest.fixture
async def perplexity_service():
    """Create a PerplexityService instance with mocked client"""
    with patch("app.services.perplexity.httpx.AsyncClient") as mock_client:
        service = PerplexityService()
        service.client = AsyncMock()
        yield service

@pytest.mark.asyncio
@observe(name="test_perplexity_quick_research")
async def test_quick_research(perplexity_service):
    """Test quick research functionality with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_QUICK_RESEARCH_RESPONSE
    perplexity_service.client.post.return_value = mock_response
    
    # Call the method
    response = await perplexity_service.quick_research(
        query="Should I bet on the Lakers tonight?",
        search_recency="day"
    )
    
    # Verify the response
    assert isinstance(response, PerplexityResponse)
    assert "Lakers are favored to win" in response.content
    assert len(response.citations) == 2
    assert all(isinstance(citation, Citation) for citation in response.citations)
    assert len(response.related_questions) == 2

@pytest.mark.asyncio
@observe(name="test_perplexity_analyze_query")
async def test_analyze_query(perplexity_service):
    """Test query analysis functionality with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_ANALYZE_QUERY_RESPONSE
    perplexity_service.client.post.return_value = mock_response
    
    # Call the method
    response = await perplexity_service.analyze_query(
        query="Should I bet on the Lakers tonight?",
        search_recency="day"
    )
    
    # Parse the JSON response
    analysis = response
    assert "raw_query" in analysis
    assert analysis["sport_type"] == "basketball"
    assert analysis["is_deep_research"] is True
    assert analysis["confidence_score"] == 0.95
    assert "team_stats" in analysis["required_data_sources"]
    assert analysis["teams"]["primary"] == "Lakers"

@pytest.mark.asyncio
@observe(name="test_perplexity_custom_prompt")
async def test_custom_system_prompt(perplexity_service):
    """Test quick research with custom system prompt and Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_QUICK_RESEARCH_RESPONSE
    perplexity_service.client.post.return_value = mock_response
    
    # Custom system prompt
    custom_prompt = "You are a conservative sports betting analyst. Focus on risks."
    
    # Call the method
    response = await perplexity_service.quick_research(
        query="Should I bet on the Lakers tonight?",
        system_prompt=custom_prompt
    )
    
    # Verify the custom prompt was used
    calls = perplexity_service.client.post.call_args_list
    assert len(calls) == 1
    assert custom_prompt in str(calls[0])

@pytest.mark.asyncio
@observe(name="test_perplexity_error_handling")
async def test_error_handling(perplexity_service):
    """Test error handling in the service with Langfuse tracing"""
    # Mock an API error response
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = Exception("API Error")
    perplexity_service.client.post.return_value = mock_response
    
    # Test error handling for each method
    with pytest.raises(Exception):
        await perplexity_service.quick_research("Test query")
    
    with pytest.raises(Exception):
        await perplexity_service.analyze_query("Test query")

@pytest.mark.asyncio
@observe(name="test_perplexity_recency_filter")
async def test_search_recency_filter(perplexity_service):
    """Test different search recency filters with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_QUICK_RESEARCH_RESPONSE
    perplexity_service.client.post.return_value = mock_response
    
    # Test different recency values
    recency_values = ["hour", "day", "week", "month"]
    for recency in recency_values:
        await perplexity_service.quick_research(
            query="Test query",
            search_recency=recency
        )
        
        # Verify the recency filter was used
        calls = perplexity_service.client.post.call_args_list
        assert recency in str(calls[-1])

# Integration tests from test_quick_research_integration.py
@pytest.mark.asyncio
@requires_api_keys
@observe(name="test_perplexity_live_api")
async def test_live_api_call():
    """Test live API call with Langfuse tracing"""
    query = "What are the odds for the Lakers next game?"
    
    async with PerplexityService() as service:
        response = await service.quick_research(query)
        
        # Validate response structure
        assert response.content is not None
        assert len(response.content) > 0
        assert "Lakers" in response.content
        
        # Validate citations
        assert response.citations is not None
        if response.citations:
            for citation in response.citations:
                assert citation.url
                assert isinstance(citation.url, str)
                assert citation.url.startswith("http") 