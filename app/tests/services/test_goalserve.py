import pytest
import json
from datetime import datetime, UTC
from unittest.mock import patch, AsyncMock
from langfuse.decorators import observe
from app.services.goalserve import (
    GoalserveNBAService,
    NBATeamStats,
    NBAPlayerStats,
    NBAGameOdds,
    NBASchedule,
    NBAHeadToHead,
    NBAStandings,
    NBALiveScore
)

# Mock API responses
MOCK_TEAM_STATS_RESPONSE = {
    "statistics": {
        "team": {
            "id": "1066",
            "name": "Los Angeles Lakers",
            "wins": 30,
            "losses": 20,
            "win_percentage": 0.600,
            "points_per_game": 115.5,
            "points_allowed": 110.2,
            "last_ten": "7-3",
            "streak": "W4",
            "home_record": "18-8",
            "away_record": "12-12",
            "conference_rank": 4
        },
        "players": [
            {
                "id": "123",
                "name": "LeBron James",
                "position": "F",
                "status": "Active",
                "points_per_game": 25.5,
                "rebounds_per_game": 7.8,
                "assists_per_game": 8.2,
                "minutes_per_game": 34.5
            }
        ]
    }
}

MOCK_SCHEDULE_RESPONSE = {
    "games": [
        {
            "id": "12345",
            "date": "2024-02-23",
            "time": "19:30",
            "hometeam": "Los Angeles Lakers",
            "awayteam": "Golden State Warriors",
            "venue": "Crypto.com Arena",
            "status": "scheduled"
        }
    ]
}

MOCK_ODDS_RESPONSE = {
    "matches": [
        {
            "contestID": "12345",
            "formatted_date": "2024-02-23",
            "time": "19:30",
            "hometeam": "Los Angeles Lakers",
            "awayteam": "Golden State Warriors",
            "odds": {
                "spread": {"home": -5.5},
                "total": {"total": 235.5},
                "moneyline": {"home": -150, "away": +130}
            }
        }
    ]
}

MOCK_H2H_RESPONSE = {
    "h2h": {
        "total_games": 50,
        "team1_wins": 30,
        "team2_wins": 20,
        "last_games": [{"game": "details"}] * 5,
        "avg_points_team1": 112.5,
        "avg_points_team2": 108.3
    }
}

MOCK_STANDINGS_RESPONSE = {
    "standings": {
        "western": [
            {
                "conference": "Western",
                "position": 1,
                "id": "1066",
                "name": "Los Angeles Lakers",
                "won": 30,
                "lost": 20,
                "percentage": 0.600,
                "games_back": 0.0,
                "last_ten": "7-3",
                "streak": "W4",
                "points_for": 115.5,
                "points_against": 110.2
            }
        ]
    }
}

MOCK_LIVE_SCORES_RESPONSE = {
    "matches": [
        {
            "id": "12345",
            "status": "live",
            "period": "3rd",
            "timer": "5:30",
            "hometeam": {
                "name": "Los Angeles Lakers",
                "score": 85,
                "scoring_leader": {"name": "LeBron James", "points": 25}
            },
            "awayteam": {
                "name": "Golden State Warriors",
                "score": 80,
                "scoring_leader": {"name": "Stephen Curry", "points": 28}
            },
            "last_play": "James with the three!"
        }
    ]
}

@pytest.fixture
async def goalserve_service():
    """Create a GoalserveNBAService instance with mocked client"""
    with patch("app.services.goalserve.httpx.AsyncClient") as mock_client:
        service = GoalserveNBAService()
        service.client = AsyncMock()
        yield service

@pytest.mark.asyncio
@observe(name="test_goalserve_team_stats")
async def test_get_team_stats(goalserve_service):
    """Test getting team statistics with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_TEAM_STATS_RESPONSE
    goalserve_service.client.get.return_value = mock_response
    
    # Call the method
    stats = await goalserve_service.get_team_stats("1066")
    
    # Verify the response
    assert isinstance(stats, NBATeamStats)
    assert stats.team_id == "1066"
    assert stats.name == "Los Angeles Lakers"
    assert stats.wins == 30
    assert stats.losses == 20
    assert stats.win_percentage == 0.600
    assert stats.points_per_game == 115.5
    assert stats.conference_rank == 4

@pytest.mark.asyncio
@observe(name="test_goalserve_player_stats")
async def test_get_player_stats(goalserve_service):
    """Test getting player statistics with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_TEAM_STATS_RESPONSE
    goalserve_service.client.get.return_value = mock_response
    
    # Call the method
    players = await goalserve_service.get_player_stats("1066")
    
    # Verify the response
    assert len(players) == 1
    player = players[0]
    assert isinstance(player, NBAPlayerStats)
    assert player.name == "LeBron James"
    assert player.position == "F"
    assert player.points_per_game == 25.5
    assert player.assists_per_game == 8.2

