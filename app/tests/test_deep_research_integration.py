import pytest
import pytest_asyncio
import os
from datetime import datetime, timedelta, UTC
import json
import asyncio
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch
from ..functions.llm_functions import analyze_query, deep_research
from ..models.betting_models import (
    QueryAnalysis,
    DeepResearchResult,
    BettingInsight,
    RiskFactor,
    Citation,
    SportType,
    DataPoint,
    PerplexityResponse,
    QuickResearchResult
)
from app.services.perplexity import PerplexityService
from app.services.goalserve import GoalserveNBAService
from app.services.supabase import SupabaseService

# Mock data for testing
MOCK_TEAM_STATS = {
    "team_id": "1066",
    "name": "Los Angeles Lakers",
    "wins": 25,
    "losses": 15,
    "win_percentage": 0.625,
    "points_per_game": 115.5,
    "points_allowed": 108.5,
    "last_ten": "7-3",
    "streak": "W4",
    "home_record": "15-5",
    "away_record": "10-10",
    "conference_rank": 4
}

MOCK_PLAYER_STATS = [{
    "player_id": "12345",
    "name": "LeBron James",
    "position": "F",
    "games_played": 35,
    "points_per_game": 25.5,
    "rebounds_per_game": 7.5,
    "assists_per_game": 8.0,
    "minutes_per_game": 34.5,
    "status": "Questionable",
    "injury_details": "Left ankle soreness"
}]

MOCK_ODDS = {
    "game_id": "12345",
    "home_team": "Los Angeles Lakers",
    "away_team": "Golden State Warriors",
    "spread": -5.5,
    "home_odds": -110,
    "away_odds": -110,
    "total": 235.5,
    "over_odds": -110,
    "under_odds": -110,
    "last_updated": datetime.now(UTC).isoformat()
}

MOCK_USER_HISTORY = {
    "user_id": "test_user_123",
    "betting_history": [
        {
            "bet_type": "spread",
            "team": "Los Angeles Lakers",
            "odds": -110,
            "result": "win",
            "stake": 100,
            "profit_loss": 90.91,
            "date": (datetime.now(UTC) - timedelta(days=5)).isoformat()
        }
    ],
    "user_stats": {
        "total_bets": 50,
        "win_rate": 0.54,
        "roi": 0.05,
        "favorite_teams": ["Los Angeles Lakers", "Golden State Warriors"],
        "preferred_bet_types": ["spread", "moneyline"]
    }
}

# Skip tests if API keys are not set
requires_api_keys = pytest.mark.skipif(
    not (os.getenv("PERPLEXITY_API_KEY") and os.getenv("GOALSERVE_API_KEY")),
    reason="Required API keys not set"
)

@pytest_asyncio.fixture
async def mock_services():
    """Fixture for mocking all required services"""
    
    # Mock Perplexity service
    perplexity = AsyncMock(spec=PerplexityService)
    perplexity.quick_research.return_value = PerplexityResponse(
        content="The Lakers are favored by 5.5 points against the Warriors. LeBron James is questionable with an ankle injury.",
        citations=[Citation(url="https://example.com/odds")],
        related_questions=["How do the Lakers perform ATS at home?"]
    )
    
    # Mock Goalserve service
    goalserve = AsyncMock(spec=GoalserveNBAService)
    goalserve.get_team_stats.return_value = MOCK_TEAM_STATS
    goalserve.get_player_stats.return_value = MOCK_PLAYER_STATS
    goalserve.get_odds_comparison.return_value = MOCK_ODDS
    
    # Mock Supabase service
    supabase = AsyncMock(spec=SupabaseService)
    supabase.get_bet_history.return_value = MOCK_USER_HISTORY["betting_history"]
    supabase.get_user_stats.return_value = MOCK_USER_HISTORY["user_stats"]
    
    # Create patch context managers
    perplexity_patch = patch("app.services.perplexity.PerplexityService", return_value=perplexity)
    goalserve_patch = patch("app.services.goalserve.GoalserveNBAService", return_value=goalserve)
    supabase_patch = patch("app.services.supabase.SupabaseService", return_value=supabase)
    
    # Start patches
    perplexity_mock = perplexity_patch.start()
    goalserve_mock = goalserve_patch.start()
    supabase_mock = supabase_patch.start()
    
    yield {
        "perplexity": perplexity,
        "goalserve": goalserve,
        "supabase": supabase
    }
    
    # Stop patches
    perplexity_patch.stop()
    goalserve_patch.stop()
    supabase_patch.stop()

