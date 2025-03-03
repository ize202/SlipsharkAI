import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from app.services.basketball_service import BasketballService
from app.models.research_models import (
    ClientMetadata,
    ResearchRequest,
    QueryAnalysis,
    DataPoint,
    ResearchMode,
    ConversationContext
)
from app.workflows.research_chain import ResearchChain
from app.config import get_logger

logger = get_logger(__name__)

# Test client metadata matching production
TEST_CLIENT_METADATA = ClientMetadata(
    timestamp="2025-03-03",
    timezone="America/New_York",
    locale="en-US"
)

async def validate_data_points(data_points: List[DataPoint]) -> bool:
    """Validate gathered data points"""
    if not data_points:
        logger.error("No data points returned")
        return False
        
    basketball_data = [dp for dp in data_points if dp.source == "basketball_api"]
    if not basketball_data:
        logger.error("No basketball API data points found")
        return False
        
    for dp in basketball_data:
        if isinstance(dp.content, dict) and "error" in dp.content:
            logger.error(f"Error in basketball data: {dp.content['error']}")
            return False
            
    return True

async def run_research_test(
    research_chain: ResearchChain,
    description: str,
    query: str,
    teams: Dict[str, str],
    players: List[str],
    game_date: Optional[str],
    expected_success: bool = True
) -> None:
    """Run a research chain test"""
    logger.info(f"\nTesting: {description}")
    
    try:
        # Create analysis object similar to what the LLM would produce
        analysis = QueryAnalysis(
            raw_query=query,
            teams=teams,
            players=players,
            game_date=game_date,
            recommended_mode=ResearchMode.DEEP,
            sport_type="basketball",
            query_type="game_info",
            confidence_score=0.9
        )
        
        # Create research request
        request = ResearchRequest(
            query=query,
            mode=ResearchMode.DEEP,
            client_metadata=TEST_CLIENT_METADATA,
            context=ConversationContext()
        )
        
        # Gather data using the research chain
        data_points = await research_chain._gather_data(analysis, request)
        
        # Validate results
        is_valid = await validate_data_points(data_points)
        assert is_valid == expected_success, f"Validation failed for: {description}"
        
        if is_valid:
            basketball_data = [dp for dp in data_points if dp.source == "basketball_api"]
            logger.info(f"Found {len(basketball_data)} basketball data points for query: {description}")
            
    except Exception as e:
        logger.error(f"Error testing {description}: {str(e)}")
        if expected_success:
            raise

@pytest.mark.asyncio
async def test_single_day_queries():
    """Test queries for single day references"""
    async with ResearchChain() as research_chain:
        # Test cases for single day queries
        test_cases = [
            (
                "Lakers games tonight",
                "Show me Lakers games tonight",
                {"team1": "Lakers"},
                [],
                "tonight"
            ),
            (
                "Celtics games yesterday",
                "How did the Celtics play yesterday",
                {"team1": "Celtics"},
                [],
                "yesterday"
            ),
            (
                "Nuggets games this Friday",
                "Show me Nuggets games this Friday",
                {"team1": "Nuggets"},
                [],
                "this Friday"
            ),
            (
                "Suns game last Wednesday",
                "Get me stats from last Wednesday's Suns game",
                {"team1": "Suns"},
                [],
                "last Wednesday"
            ),
            (
                "Lakers performance from 3 days ago",
                "Show me Lakers performance from 3 days ago",
                {"team1": "Lakers"},
                [],
                "3 days ago"
            )
        ]
        
        for description, query, teams, players, date_ref in test_cases:
            await run_research_test(research_chain, description, query, teams, players, date_ref)

@pytest.mark.asyncio
async def test_range_queries():
    """Test queries for date ranges"""
    async with ResearchChain() as research_chain:
        # Test cases for range queries
        test_cases = [
            (
                "Lakers games this week",
                "Show me Lakers games this week",
                {"team1": "Lakers"},
                [],
                "this week"
            ),
            (
                "Nets performance last week",
                "How did the Nets perform last week",
                {"team1": "Nets"},
                [],
                "last week"
            ),
            (
                "Warriors weekend games",
                "What games are on this weekend",
                {"team1": "Warriors"},
                [],
                "this weekend"
            ),
            (
                "Warriors last weekend",
                "How did the Warriors do last weekend",
                {"team1": "Warriors"},
                [],
                "last weekend"
            )
        ]
        
        for description, query, teams, players, date_ref in test_cases:
            await run_research_test(research_chain, description, query, teams, players, date_ref)

@pytest.mark.asyncio
async def test_comparative_queries():
    """Test comparative queries between teams"""
    async with ResearchChain() as research_chain:
        # Test cases for comparative queries
        test_cases = [
            (
                "Bucks vs Celtics next week",
                "Compare Bucks vs Celtics stats for next week",
                {"team1": "Bucks", "team2": "Celtics"},
                [],
                "next week"
            ),
            (
                "Nuggets vs Suns future",
                "Compare Nuggets vs Suns stats 2 weeks from now",
                {"team1": "Nuggets", "team2": "Suns"},
                [],
                "in 2 weeks"
            ),
            (
                "Lakers comparison",
                "Compare Lakers performance tonight vs last week",
                {"team1": "Lakers"},
                [],
                "tonight"
            )
        ]
        
        for description, query, teams, players, date_ref in test_cases:
            await run_research_test(research_chain, description, query, teams, players, date_ref)

@pytest.mark.asyncio
async def test_forward_looking_queries():
    """Test queries for future games"""
    async with ResearchChain() as research_chain:
        # Test cases for future queries
        test_cases = [
            (
                "Upcoming Lakers games",
                "Show me upcoming Lakers games",
                {"team1": "Lakers"},
                [],
                "upcoming"
            ),
            (
                "Next Warriors games",
                "What are the next Warriors games",
                {"team1": "Warriors"},
                [],
                "next"
            ),
            (
                "Warriors next Friday",
                "Show me Warriors stats from yesterday and predictions for next Friday",
                {"team1": "Warriors"},
                [],
                "next Friday"
            )
        ]
        
        for description, query, teams, players, date_ref in test_cases:
            await run_research_test(research_chain, description, query, teams, players, date_ref)

@pytest.mark.asyncio
async def test_historical_queries():
    """Test queries for historical performance"""
    async with ResearchChain() as research_chain:
        # Test cases for historical queries
        test_cases = [
            (
                "Recent Celtics performance",
                "Get me recent Celtics performance",
                {"team1": "Celtics"},
                [],
                "recent"
            ),
            (
                "Lakers last week",
                "Show me Lakers performance from last week",
                {"team1": "Lakers"},
                [],
                "last week"
            ),
            (
                "Warriors yesterday",
                "Show me Warriors stats from yesterday",
                {"team1": "Warriors"},
                [],
                "yesterday"
            )
        ]
        
        for description, query, teams, players, date_ref in test_cases:
            await run_research_test(research_chain, description, query, teams, players, date_ref)

if __name__ == "__main__":
    # Run all tests
    asyncio.run(pytest.main([__file__, "-v"])) 