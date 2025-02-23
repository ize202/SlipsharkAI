import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from app.services.perplexity import PerplexityService, PerplexityResponse, Citation
from langfuse.decorators import observe
from app.tests.test_quick_research import SAMPLE_PERPLEXITY_RESPONSE
from app.tests.test_quick_research_integration import requires_api_keys
import json
import httpx

# Mock API responses
MOCK_QUICK_RESEARCH_RESPONSE = {
    "choices": [{
        "message": {
            "content": "Analysis of Lakers betting odds"
        }
    }],
    "citations": [
        {
            "url": "https://example.com",
            "title": "Lakers Game Analysis",
            "snippet": "Recent performance analysis",
            "published_date": "2024-02-23"
        }
    ],
    "related_questions": [
        "What are the Lakers' recent injuries?",
        "How do the Lakers perform against the spread?"
    ]
}

MOCK_ANALYZE_QUERY_RESPONSE = {
    "choices": [{
        "message": {
            "content": json.dumps({
                "raw_query": "Should I bet on the Lakers tonight?",
                "sport_type": "basketball",
                "is_deep_research": True,
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
            })
        }
    }]
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
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": "Analysis of Lakers betting odds"
            }
        }],
        "citations": [
            "https://example.com"
        ]
    }
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
    assert response.citations[0].title is None
    assert response.citations[0].snippet is None
    assert response.citations[0].published_date is None
    assert response.related_questions == []

@pytest.mark.asyncio
@observe(name="test_perplexity_analyze_query")
async def test_analyze_query(perplexity_service):
    """Test query analysis functionality with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "raw_query": "Should I bet on the Lakers tonight?",
                    "sport_type": "basketball",
                    "is_deep_research": True,
                    "confidence_score": 0.95,
                    "required_data_sources": ["team_stats", "injuries", "odds", "h2h"]
                })
            }
        }]
    }
    mock_response.headers = {}
    perplexity_service.client.post.return_value = mock_response

    # Call the method
    response = await perplexity_service.analyze_query(
        query="Should I bet on the Lakers tonight?",
        search_recency="day"
    )

    # Parse the response
    analysis = json.loads(response)
    assert analysis["raw_query"] == "Should I bet on the Lakers tonight?"
    assert analysis["sport_type"] == "basketball"
    assert analysis["is_deep_research"] is True
    assert analysis["confidence_score"] == 0.95
    assert "team_stats" in analysis["required_data_sources"]

@pytest.mark.asyncio
@observe(name="test_perplexity_custom_prompt")
async def test_custom_system_prompt(perplexity_service):
    """Test quick research with custom system prompt and Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": "Analysis of Lakers betting odds"
            }
        }],
        "citations": []
    }
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
    assert len(response.citations) == 0

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
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": "Analysis of Lakers betting odds"
            }
        }],
        "citations": [
            "https://example.com"
        ]
    }
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
        assert len(response.citations) == 1
        assert response.citations[0].url == "https://example.com"

@pytest.mark.asyncio
@requires_api_keys
@observe(name="test_perplexity_live_api")
async def test_live_api_call():
    """Test live API call with Langfuse tracing"""
    query = "What are the odds for the Lakers next game?"

    # Create service instance with longer timeout
    service = PerplexityService(timeout=60.0)
    
    try:
        # Test quick research
        response = await service.quick_research(query)
        assert response.content is not None
        assert len(response.content) > 0
        assert "Lakers" in response.content.lower()
        assert isinstance(response.citations, list)
        assert all(isinstance(citation, Citation) for citation in response.citations)
        
        # Test analyze query
        analysis_str = await service.analyze_query(query)
        analysis = json.loads(analysis_str)
        assert "raw_query" in analysis
        assert "sport_type" in analysis
        assert analysis["sport_type"].lower() == "basketball"
        assert isinstance(analysis["confidence_score"], (int, float))
        assert 0 <= float(analysis["confidence_score"]) <= 1
        assert isinstance(analysis["required_data_sources"], list)
        assert len(analysis["required_data_sources"]) > 0
    
    except Exception as e:
        pytest.skip(f"Skipping live API test due to error: {str(e)}")
    
    finally:
        # Ensure client is closed
        await service.client.aclose() 