@pytest.mark.asyncio
@requires_api_keys
async def test_deep_research_nba_full_flow(mock_services):
    """Test the complete deep research workflow for NBA betting"""
    
    # Step 1: Create and analyze query
    query = "Should I bet on the Lakers to cover -5.5 against the Warriors tonight? LeBron's status is questionable."
    
    # Mock analyze_query response
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,
            confidence_score=0.85,
            required_data_sources=["team_stats", "injuries", "odds", "news"],
            bet_type="spread"
        )
        analysis = await analyze_query(query)
    
    assert isinstance(analysis, QueryAnalysis)
    assert analysis.sport_type == SportType.BASKETBALL
    assert analysis.is_deep_research
    assert "Lakers" in analysis.raw_query
    assert analysis.confidence_score > 0.5
    
    # Step 2: Perform deep research
    result = await deep_research(analysis)
    
    # Basic validation
    assert isinstance(result, DeepResearchResult)
    assert len(result.summary) > 0
    assert len(result.insights) > 0
    assert len(result.risk_factors) > 0
    
    # Content validation
    content_lower = result.summary.lower()
    assert any(word in content_lower for word in ["lakers", "warriors"])
    assert any(word in content_lower for word in ["spread", "cover", "-5.5"])
    assert any(word in content_lower for word in ["lebron", "status", "questionable"])
    
    # Insights validation
    assert all(isinstance(insight, BettingInsight) for insight in result.insights)
    assert any("injury" in insight.description.lower() for insight in result.insights)
    assert any("spread" in insight.description.lower() for insight in result.insights)
    
    # Risk factors validation
    assert all(isinstance(risk, RiskFactor) for risk in result.risk_factors)
    assert any("injury" in risk.description.lower() for risk in result.risk_factors)
    
    # Odds analysis validation
    assert isinstance(result.odds_analysis, dict)
    assert "spread" in result.odds_analysis
    assert "line_movement" in result.odds_analysis
    
    # Citations validation
    assert len(result.citations) > 0
    assert all(isinstance(cite, Citation) for cite in result.citations)
    
    # Verify citations are recent
    for cite in result.citations:
        if cite.published_date:
            pub_date = datetime.fromisoformat(cite.published_date)
            assert datetime.now() - pub_date < timedelta(days=7)
    
    # Confidence score validation
    assert 0.0 <= result.confidence_score <= 1.0
    
    # Timestamp validation
    last_updated = datetime.fromisoformat(result.last_updated)
    assert datetime.now(UTC) - last_updated < timedelta(minutes=5)
    
    # Verify service calls
    mock_services["perplexity"].quick_research.assert_called_once()
    mock_services["goalserve"].get_team_stats.assert_called_once()
    mock_services["goalserve"].get_player_stats.assert_called_once()
    mock_services["goalserve"].get_odds_comparison.assert_called_once()

@pytest.mark.asyncio
@requires_api_keys
async def test_deep_research_with_user_history(mock_services):
    """Test deep research incorporating user betting history"""
    
    # Create test user ID
    test_user_id = "test_user_123"
    
    # Step 1: Analyze query
    query = "Should I bet on the Lakers money line? I've been tracking their home games."
    
    # Mock analyze_query response
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,
            confidence_score=0.85,
            required_data_sources=["team_stats", "odds", "user_history"],
            bet_type="moneyline",
            user_id=test_user_id
        )
        analysis = await analyze_query(query)
    
    # Step 2: Perform deep research
    result = await deep_research(analysis)
    
    # Validate user-specific insights
    assert "betting_history" in result.metadata
    assert "user_stats" in result.metadata
    
    # Validate personalized recommendations
    history_insights = [
        insight for insight in result.insights 
        if "historical" in insight.description.lower() or 
           "previous" in insight.description.lower()
    ]
    assert len(history_insights) > 0
    
    # Verify service calls
    mock_services["supabase"].get_bet_history.assert_called_once_with(
        user_id=test_user_id,
        days_back=30
    )
    mock_services["supabase"].get_user_stats.assert_called_once_with(
        user_id=test_user_id
    )

