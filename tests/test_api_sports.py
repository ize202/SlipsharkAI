"""
Tests for the NBA API service
"""

import os
import pytest
import asyncio
import logging
from datetime import datetime
from app.services.api_sports_basketball import (
    NBAService,
    NBAApiError,
    RateLimitError,
    AuthenticationError,
    Team,
    Game,
    TeamStatistics
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
async def nba_service():
    """Fixture providing an NBA service instance"""
    async with NBAService() as service:
        yield service

@pytest.mark.asyncio
async def test_list_teams(nba_service):
    """Test listing NBA teams"""
    teams = await nba_service.teams.list_teams()
    assert len(teams) > 0
    assert all(isinstance(team, Team) for team in teams)
    logger.info(f"Found {len(teams)} teams")
    # Log first team as example
    logger.info(f"Example team: {teams[0].model_dump_json(indent=2)}")

@pytest.mark.asyncio
async def test_team_statistics(nba_service):
    """Test getting team statistics"""
    # Lakers team ID
    lakers_id = 17
    stats = await nba_service.teams.get_team_statistics(lakers_id)
    assert isinstance(stats, TeamStatistics)
    logger.info(f"Lakers stats: {stats.model_dump_json(indent=2)}")

@pytest.mark.asyncio
async def test_list_games(nba_service):
    """Test listing games"""
    # Get today's games
    today = datetime.now().strftime("%Y-%m-%d")
    games = await nba_service.games.list_games(date=today)
    logger.info(f"Found {len(games)} games for {today}")
    if games:
        logger.info(f"Example game: {games[0].model_dump_json(indent=2)}")

@pytest.mark.asyncio
async def test_game_statistics(nba_service):
    """Test getting game statistics"""
    # First get a game ID from recent games
    games = await nba_service.games.list_games()
    if games:
        game_id = games[0].id
        stats = await nba_service.games.get_game_statistics(game_id)
        assert stats is not None
        logger.info(f"Game stats for game {game_id}: {stats}")

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling with invalid API key"""
    # Temporarily set invalid API key
    original_key = os.environ.get("API_SPORTS_KEY")
    os.environ["API_SPORTS_KEY"] = "invalid_key"
    
    try:
        async with NBAService() as service:
            with pytest.raises(AuthenticationError):
                await service.teams.list_teams()
    finally:
        # Restore original key
        if original_key:
            os.environ["API_SPORTS_KEY"] = original_key
        else:
            del os.environ["API_SPORTS_KEY"]

async def main():
    """Main test function"""
    async with NBAService() as service:
        logger.info("Testing NBA API Service...")
        
        # Test teams
        await test_list_teams(service)
        
        # Test team statistics
        await test_team_statistics(service)
        
        # Test games
        await test_list_games(service)
        
        # Test game statistics
        await test_game_statistics(service)
        
        logger.info("All tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 