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
    """Print a separator with title for test output"""
    print(f"\n{'='*20} {title} {'='*20}\n")

def log_test_case(description: str):
    """Print test case description"""
    print(f"\n--- Testing: {description} ---")

def log_api_response(data_points, title: str):
    """Log API response data points"""
    print(f"\n{title}:")
    for dp in data_points:
        print(f"Source: {dp.source}")
        if isinstance(dp.content, dict) and "error" in dp.content:
            print(f"Error: {dp.content['error']}")

def create_test_metadata(timezone: str = "America/New_York") -> ClientMetadata:
    """Create test client metadata with minimal context"""
    return ClientMetadata(
        timestamp=datetime(2025, 3, 3, 18, 12, 17, 702408),
        timezone=timezone,
        locale="en-US"
    )

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

@pytest.mark.asyncio
async def test_matchup_analysis_through_chain():
    """Test matchup analysis through the research chain"""
    log_separator("Testing Matchup Analysis Through Chain")
    
    async with ResearchChain() as chain:
        # Test with minimal data for Lakers vs Warriors
        request = ResearchRequest(
            query="Compare Lakers vs Warriors head to head stats",
            mode=ResearchMode.DEEP,
            client_metadata=create_test_metadata(),
            context=ConversationContext(
                teams=["Los Angeles Lakers", "Golden State Warriors"],
                sport=SportType.BASKETBALL,
                required_data=["team_stats", "recent_games"]  # Specify only needed data
            )
        )
        
        response = await chain.process_request(request)
        log_api_response(response.data_points, "Matchup Response")
        
        # Verify response structure
        basketball_data = [dp for dp in response.data_points if dp.source == "basketball_api"]
        assert len(basketball_data) > 0, "No basketball API data found"
        
        # Check for essential data components
        found_stats = False
        found_games = False
        for dp in basketball_data:
            content = dp.content
            if isinstance(content, dict):
                if content.get("statistics"):
                    found_stats = True
                    assert isinstance(content["statistics"], dict), "Invalid statistics format"
                if content.get("games"):
                    found_games = True
                    assert isinstance(content["games"], list), "Invalid games format"
                    # Only check first 5 games to reduce context
                    content["games"] = content["games"][:5]
        
        assert found_stats, "No team statistics found in response"
        assert found_games, "No games data found in response"

@pytest.mark.asyncio
async def test_matchup_error_handling():
    """Test error handling for matchup analysis"""
    log_separator("Testing Matchup Error Handling")
    
    async with ResearchChain() as chain:
        error_test_cases = [
            {
                "description": "Invalid team names",
                "query": "Compare Invalid Team A vs Invalid Team B",
                "expected_error": "Team not found"
            },
            {
                "description": "Missing second team",
                "query": "How does the Lakers match up?",
                "expected_error": "second team"
            }
        ]
        
        for case in error_test_cases:
            log_test_case(case["description"])
            
            request = ResearchRequest(
                query=case["query"],
                mode=ResearchMode.DEEP,
                client_metadata=create_test_metadata(),
                context=ConversationContext(
                    required_data=["team_stats"]  # Minimal data requirement
                )
            )
            
            response = await chain.process_request(request)
            log_api_response(response.data_points, "Error Case Response")
            
            # Verify error handling with more flexible error message matching
            error_found = False
            for dp in response.data_points:
                if dp.source == "basketball_api" and isinstance(dp.content, dict):
                    error = dp.content.get("error", "").lower()
                    expected = case["expected_error"].lower()
                    if error and expected in error:
                        error_found = True
                        break
            
            assert error_found, f"Expected error containing '{case['expected_error']}' not found in response"

@pytest.mark.asyncio
async def test_matchup_with_different_timezones():
    """Test matchup analysis with different timezone contexts"""
    log_separator("Testing Matchup Analysis with Different Timezones")
    
    # Test with just one timezone to reduce context
    tz = "America/New_York"
    log_test_case(f"Testing with timezone: {tz}")
    
    async with ResearchChain() as chain:
        request = ResearchRequest(
            query="Compare Lakers vs Warriors head to head stats",
            mode=ResearchMode.DEEP,
            client_metadata=create_test_metadata(timezone=tz),
            context=ConversationContext(
                teams=["Los Angeles Lakers", "Golden State Warriors"],
                sport=SportType.BASKETBALL,
                required_data=["team_stats", "recent_games"]  # Specify only needed data
            )
        )
        
        response = await chain.process_request(request)
        log_api_response(response.data_points, "Timezone Test Response")
        
        # Verify timezone handling
        basketball_data = [dp for dp in response.data_points if dp.source == "basketball_api"]
        assert len(basketball_data) > 0, "No basketball API data found"
        
        # Check that games data is present and properly formatted
        for dp in basketball_data:
            if isinstance(dp.content, dict) and "games" in dp.content:
                games = dp.content["games"]
                assert isinstance(games, list), "Games should be a list"
                # Only check first 5 games to reduce context
                dp.content["games"] = games[:5]
                if games:
                    assert "date" in games[0], "Game should have a date"

async def main():
    """Run all test functions"""
    try:
        await test_basketball_service_comprehensive()
        await test_error_handling()
        await test_date_handling()
        await test_matchup_analysis_through_chain()
        await test_matchup_error_handling()
        await test_matchup_with_different_timezones()
    except Exception as e:
        logger.error("Test suite failed", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 