@pytest.mark.asyncio
@requires_api_keys
async def test_deep_research_error_handling(mock_services):
    """Test error handling in deep research workflow"""
    
    # Test with invalid team name
    query = "Should I bet on the Invalid Team tonight?"
    
    # Mock analyze_query response
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,
            confidence_score=0.85,
            required_data_sources=["team_stats", "odds"],
            bet_type="moneyline"
        )
        analysis = await analyze_query(query)
    
    # Mock service error
    mock_services["goalserve"].get_team_stats.side_effect = ValueError("Invalid team name")
    
    try:
        await deep_research(analysis)
        pytest.fail("Should have raised an error for invalid team")
    except ValueError as e:
        assert "team name" in str(e).lower()
    
    # Test with missing required data
    analysis.required_data_sources = ["nonexistent_source"]
    try:
        await deep_research(analysis)
        pytest.fail("Should have raised an error for missing data source")
    except ValueError as e:
        assert "data source" in str(e).lower()

@pytest.mark.asyncio
@requires_api_keys
async def test_deep_research_data_freshness(mock_services):
    """Test that deep research uses fresh data"""
    
    query = "What's the best bet for tonight's Lakers game?"
    
    # Mock analyze_query response
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,
            confidence_score=0.85,
            required_data_sources=["team_stats", "odds"],
            bet_type="any"
        )
        analysis = await analyze_query(query)
    
    # First research
    result1 = await deep_research(analysis)
    
    # Update mock data
    mock_services["goalserve"].get_odds_comparison.return_value = {
        **MOCK_ODDS,
        "spread": -6.0,  # Line movement
        "last_updated": datetime.now(UTC).isoformat()
    }
    
    # Second research
    result2 = await deep_research(analysis)
    
    # Timestamps should be different
    time1 = datetime.fromisoformat(result1.last_updated)
    time2 = datetime.fromisoformat(result2.last_updated)
    assert time2 > time1
    
    # Data should be fresh
    assert result1.odds_analysis != result2.odds_analysis

@pytest.mark.asyncio
@requires_api_keys
async def test_deep_research_parallel_data_gathering(mock_services):
    """Test that data gathering happens in parallel"""
    
    start_time = datetime.now()
    
    query = "Should I bet on the Lakers vs Warriors game tonight?"
    
    # Mock analyze_query response
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,
            confidence_score=0.85,
            required_data_sources=["team_stats", "odds", "injuries", "news"],
            bet_type="any"
        )
        analysis = await analyze_query(query)
    
    # Add delay to mock service calls
    async def delayed_response(*args, **kwargs):
        await asyncio.sleep(1)
        return MOCK_TEAM_STATS
    
    mock_services["goalserve"].get_team_stats.side_effect = delayed_response
    mock_services["goalserve"].get_player_stats.side_effect = delayed_response
    mock_services["goalserve"].get_odds_comparison.side_effect = delayed_response
    
    result = await deep_research(analysis)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # If data gathering is parallel, this should complete in under 2 seconds
    # (Each mock call takes 1 second, but they run in parallel)
    assert duration < 2.0
    
    # Verify we got data from all sources
    assert len(result.citations) >= 3  # Should have multiple sources
    assert "team_stats" in result.metadata
    assert "odds" in result.metadata
    assert "injuries" in result.metadata 

