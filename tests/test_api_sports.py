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
    TeamStatistics,
    NBAApiConfig
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
async def nba_service():
    """Create an NBA service for testing"""
    config = NBAApiConfig.from_env()
    async with NBAService(config) as service:
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

@pytest.mark.asyncio
async def test_list_seasons(nba_service):
    """Test listing available seasons"""
    seasons = await nba_service.seasons.list_seasons()
    assert len(seasons) > 0
    assert all(isinstance(season, int) for season in seasons)
    logger.info(f"Available seasons: {seasons}")

@pytest.mark.asyncio
async def test_list_leagues(nba_service):
    """Test listing available leagues"""
    leagues = await nba_service.leagues.list_leagues()
    assert len(leagues) > 0
    logger.info(f"Available leagues: {leagues}")

@pytest.mark.asyncio
async def test_get_players(nba_service):
    """Test getting players"""
    # Get Lakers players from current season
    lakers_id = 17
    players = await nba_service.players.get_players(
        team_id=lakers_id,
        season="2023"
    )
    assert len(players) > 0
    logger.info(f"Found {len(players)} Lakers players")
    if players:
        logger.info(f"Example player: {players[0].model_dump_json(indent=2)}")

@pytest.mark.asyncio
async def test_player_statistics(nba_service):
    """Test getting player statistics"""
    # First get a player ID from the Lakers
    lakers_id = 17
    players = await nba_service.players.get_players(
        team_id=lakers_id,
        season="2023"
    )
    if players:
        player_id = players[0].id
        stats = await nba_service.players.get_player_statistics(
            player_id=player_id,
            season="2023"
        )
        assert len(stats) > 0
        logger.info(f"Player stats: {stats[0].model_dump_json(indent=2)}")

@pytest.mark.asyncio
async def test_standings(nba_service):
    """Test getting standings"""
    standings = await nba_service.standings.get_standings(
        league="standard",
        season="2023"
    )
    assert len(standings) > 0
    logger.info(f"Found {len(standings)} team standings")
    if standings:
        logger.info(f"Example standing: {standings[0].model_dump_json(indent=2)}")

async def main():
    """Run all tests"""
    logger.info("Testing NBA API Service...")
    config = NBAApiConfig.from_env()
    async with NBAService(config) as service:
        await test_list_seasons(service)
        await test_list_leagues(service)
        await test_list_teams(service)
        await test_team_statistics(service)
        await test_list_games(service)
        await test_game_statistics(service)
        await test_get_players(service)
        await test_player_statistics(service)
        await test_standings(service)
        logger.info("All tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 