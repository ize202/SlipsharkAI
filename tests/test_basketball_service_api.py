import asyncio
from datetime import datetime, timezone
import pytz
import pytest
from app.workflows.research_chain import ResearchChain
from app.models.research_models import (
    ClientMetadata,
    ResearchRequest,
    QueryAnalysis,
    ResearchMode,
    SportType,
    ConversationContext,
    DataPoint
)
from app.config import get_logger
import json
from app.services.basketball_service import BasketballService
from app.utils.test_utils import create_test_metadata
from loguru import logger

logger = get_logger(__name__)

def log_separator(title: str):
    """Print a separator with title for better log readability"""
    logger.info("\n" + "=" * 80)
    logger.info(f"{title}")
    logger.info("=" * 80 + "\n")

def log_test_case(description: str):
    """Log test case description"""
    logger.info(f"\n=== Test Case: {description} ===")

def log_api_response(response, description="API Response"):
    """Log API response in a readable format"""
    try:
        if isinstance(response, list) and response and isinstance(response[0], DataPoint):
            # Convert DataPoints to dictionaries
            serializable_response = [
                {
                    "source": dp.source,
                    "content": dp.content,
                    "timestamp": dp.timestamp.isoformat() if dp.timestamp else None,
                    "confidence": dp.confidence
                }
                for dp in response
            ]
        else:
            serializable_response = response
            
        logger.info(f"\n--- {description} ---\n{json.dumps(serializable_response, indent=2, default=str)}")
    except Exception as e:
        logger.error(f"Error logging response: {e}")
        logger.error(f"Raw response: {response}")

@pytest.mark.asyncio
async def test_basketball_service_comprehensive():
    """Test comprehensive basketball service functionality"""
    # Initialize service
    service = BasketballService()
    
    # Create test client metadata
    client_metadata = create_test_metadata()
    
    async with service:
        # Test 1: Team Recent Performance
        logger.info("Testing team recent performance...")
        query_analysis = QueryAnalysis(
            raw_query="How have the Lakers been performing?",
            sport_type="basketball",
            teams={"team1": "Los Angeles Lakers"},
            players=[],
            bet_type=None,
            odds_mentioned=None,
            game_date=None,
            required_data=["team_stats", "recent_games"],
            recommended_mode=ResearchMode.QUICK,
            confidence_score=0.9
        )
    
        team_data = await service.get_team_data("Los Angeles Lakers", client_metadata)
        assert "error" not in team_data, f"Error in team data: {team_data.get('error')}"
        assert "statistics" in team_data, "Team statistics not found in response"
        assert "games" in team_data, "Games not found in response"
        assert "standings" in team_data, "Standings not found in response"
    
        # Test 2: Player Recent Stats
        logger.info("Testing player recent stats...")
        query_analysis = QueryAnalysis(
            raw_query="How has LeBron James been playing?",
            sport_type="basketball",
            teams={"team1": "Los Angeles Lakers"},
            players=["LeBron James"],
            bet_type=None,
            odds_mentioned=None,
            game_date=None,
            required_data=["player_stats", "recent_games"],
            recommended_mode=ResearchMode.QUICK,
            confidence_score=0.9
        )
    
        player_data = await service.get_player_data(
            "LeBron James",
            team_name="Los Angeles Lakers",
            client_metadata=client_metadata
        )
        assert "error" not in player_data, f"Error in player data: {player_data.get('error')}"
        assert "player" in player_data, "Player info not found in response"
        assert "statistics" in player_data, "Player statistics not found in response"
    
        # Test 3: Team Matchup Analysis
        logger.info("Testing team matchup analysis...")
        query_analysis = QueryAnalysis(
            raw_query="Compare Lakers vs Warriors",
            sport_type="basketball",
            teams={"team1": "Los Angeles Lakers", "team2": "Golden State Warriors"},
            players=[],
            bet_type=None,
            odds_mentioned=None,
            game_date=None,
            required_data=["team_stats", "matchup_history"],
            recommended_mode=ResearchMode.QUICK,
            confidence_score=0.9
        )
    
        matchup_data = await service.get_matchups("Los Angeles Lakers", "Golden State Warriors", client_metadata)
        assert isinstance(matchup_data, list), "Matchup data should be a list"
        assert len(matchup_data) >= 0, "Matchup data should be a list, even if empty"
        for game in matchup_data:
            assert "teams" in game, "Each matchup should have teams data"
            assert "home" in game["teams"], "Each matchup should have home team data"
            assert "away" in game["teams"], "Each matchup should have away team data"

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in basketball service"""
    service = BasketballService()
    client_metadata = create_test_metadata()
    
    async with service:
        # Test invalid team name
        invalid_team_data = await service.get_team_data("Invalid Team", client_metadata)
        assert "error" in invalid_team_data
        assert "Team not found" in invalid_team_data["error"]
        
        # Test invalid player data without team
        invalid_player_data = await service.get_player_data("Invalid Player")
        assert "error" in invalid_player_data
        assert "Team field is required" in invalid_player_data["error"]
        
        # Test invalid matchup
        invalid_matchup = await service.get_matchup_data("Invalid Team 1", "Invalid Team 2")
        assert "error" in invalid_matchup
        assert "One or both teams not found" in invalid_matchup["error"]

@pytest.mark.asyncio
async def test_date_handling():
    """Test date handling in basketball service"""
    service = BasketballService()
    client_metadata = create_test_metadata()
    
    async with service:
        # Test recent games
        recent_games = await service.get_games("recent", client_metadata=client_metadata)
        assert isinstance(recent_games, list), "Recent games should be a list"
        
        # Test team-specific recent games
        team_games = await service.get_games("recent", team_name="Los Angeles Lakers", client_metadata=client_metadata)
        assert isinstance(team_games, list), "Team games should be a list"
        if team_games:  # Only check if games are returned
            assert any("Los Angeles Lakers" in str(game) for game in team_games), "Team games should include the specified team"

async def main():
    """Run all test functions including new ones"""
    try:
        # Existing tests
        await test_basketball_service_comprehensive()
        await test_error_handling()
        await test_date_handling()
    except Exception as e:
        logger.error("Test suite failed", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 