@pytest.mark.asyncio
async def test_betting_chain_orchestration(mock_services):
    """Test the BettingResearchChain class that orchestrates the workflow"""
    from app.workflows.betting_chain import BettingResearchChain
    
    # Initialize the chain
    chain = BettingResearchChain()
    
    # Test quick research path
    quick_query = "What's the moneyline for the Lakers game tonight?"
    
    # Mock analyze_query to return quick research
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=quick_query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=False,
            confidence_score=0.85,
            required_data_sources=["odds", "news"],
            bet_type="moneyline"
        )
        
        # Process quick research query
        result = await chain.process_query(quick_query)
        
        # Verify it's a QuickResearchResult
        assert isinstance(result, QuickResearchResult)
        assert not result.deep_research_recommended
        
        # Verify only Perplexity service was called
        mock_services["perplexity"].quick_research.assert_called_once()
        mock_services["goalserve"].get_team_stats.assert_not_called()
        mock_services["supabase"].get_bet_history.assert_not_called()
    
    # Test deep research path
    deep_query = "Should I bet on the Lakers -5.5 vs Warriors? Need comprehensive analysis."
    
    # Reset mock calls
    mock_services["perplexity"].quick_research.reset_mock()
    
    # Mock analyze_query to return deep research
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=deep_query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,
            confidence_score=0.9,
            required_data_sources=["team_stats", "odds", "injuries", "news"],
            bet_type="spread"
        )
        
        # Process deep research query
        result = await chain.process_query(deep_query)
        
        # Verify it's a DeepResearchResult
        assert isinstance(result, DeepResearchResult)
        assert len(result.insights) > 0
        assert len(result.risk_factors) > 0
        
        # Verify all services were called
        mock_services["perplexity"].quick_research.assert_called_once()
        mock_services["goalserve"].get_team_stats.assert_called_once()
        mock_services["goalserve"].get_player_stats.assert_called_once()
        mock_services["goalserve"].get_odds_comparison.assert_called_once()
    
    # Test extending quick research to deep research
    quick_result = QuickResearchResult(
        summary="Lakers are -5.5 favorites",
        key_points=["Line opened at -4.5", "Heavy betting on Lakers"],
        confidence_score=0.8,
        deep_research_recommended=True,
        citations=[Citation(url="https://example.com/odds")],
        related_questions=["How do Lakers perform ATS?"],
        last_updated=datetime.now(UTC).isoformat()
    )
    
    # Reset mock calls
    mock_services["perplexity"].quick_research.reset_mock()
    mock_services["goalserve"].get_team_stats.reset_mock()
    
    # Mock analyze_query for extension
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=deep_query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,  # Force deep research
            confidence_score=0.9,
            required_data_sources=["team_stats", "odds", "injuries", "news"],
            bet_type="spread"
        )
        
        # Extend the research
        result = await chain.extend_research(quick_result, deep_query)
        
        # Verify it's a DeepResearchResult
        assert isinstance(result, DeepResearchResult)
        assert len(result.insights) > 0
        assert len(result.risk_factors) > 0
        
        # Verify all services were called
        mock_services["perplexity"].quick_research.assert_called_once()
        mock_services["goalserve"].get_team_stats.assert_called_once()
        mock_services["goalserve"].get_player_stats.assert_called_once()
        mock_services["goalserve"].get_odds_comparison.assert_called_once()
        
        # Verify the deep research incorporated quick research insights
        summary_lower = result.summary.lower()
        assert "opened at -4.5" in summary_lower  # Info from quick result
        assert "heavy betting" in summary_lower  # Info from quick result 

@pytest.mark.asyncio
async def test_api_endpoints(mock_services):
    """Test the API endpoints that use the betting chain"""
    from fastapi.testclient import TestClient
    from app.api import app, QueryRequest, ExtendResearchRequest
    
    client = TestClient(app)
    
    # Test analyze endpoint with quick research
    quick_query = QueryRequest(
        query="What's the moneyline for the Lakers game tonight?",
        force_deep_research=False
    )
    
    # Mock analyze_query to return quick research
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=quick_query.query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=False,
            confidence_score=0.85,
            required_data_sources=["odds", "news"],
            bet_type="moneyline"
        )
        
        response = client.post("/analyze", json=quick_query.model_dump())
        assert response.status_code == 200
        
        result = response.json()
        assert "summary" in result
        assert "key_points" in result
        assert "confidence_score" in result
        assert "deep_research_recommended" in result
        
        # Verify only Perplexity service was called
        mock_services["perplexity"].quick_research.assert_called_once()
        mock_services["goalserve"].get_team_stats.assert_not_called()
    
    # Test analyze endpoint with forced deep research
    deep_query = QueryRequest(
        query="Should I bet on the Lakers -5.5 vs Warriors? Need comprehensive analysis.",
        force_deep_research=True
    )
    
    # Reset mock calls
    mock_services["perplexity"].quick_research.reset_mock()
    
    # Mock analyze_query to return deep research
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=deep_query.query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,
            confidence_score=0.9,
            required_data_sources=["team_stats", "odds", "injuries", "news"],
            bet_type="spread"
        )
        
        response = client.post("/analyze", json=deep_query.model_dump())
        assert response.status_code == 200
        
        result = response.json()
        assert "summary" in result
        assert "insights" in result
        assert "risk_factors" in result
        assert "odds_analysis" in result
        
        # Verify all services were called
        mock_services["perplexity"].quick_research.assert_called_once()
        mock_services["goalserve"].get_team_stats.assert_called_once()
        mock_services["goalserve"].get_odds_comparison.assert_called_once()
    
    # Test extend endpoint
    quick_result = QuickResearchResult(
        summary="Lakers are -5.5 favorites",
        key_points=["Line opened at -4.5", "Heavy betting on Lakers"],
        confidence_score=0.8,
        deep_research_recommended=True,
        citations=[{"url": "https://example.com/odds"}],
        related_questions=["How do Lakers perform ATS?"],
        last_updated=datetime.now(UTC).isoformat()
    )
    
    extend_request = ExtendResearchRequest(
        original_query="Should I bet on the Lakers spread?",
        quick_result=quick_result
    )
    
    # Reset mock calls
    mock_services["perplexity"].quick_research.reset_mock()
    mock_services["goalserve"].get_team_stats.reset_mock()
    
    # Mock analyze_query for extension
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.return_value = QueryAnalysis(
            raw_query=extend_request.original_query,
            sport_type=SportType.BASKETBALL,
            is_deep_research=True,
            confidence_score=0.9,
            required_data_sources=["team_stats", "odds", "injuries", "news"],
            bet_type="spread"
        )
        
        response = client.post("/extend", json=extend_request.model_dump())
        assert response.status_code == 200
        
        result = response.json()
        assert "summary" in result
        assert "insights" in result
        assert "risk_factors" in result
        assert "odds_analysis" in result
        
        # Verify all services were called
        mock_services["perplexity"].quick_research.assert_called_once()
        mock_services["goalserve"].get_team_stats.assert_called_once()
        mock_services["goalserve"].get_odds_comparison.assert_called_once()
    
    # Test error handling
    error_query = QueryRequest(
        query="Invalid query that will cause an error",
        force_deep_research=False
    )
    
    # Mock analyze_query to raise an error
    with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
        mock_analyze.side_effect = ValueError("Invalid query")
        
        response = client.post("/analyze", json=error_query.model_dump())
        assert response.status_code == 500
        assert "Invalid query" in response.json()["detail"] 

