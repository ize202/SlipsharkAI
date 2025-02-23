import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
import httpx

from ..functions.llm_functions import quick_research, analyze_query
from ..models.betting_models import (
    QueryAnalysis,
    QuickResearchResult,
    Citation,
    SportType
)
from ..services.perplexity import PerplexityResponse

# Sample test data
SAMPLE_QUERY = QueryAnalysis(
    raw_query="Should I bet on the Lakers vs Warriors game tonight?",
    sport_type=SportType.BASKETBALL,
    is_deep_research=False,
    confidence_score=0.8,
    required_data_sources=["odds", "news", "injuries"]
)

SAMPLE_PERPLEXITY_RESPONSE = {
    "choices": [{
        "message": {
            "content": """Here's my analysis of the Lakers vs Warriors game:

- Lakers are currently -3.5 point favorites
- Anthony Davis is listed as probable with ankle soreness
- Warriors have won 3 straight road games
- Recent head-to-head favors Lakers (won 2 of last 3)

The line movement suggests sharp money on Lakers, but AD's injury adds risk."""
        }
    }],
    "citations": [
        {
            "url": "https://sports.example.com/odds/lakers-warriors",
            "title": "Lakers vs Warriors Odds",
            "snippet": "Lakers -3.5 (-110), Warriors +3.5 (-110)",
            "published_date": "2024-02-23"
        },
        {
            "url": "https://sports.example.com/news/davis-injury",
            "title": "Anthony Davis Injury Update",
            "snippet": "Davis listed as probable with ankle soreness",
            "published_date": "2024-02-23"
        }
    ],
    "related_questions": [
        "What is the Lakers' record against the spread this season?",
        "How have the Warriors performed as road underdogs?"
    ]
}

@pytest.mark.asyncio
async def test_quick_research_success():
    """Test successful quick research flow"""
    
    # Mock the Perplexity service response
    mock_response = PerplexityResponse(
        content=SAMPLE_PERPLEXITY_RESPONSE["choices"][0]["message"]["content"],
        citations=SAMPLE_PERPLEXITY_RESPONSE["citations"],
        related_questions=SAMPLE_PERPLEXITY_RESPONSE["related_questions"]
    )
    
    with patch("app.services.perplexity.PerplexityService.quick_research", 
               new_callable=AsyncMock) as mock_quick_research:
        mock_quick_research.return_value = mock_response
        
        result = await quick_research(SAMPLE_QUERY)
        
        # Verify the result is a QuickResearchResult
        assert isinstance(result, QuickResearchResult)
        
        # Check key points were extracted
        assert len(result.key_points) >= 4  # We have 4 bullet points in sample
        assert any("Lakers are currently -3.5" in point for point in result.key_points)
        
        # Verify citations were processed
        assert len(result.citations) == 2
        assert isinstance(result.citations[0], Citation)
        assert result.citations[0].url == "https://sports.example.com/odds/lakers-warriors"
        
        # Check confidence score calculation
        assert 0.7 <= result.confidence_score <= 0.95
        
        # Verify timestamp format
        datetime.fromisoformat(result.last_updated)  # Should not raise error
        
        # Check related questions
        assert len(result.related_questions) == 2
        assert "Warriors performed as road underdogs" in result.related_questions[1]

@pytest.mark.asyncio
async def test_quick_research_no_citations():
    """Test quick research when no citations are returned"""
    
    # Mock response without citations
    mock_response = PerplexityResponse(
        content="Simple analysis without citations",
        citations=None,
        related_questions=None
    )
    
    with patch("app.services.perplexity.PerplexityService.quick_research", 
               new_callable=AsyncMock) as mock_quick_research:
        mock_quick_research.return_value = mock_response
        
        result = await quick_research(SAMPLE_QUERY)
        
        assert isinstance(result, QuickResearchResult)
        assert result.citations == []
        assert result.related_questions == []
        assert result.confidence_score == 0.7  # Base confidence without citations

@pytest.mark.asyncio
async def test_quick_research_http_error():
    """Test handling of HTTP errors from Perplexity API"""
    
    with patch("app.services.perplexity.PerplexityService.quick_research", 
               new_callable=AsyncMock) as mock_quick_research:
        # Simulate HTTP error
        mock_quick_research.side_effect = httpx.HTTPError("API Error")
        
        with pytest.raises(httpx.HTTPError):
            await quick_research(SAMPLE_QUERY)

@pytest.mark.asyncio
async def test_quick_research_invalid_response():
    """Test handling of invalid response format"""
    
    # Mock response with invalid format
    mock_response = PerplexityResponse(
        content="",  # Empty content
        citations=None,
        related_questions=None
    )
    
    with patch("app.services.perplexity.PerplexityService.quick_research", 
               new_callable=AsyncMock) as mock_quick_research:
        mock_quick_research.return_value = mock_response
        
        result = await quick_research(SAMPLE_QUERY)
        
        # Should still return a valid QuickResearchResult
        assert isinstance(result, QuickResearchResult)
        assert result.summary == ""
        assert len(result.key_points) == 1  # Should contain the empty content
        assert not result.deep_research_recommended  # No complexity detected

@pytest.mark.asyncio
async def test_deep_research_recommendation():
    """Test conditions that trigger deep research recommendations"""
    
    # Mock response with conditions that should trigger deep research
    mock_response = PerplexityResponse(
        content="A very long analysis " * 50,  # Long content
        citations=[{"url": "url1"}, {"url": "url2"}, {"url": "url3"}],  # Many citations
        related_questions=["Q1", "Q2", "Q3"]  # Many questions
    )
    
    with patch("app.services.perplexity.PerplexityService.quick_research", 
               new_callable=AsyncMock) as mock_quick_research:
        mock_quick_research.return_value = mock_response
        
        result = await quick_research(SAMPLE_QUERY)
        
        assert result.deep_research_recommended
        assert result.confidence_score > 0.7  # Should be boosted by citations
