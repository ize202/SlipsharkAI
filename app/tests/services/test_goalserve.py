import pytest
import pytest_asyncio
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
    "statistic": {
        "team": {
            "id": "1066",
            "name": "Los Angeles Lakers",
            "stats": {
                "wins": "10",
                "losses": "5",
                "win_percentage": "0.667",
                "points_per_game": "115.5",
                "points_allowed": "108.5",
                "last_ten": "7-3",
                "streak": "W4",
                "home_record": "6-2",
                "away_record": "4-3",
                "conference_rank": "4"
            },
            "players": [
                {
                    "id": "12345",
                    "name": "John Doe",
                    "position": "F",
                    "status": "Active",
                    "points_per_game": "25.5",
                    "rebounds_per_game": "10.2",
                    "assists_per_game": "8.5",
                    "minutes_per_game": "35.5"
                }
            ]
        }
    }
}

MOCK_SCHEDULE_RESPONSE = {
    "matches": [
        {
            "id": "12345",
            "home_team": {
                "name": "Los Angeles Lakers",
                "id": "1066"
            },
            "away_team": {
                "name": "Golden State Warriors",
                "id": "1067"
            },
            "venue_name": "Crypto.com Arena",
            "status": "scheduled",
            "date": "2024-02-23T19:30:00Z",
            "formatted_date": "23.02.2024"
        }
    ]
}

MOCK_ODDS_RESPONSE = {
    "matches": [
        {
            "id": "12345",
            "home_team": {
                "name": "Los Angeles Lakers",
                "id": "1066"
            },
            "away_team": {
                "name": "Golden State Warriors",
                "id": "1067"
            },
            "odds": {
                "home_team_odds": "1.5",
                "away_team_odds": "2.5",
                "spread": "-5.5",
                "total": "235.5"
            }
        }
    ]
}

MOCK_H2H_RESPONSE = {
    "h2h": {
        "total_games": "10",
        "team1_wins": "6",
        "team2_wins": "4",
        "last_games": [
            {
                "date": "2024-02-20",
                "winner": "Los Angeles Lakers",
                "score": "120-110"
            }
        ],
        "avg_points_team1": "115.5",
        "avg_points_team2": "110.2"
    }
}

MOCK_STANDINGS_RESPONSE = {
    "standings": {
        "western": [
            {
                "team_id": "1066",
                "name": "Los Angeles Lakers",
                "wins": "10",
                "losses": "5",
                "win_percentage": "0.667",
                "conference_rank": "4"
            }
        ]
    }
}

MOCK_LIVE_SCORES_RESPONSE = {
    "matches": [
        {
            "id": "12345",
            "home_team": {
                "name": "Los Angeles Lakers",
                "id": "1066",
                "totalscore": "100"
            },
            "away_team": {
                "name": "Golden State Warriors",
                "id": "1067",
                "totalscore": "95"
            },
            "period": "4th",
            "time_remaining": "2:30",
            "status": "live"
        }
    ]
}

@pytest_asyncio.fixture
async def goalserve_service():
    """Fixture for GoalserveNBAService with mocked client"""
    service = GoalserveNBAService()
    service.client = AsyncMock()
    service.client.__aenter__.return_value = service.client
    return service

@pytest.mark.asyncio
@observe(name="test_goalserve_team_stats")
async def test_get_team_stats(goalserve_service):
    """Test getting team statistics with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=MOCK_TEAM_STATS_RESPONSE)
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response

    # Call the method
    stats = await goalserve_service.get_team_stats("1066")

    # Verify the response
    assert stats.team_id == "1066"
    assert stats.name == "Los Angeles Lakers"
    assert stats.wins == 10
    assert stats.losses == 5
    assert stats.win_percentage == 0.667
    assert stats.points_per_game == 115.5
    assert stats.points_allowed == 108.5
    assert stats.last_ten == "7-3"
    assert stats.streak == "W4"
    assert stats.home_record == "6-2"
    assert stats.away_record == "4-3"
    assert stats.conference_rank == 4

@pytest.mark.asyncio
@observe(name="test_goalserve_player_stats")
async def test_get_player_stats(goalserve_service):
    """Test getting player statistics with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=MOCK_TEAM_STATS_RESPONSE)
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response

    # Call the method
    players = await goalserve_service.get_player_stats("1066")

    # Verify the response
    assert len(players) == 1
    assert players[0].player_id == "12345"
    assert players[0].name == "John Doe"

