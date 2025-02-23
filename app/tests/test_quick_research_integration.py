import pytest
import os
from datetime import datetime, timedelta, UTC
from ..functions.llm_functions import quick_research, analyze_query
from ..models.betting_models import (
    QueryAnalysis,
    QuickResearchResult,
    Citation,
    SportType
)
import json
from app.services.perplexity import PerplexityService

# Skip tests if API keys are not set
requires_api_keys = pytest.mark.skipif(
    not os.getenv("PERPLEXITY_API_KEY"),
    reason="PERPLEXITY_API_KEY environment variable not set"
)

@pytest.mark.asyncio
@requires_api_keys
async def test_analyze_nba_query():
    """Test analyzing an NBA betting query"""
    query = "Should I bet on the Lakers to cover the spread against the Warriors tonight?"
    
    analysis = await analyze_query(query)
    
    assert isinstance(analysis, QueryAnalysis)
    assert analysis.sport_type == SportType.BASKETBALL
    assert "Lakers" in analysis.raw_query
    assert analysis.confidence_score > 0.5

@pytest.mark.asyncio
@requires_api_keys
async def test_quick_research_nba():
    """Test quick research for an NBA game"""
    
    # Create a sample query
    query = QueryAnalysis(
        raw_query="Should I bet on the Lakers vs Warriors game tonight?",
        sport_type=SportType.BASKETBALL,
        is_deep_research=False,
        confidence_score=0.8,
        required_data_sources=["odds", "news", "injuries"]
    )
    
    result = await quick_research(query)
    
    # Basic validation
    assert isinstance(result, QuickResearchResult)
    assert len(result.summary) > 0
    
    # Check for key information types
    content_lower = result.summary.lower()
    assert any(word in content_lower for word in ["lakers", "warriors"])
    assert any(word in content_lower for word in ["odds", "spread", "line", "points"])
    
    # Validate key points extraction
    assert len(result.key_points) > 0
    assert all(isinstance(point, str) for point in result.key_points)
    
    # Check citations
    if result.citations:
        assert all(isinstance(cite, Citation) for cite in result.citations)
        # Verify citations are recent
        for cite in result.citations:
            if cite.published_date:
                pub_date = datetime.fromisoformat(cite.published_date)
                assert datetime.now() - pub_date < timedelta(days=7)  # Should be recent
    
    # Check confidence score
    assert 0.0 <= result.confidence_score <= 1.0
    
    # Validate timestamp
    last_updated = datetime.fromisoformat(result.last_updated)
    assert datetime.now(UTC) - last_updated < timedelta(minutes=5)  # Should be very recent

@pytest.mark.asyncio
@requires_api_keys
async def test_quick_research_with_specific_question():
    """Test quick research with a specific betting question"""
    
    query = QueryAnalysis(
        raw_query="What's the over/under for the next Lakers game and how have they performed against the total?",
        sport_type=SportType.BASKETBALL,
        is_deep_research=False,
        confidence_score=0.8,
        required_data_sources=["odds", "stats"]
    )
    
    result = await quick_research(query)
    
    # Check for specific betting information
    content_lower = result.summary.lower()
    assert any(word in content_lower for word in ["over/under", "total", "points"])
    assert len(result.key_points) > 0
    
    # Should have citations for odds and stats
    if result.citations:
        urls = [cite.url.lower() for cite in result.citations]
        assert any("odds" in url or "lines" in url for url in urls)

@pytest.mark.asyncio
@requires_api_keys
async def test_quick_research_injury_news():
    """Test quick research with injury-related query"""
    query = "Are there any injuries affecting the Chiefs for their next game?"
    
    async with PerplexityService() as service:
        response = await service.quick_research(query)
        
        # Validate response content
        assert response.content is not None
        assert len(response.content) > 0
        assert "Chiefs" in response.content
        
        # Validate related questions
        assert response.related_questions is not None
        if response.related_questions:  # Might be empty if none found
            assert isinstance(response.related_questions, list)
            assert all(isinstance(q, str) for q in response.related_questions)

@pytest.mark.asyncio
@requires_api_keys
async def test_quick_research_with_recency():
    """Test quick research with different recency settings"""
    query = "What are the latest odds for the Super Bowl?"
    
    async with PerplexityService() as service:
        response = await service.quick_research(query, search_recency="hour")
        
        # Validate response
        assert response.content is not None
        assert len(response.content) > 0
        assert "Super Bowl" in response.content
        
        # Validate citations
        assert response.citations is not None
        if response.citations:
            for citation in response.citations:
                assert citation.url  # Check that URL exists and is not empty
                assert isinstance(citation.url, str)  # Verify it's a string

@pytest.mark.asyncio
async def test_quick_research_basic_query():
    """Test basic quick research functionality"""
    query = "What are the odds for the Lakers next game?"
    
    async with PerplexityService() as service:
        response = await service.quick_research(query)
        
        # Validate response structure
        assert response.content is not None
        assert len(response.content) > 0
        assert "Lakers" in response.content
        
        # Validate citations
        assert response.citations is not None
        if response.citations:  # Citations might be empty if no sources found
            for citation in response.citations:
                assert citation.url  # Check that URL exists and is not empty
                assert isinstance(citation.url, str)  # Verify it's a string
                assert citation.url.startswith("http")

@pytest.mark.asyncio
async def test_analyze_query():
    """Test query analysis functionality"""
    query = "Should I bet on the Lakers to win their next game?"
    
    async with PerplexityService() as service:
        response = await service.analyze_query(query)
        
        # Parse the JSON response
        analysis = json.loads(response)
        
        # Validate analysis structure
        assert "raw_query" in analysis
        assert "sport_type" in analysis
        assert "is_deep_research" in analysis
        assert "confidence_score" in analysis
        assert "required_data_sources" in analysis
        
        # Validate specific values
        assert analysis["raw_query"] == query
        assert analysis["sport_type"] == "basketball"
        assert isinstance(analysis["is_deep_research"], bool)
        assert 0 <= float(analysis["confidence_score"]) <= 1
        assert isinstance(analysis["required_data_sources"], list)