@pytest.mark.asyncio
@observe(name="test_goalserve_upcoming_games")
async def test_get_upcoming_games(goalserve_service):
    """Test getting upcoming games with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_SCHEDULE_RESPONSE
    goalserve_service.client.get.return_value = mock_response
    
    # Call the method
    games = await goalserve_service.get_upcoming_games("Los Angeles Lakers")
    
    # Verify the response
    assert len(games) == 1
    game = games[0]
    assert isinstance(game, NBASchedule)
    assert game.home_team == "Los Angeles Lakers"
    assert game.away_team == "Golden State Warriors"
    assert game.venue == "Crypto.com Arena"
    assert game.status == "scheduled"

@pytest.mark.asyncio
@observe(name="test_goalserve_odds_comparison")
async def test_get_odds_comparison(goalserve_service):
    """Test getting odds comparison with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_ODDS_RESPONSE
    goalserve_service.client.get.return_value = mock_response
    
    # Call the method
    odds = await goalserve_service.get_odds_comparison(date1="2024-02-23")
    
    # Verify the response
    assert len(odds) == 1
    game_odds = odds[0]
    assert isinstance(game_odds, NBAGameOdds)
    assert game_odds.home_team == "Los Angeles Lakers"
    assert game_odds.spread == -5.5
    assert game_odds.total == 235.5
    assert game_odds.home_moneyline == -150

@pytest.mark.asyncio
@observe(name="test_goalserve_head_to_head")
async def test_get_head_to_head(goalserve_service):
    """Test getting head-to-head comparison with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_H2H_RESPONSE
    goalserve_service.client.get.return_value = mock_response
    
    # Call the method
    h2h = await goalserve_service.get_head_to_head("1066", "1067")
    
    # Verify the response
    assert isinstance(h2h, NBAHeadToHead)
    assert h2h.total_games == 50
    assert h2h.home_team_wins == 30
    assert h2h.away_team_wins == 20
    assert len(h2h.last_five) == 5

@pytest.mark.asyncio
@observe(name="test_goalserve_standings")
async def test_get_standings(goalserve_service):
    """Test getting standings with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_STANDINGS_RESPONSE
    goalserve_service.client.get.return_value = mock_response
    
    # Call the method
    standings = await goalserve_service.get_standings()
    
    # Verify the response
    assert len(standings) == 1
    team = standings[0]
    assert isinstance(team, NBAStandings)
    assert team.conference == "Western"
    assert team.rank == 1
    assert team.team_name == "Los Angeles Lakers"
    assert team.wins == 30

@pytest.mark.asyncio
@observe(name="test_goalserve_live_scores")
async def test_get_live_scores(goalserve_service):
    """Test getting live scores with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_LIVE_SCORES_RESPONSE
    goalserve_service.client.get.return_value = mock_response
    
    # Call the method
    scores = await goalserve_service.get_live_scores()
    
    # Verify the response
    assert len(scores) == 1
    game = scores[0]
    assert isinstance(game, NBALiveScore)
    assert game.status == "live"
    assert game.current_period == "3rd"
    assert game.home_team == "Los Angeles Lakers"
    assert game.home_score == 85
    assert game.away_score == 80

@pytest.mark.asyncio
@observe(name="test_goalserve_error_handling")
async def test_error_handling(goalserve_service):
    """Test error handling in the service with Langfuse tracing"""
    # Mock an API error response
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = Exception("API Error")
    goalserve_service.client.get.return_value = mock_response
    
    # Test error handling for each method
    with pytest.raises(Exception):
        await goalserve_service.get_team_stats("1066")
    
    with pytest.raises(Exception):
        await goalserve_service.get_player_stats("1066")
    
    with pytest.raises(Exception):
        await goalserve_service.get_upcoming_games("Los Angeles Lakers")

@pytest.mark.asyncio
@observe(name="test_goalserve_gzip_handling")
async def test_gzip_handling(goalserve_service):
    """Test GZIP compression handling with Langfuse tracing"""
    # Mock a GZIP compressed response
    mock_response = AsyncMock()
    mock_response.headers = {"content-encoding": "gzip"}
    mock_response.content = b"gzipped_content"  # This would be actual GZIP data
    goalserve_service.client.get.return_value = mock_response
    
    with patch("gzip.decompress") as mock_decompress:
        mock_decompress.return_value = json.dumps(MOCK_TEAM_STATS_RESPONSE).encode()
        
        # Call the method
        stats = await goalserve_service.get_team_stats("1066")
        
        # Verify GZIP handling
        assert mock_decompress.called
        assert isinstance(stats, NBATeamStats)

@pytest.mark.asyncio
@observe(name="test_goalserve_date_parsing")
async def test_date_parsing(goalserve_service):
    """Test date parsing in responses with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_SCHEDULE_RESPONSE
    goalserve_service.client.get.return_value = mock_response
    
    # Call the method
    games = await goalserve_service.get_upcoming_games("Los Angeles Lakers")
    
    # Verify date parsing
    game = games[0]
    assert isinstance(game.start_time, datetime)
    assert game.start_time.year == 2024
    assert game.start_time.month == 2
    assert game.start_time.day == 23 