@pytest.mark.asyncio
@observe(name="test_goalserve_upcoming_games")
async def test_get_upcoming_games(goalserve_service):
    """Test getting upcoming games with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=MOCK_SCHEDULE_RESPONSE)
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response

    # Call the method
    games = await goalserve_service.get_upcoming_games("Los Angeles Lakers")

    # Verify the response
    assert len(games) == 1
    assert games[0].game_id == "12345"
    assert games[0].home_team == "Los Angeles Lakers"

@pytest.mark.asyncio
@observe(name="test_goalserve_odds_comparison")
async def test_get_odds_comparison(goalserve_service):
    """Test getting odds comparison with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=MOCK_ODDS_RESPONSE)
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response

    # Call the method
    odds = await goalserve_service.get_odds_comparison()

    # Verify the response
    assert len(odds) == 1
    assert odds[0].game_id == "12345"
    assert odds[0].home_team_odds == 1.5

@pytest.mark.asyncio
@observe(name="test_goalserve_head_to_head")
async def test_get_head_to_head(goalserve_service):
    """Test getting head-to-head comparison with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=MOCK_H2H_RESPONSE)
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response

    # Call the method
    h2h = await goalserve_service.get_head_to_head("1066", "1067")

    # Verify the response
    assert h2h.total_games == 10
    assert h2h.home_team_wins == 6
    assert h2h.away_team_wins == 4

@pytest.mark.asyncio
@observe(name="test_goalserve_standings")
async def test_get_standings(goalserve_service):
    """Test getting standings with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=MOCK_STANDINGS_RESPONSE)
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response

    # Call the method
    standings = await goalserve_service.get_standings()

    # Verify the response
    assert len(standings) == 1
    assert standings[0].team_id == "1066"
    assert standings[0].wins == 10

@pytest.mark.asyncio
@observe(name="test_goalserve_live_scores")
async def test_get_live_scores(goalserve_service):
    """Test getting live scores with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=MOCK_LIVE_SCORES_RESPONSE)
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response

    # Call the method
    scores = await goalserve_service.get_live_scores()

    # Verify the response
    assert len(scores) == 1
    assert scores[0].game_id == "12345"
    assert scores[0].home_team_score == 100

@pytest.mark.asyncio
@observe(name="test_goalserve_gzip_handling")
async def test_gzip_handling(goalserve_service):
    """Test GZIP compression handling with Langfuse tracing"""
    # Mock a GZIP compressed response
    mock_response = AsyncMock()
    mock_response.headers = {"content-encoding": "gzip"}
    mock_response.content = b"gzipped_content"
    goalserve_service.client.get.return_value = mock_response

    with patch("gzip.decompress") as mock_decompress:
        mock_decompress.return_value = json.dumps(MOCK_TEAM_STATS_RESPONSE).encode()

        # Call the method
        stats = await goalserve_service.get_team_stats("1066")

        # Verify the response
        assert stats.team_id == "1066"
        assert stats.wins == 10
        assert stats.losses == 5

@pytest.mark.asyncio
@observe(name="test_goalserve_date_parsing")
async def test_date_parsing(goalserve_service):
    """Test date parsing in responses with Langfuse tracing"""
    # Mock the API response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=MOCK_SCHEDULE_RESPONSE)
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response

    # Call the method
    games = await goalserve_service.get_upcoming_games("Los Angeles Lakers")

    # Verify date parsing
    assert isinstance(games[0].game_date, datetime)
    assert games[0].game_date.year == 2024  # Adjust based on your mock data

@pytest.mark.asyncio
@observe(name="test_goalserve_error_handling")
async def test_error_handling(goalserve_service):
    """Test error handling in the service with Langfuse tracing"""
    # Mock an API error response
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = Exception("API Error")
    mock_response.headers = {}
    goalserve_service.client.get.return_value = mock_response
    
    # Test error handling for each method
    with pytest.raises(Exception):
        await goalserve_service.get_team_stats("1066") 