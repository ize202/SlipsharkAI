import pytest
import pytest_asyncio
import os
from datetime import datetime, UTC
import logging
from typing import List, Dict, Any
from langfuse.decorators import observe

from app.models.betting_models import (
    DeepResearchResult,
    BettingInsight,
    RiskFactor,
    Citation,
    SportType,
    DataPoint
)
from app.services.perplexity import PerplexityService
from app.services.goalserve import GoalserveNBAService
from app.services.supabase import SupabaseService
from app.workflows.betting_chain import BettingResearchChain

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Skip tests if API keys are not set
requires_api_keys = pytest.mark.skipif(
    not (os.getenv("PERPLEXITY_API_KEY") and os.getenv("GOALSERVE_API_KEY")),
    reason="Required API keys not set"
)

@pytest.mark.asyncio
@requires_api_keys
@observe(name="deep_research_test")
async def test_deep_research_nba_real_integration():
    """Test the complete deep research workflow for NBA betting with real API calls"""
    
    logger.info("Starting NBA deep research integration test")
    
    # Initialize services directly (no mocks)
    chain = BettingResearchChain()
    
    # Test with a real upcoming NBA game
    query = "Should I bet on the Nuggets to cover against the Pacers on Monday? I'm particularly interested in how Jokic matches up against Turner."
    
    try:
        logger.info(f"Processing query: {query}")
        
        # Process the query through the chain
        result = await chain.process_query(query, force_deep_research=True)
        
        # Basic validation
        assert isinstance(result, DeepResearchResult), "Result should be a DeepResearchResult"
        assert len(result.summary) > 0, "Summary should not be empty"
        assert len(result.insights) > 0, "Should have at least one insight"
        assert len(result.risk_factors) > 0, "Should have at least one risk factor"
        
        # Content validation
        content_lower = result.summary.lower()
        assert any(word in content_lower for word in ["nuggets", "pacers"]), "Summary should mention relevant teams"
        
        # Validate insights
        for insight in result.insights:
            assert isinstance(insight, BettingInsight), "Each insight should be a BettingInsight"
            assert 0 <= insight.confidence <= 1, "Confidence score should be between 0 and 1"
            assert len(insight.category) > 0, "Insight category should not be empty"
            assert len(insight.insight) > 0, "Insight content should not be empty"
            assert len(insight.impact) > 0, "Impact description should not be empty"
            if insight.supporting_data:
                assert isinstance(insight.supporting_data, list), "Supporting data should be a list"
        
        # Validate risk factors
        for risk in result.risk_factors:
            assert isinstance(risk, RiskFactor), "Each risk should be a RiskFactor"
            assert risk.severity in ["low", "medium", "high"], "Risk severity should be low, medium, or high"
            assert len(risk.factor) > 0, "Risk factor should not be empty"
            if risk.mitigation:
                assert len(risk.mitigation) > 0, "Mitigation strategy should not be empty if provided"
        
        # Validate citations
        for citation in result.citations:
            assert isinstance(citation, Citation), "Each citation should be a Citation"
            assert citation.url.startswith("http"), "Citation URL should be valid"
            if citation.title:
                assert len(citation.title) > 0, "Citation title should not be empty if provided"
            if citation.snippet:
                assert len(citation.snippet) > 0, "Citation snippet should not be empty if provided"
            if citation.published_date:
                assert citation.published_date.startswith("20"), "Published date should be a valid date string"
        
        # Log results for inspection
        logger.info("\nTest Results:")
        logger.info(f"Summary: {result.summary}")
        logger.info("\nInsights:")
        for insight in result.insights:
            logger.info(f"- {insight.category}: {insight.insight} (Confidence: {insight.confidence})")
            logger.info(f"  Impact: {insight.impact}")
            if insight.supporting_data:
                logger.info(f"  Supporting Data: {', '.join(insight.supporting_data)}")
        logger.info("\nRisk Factors:")
        for risk in result.risk_factors:
            logger.info(f"- {risk.factor} (Severity: {risk.severity})")
            if risk.mitigation:
                logger.info(f"  Mitigation: {risk.mitigation}")
        logger.info("\nCitations:")
        for citation in result.citations:
            logger.info(f"- {citation.url}")
            if citation.title:
                logger.info(f"  Title: {citation.title}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}", exc_info=True)
        raise 