@pytest.mark.asyncio
async def test_langfuse_observability(mock_services):
    """Test that Langfuse observability is working correctly"""
    from langfuse import Langfuse
    from app.workflows.betting_chain import BettingResearchChain
    
    # Initialize Langfuse client
    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "test"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", "test"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    )
    
    # Initialize the chain
    chain = BettingResearchChain()
    
    # Create a trace
    with langfuse.trace("deep_research_test") as trace:
        # Process a deep research query
        query = "Should I bet on the Lakers -5.5 vs Warriors? Need comprehensive analysis."
        
        # Mock analyze_query to return deep research
        with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
            mock_analyze.return_value = QueryAnalysis(
                raw_query=query,
                sport_type=SportType.BASKETBALL,
                is_deep_research=True,
                confidence_score=0.9,
                required_data_sources=["team_stats", "odds", "injuries", "news"],
                bet_type="spread"
            )
            
            # Process the query
            with trace.span("process_query"):
                result = await chain.process_query(query, force_deep_research=True)
            
            # Verify the result
            assert isinstance(result, DeepResearchResult)
            
            # Log metrics
            trace.metrics({
                "confidence_score": result.confidence_score,
                "num_insights": len(result.insights),
                "num_risk_factors": len(result.risk_factors),
                "num_citations": len(result.citations),
                "response_time_ms": trace.current_span.end_time - trace.current_span.start_time
            })
            
            # Log the final result
            trace.log({
                "level": "info",
                "name": "deep_research_result",
                "result": result.model_dump()
            })
            
            # Verify service spans were created
            assert any(span.name == "perplexity_quick_research" for span in trace.spans)
            assert any(span.name == "goalserve_get_team_stats" for span in trace.spans)
            assert any(span.name == "goalserve_get_odds" for span in trace.spans)
            
            # Verify service calls
            mock_services["perplexity"].quick_research.assert_called_once()
            mock_services["goalserve"].get_team_stats.assert_called_once()
            mock_services["goalserve"].get_odds_comparison.assert_called_once()
    
    # Test error tracing
    with langfuse.trace("error_test") as trace:
        # Mock analyze_query to raise an error
        with patch("app.functions.llm_functions.analyze_query") as mock_analyze:
            mock_analyze.side_effect = ValueError("Invalid query")
            
            try:
                with trace.span("process_query"):
                    await chain.process_query("Invalid query")
            except ValueError as e:
                # Log the error
                trace.log({
                    "level": "error",
                    "name": "query_error",
                    "error": str(e)
                })
                
                # Verify error was logged
                assert any(log.level == "error" for log in trace.logs)
                assert any("Invalid query" in log.body for log in trace.logs) 