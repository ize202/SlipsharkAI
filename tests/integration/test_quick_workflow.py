"""
Quick Workflow Test

This is a simplified version of the research workflow test that only tests
the query analyzer step, which is the first LLM call in the workflow.

This test is useful for quick verification that the workflow is functioning
without making all the external API calls.
"""

import pytest
import asyncio
from datetime import datetime

from app.models.research_models import ResearchRequest, ResearchMode
from app.workflows.research_chain import ResearchChain

# Simple test query
TEST_QUERY = "What are the odds for the Lakers game tonight?"

@pytest.fixture
def research_chain():
    """Fixture to create and return a ResearchChain instance"""
    return ResearchChain()

@pytest.mark.asyncio
async def test_query_analyzer_quick(research_chain: ResearchChain):
    """Test just the query analyzer step of the workflow for quick verification"""
    # Create a research request
    request = ResearchRequest(
        query=TEST_QUERY,
        mode=ResearchMode.QUICK
    )
    
    # Call the query analyzer directly
    start_time = datetime.utcnow()
    analysis = await research_chain._analyze_query(request)
    end_time = datetime.utcnow()
    
    # Log processing time
    processing_time = (end_time - start_time).total_seconds()
    print(f"\nQuery analysis processing time: {processing_time:.2f} seconds")
    
    # Validate analysis
    assert analysis.raw_query == TEST_QUERY, "Raw query should match input"
    assert analysis.sport_type.lower() == "basketball", "Sport type should be basketball"
    assert isinstance(analysis.confidence_score, float), "Confidence score should be a float"
    assert 0 <= analysis.confidence_score <= 1, "Confidence score should be between 0 and 1"
    assert analysis.recommended_mode == ResearchMode.QUICK, "Recommended mode should be QUICK for QUICK mode request"
    
    # Print analysis for manual inspection
    print(f"\nQuery Analysis Results:")
    print(f"Sport Type: {analysis.sport_type}")
    print(f"Teams: {analysis.teams}")
    print(f"Recommended Mode: {analysis.recommended_mode}")
    print(f"Confidence Score: {analysis.confidence_score}")
    
    return analysis

if __name__ == "__main__":
    # This allows running the test directly with python
    asyncio.run(test_query_analyzer_quick(ResearchChain())) 