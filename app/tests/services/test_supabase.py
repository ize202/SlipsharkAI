import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, MagicMock, AsyncMock
from langfuse.decorators import observe
from app.services.supabase import SupabaseService, BetHistory, UserStats, UserPreferences
from app.utils.decorators import requires_api_keys

# Mock API responses
MOCK_BET_HISTORY = [
    {
        "entry_id": "bet_123",
        "bet_type": "moneyline",
        "sport": "basketball",
        "game_id": "game_456",
        "odds": -110,
        "boost_applied": False,
        "boost_percentage": None,
        "cash_out_available": True,
        "early_payout": False,
        "void_reason": None,
        "metadata": {
            "team": "Los Angeles Lakers",
            "opponent": "Golden State Warriors",
            "prediction": "win",
            "stake": 100.00,
            "result": "win",
            "profit_loss": 90.91,
            "placed_at": "2024-02-23T19:30:00Z"
        }
    }
]

MOCK_USER_STATS = [
    {
        "user_id": "user_123",
        "entry_type": "bet",
        "sport": "basketball",
        "period": "last_month",
        "total_entries": 50,
        "won_entries": 28,
        "total_stake": 1000.0,
        "total_payout": 1150.0,
        "roi": 0.15,
        "updated_at": "2024-02-23T19:30:00Z"
    }
]

MOCK_SIMILAR_BETS = [
    {
        "entry_id": "bet_789",
        "bet_type": "moneyline",
        "sport": "basketball",
        "game_id": "game_101",
        "odds": 2.0,
        "boost_applied": False,
        "boost_percentage": None,
        "metadata": {
            "team": "Boston Celtics",
            "opponent": "Miami Heat",
            "prediction": "win"
        },
        "created_at": "2024-02-22T19:30:00Z"
    }
]

MOCK_USER_PREFERENCES = {
    "user_id": "user123",
    "favorite_teams": ["Los Angeles Lakers", "Golden State Warriors"],
    "favorite_leagues": ["NBA"],
    "stake_limits": {
        "min": 10.00,
        "max": 1000.00
    },
    "notification_preferences": {
        "email": True,
        "push": False
    },
    "updated_at": "2024-02-23T19:30:00Z"
}

@pytest_asyncio.fixture
async def supabase_service():
    """Fixture for SupabaseService with mocked client"""
    # Create mock Supabase client
    mock_client = MagicMock()
    
    # Create mock response
    mock_response = AsyncMock()
    mock_response.execute = AsyncMock()
    
    # Create mock query builder
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq = MagicMock()
    mock_gte = MagicMock()
    mock_lte = MagicMock()
    
    # Set up the chain
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.eq.return_value = mock_eq  # For double eq() calls
    mock_eq.gte.return_value = mock_gte
    mock_gte.lte.return_value = mock_lte
    
    # Make all query builder methods return the final mock_response.execute
    mock_table.execute = mock_response.execute
    mock_select.execute = mock_response.execute
    mock_eq.execute = mock_response.execute
    mock_gte.execute = mock_response.execute
    mock_lte.execute = mock_response.execute
    
    # Make all query builder methods return themselves for chaining
    mock_table.select = MagicMock(return_value=mock_table)
    mock_table.eq = MagicMock(return_value=mock_table)
    mock_table.gte = MagicMock(return_value=mock_table)
    mock_table.lte = MagicMock(return_value=mock_table)
    
    mock_select.eq = MagicMock(return_value=mock_select)
    mock_select.gte = MagicMock(return_value=mock_select)
    mock_select.lte = MagicMock(return_value=mock_select)
    
    mock_eq.eq = MagicMock(return_value=mock_eq)
    mock_eq.gte = MagicMock(return_value=mock_eq)
    mock_eq.lte = MagicMock(return_value=mock_eq)
    
    mock_gte.eq = MagicMock(return_value=mock_gte)
    mock_gte.gte = MagicMock(return_value=mock_gte)
    mock_gte.lte = MagicMock(return_value=mock_gte)
    
    mock_lte.eq = MagicMock(return_value=mock_lte)
    mock_lte.gte = MagicMock(return_value=mock_lte)
    mock_lte.lte = MagicMock(return_value=mock_lte)
    
    # Create service instance with mock client
    service = SupabaseService()
    service.client = mock_client
    return service, mock_response.execute

@pytest.mark.asyncio
@observe(name="test_supabase_get_bet_history")
async def test_get_bet_history(supabase_service):
    """Test getting bet history with Langfuse tracing"""
    service, mock_execute = supabase_service
    
    # Set up mock response
    mock_execute.return_value.data = MOCK_BET_HISTORY

    # Call the method
    history = await service.get_bet_history(
        user_id="user123",
        days_back=30
    )

    # Verify the response
    assert len(history) == 1
    bet = history[0]
    assert isinstance(bet, BetHistory)
    assert bet.entry_id == "bet_123"
    assert bet.bet_type == "moneyline"
    assert bet.sport == "basketball"
    assert bet.game_id == "game_456"
    assert bet.odds == -110
    assert bet.boost_applied is False
    assert bet.boost_percentage is None
    assert bet.cash_out_available is True
    assert bet.early_payout is False
    assert bet.void_reason is None
    
    # Verify metadata
    assert isinstance(bet.metadata, dict)
    assert bet.metadata["team"] == "Los Angeles Lakers"
    assert bet.metadata["opponent"] == "Golden State Warriors"
    assert bet.metadata["prediction"] == "win"
    assert bet.metadata["stake"] == 100.00
    assert bet.metadata["result"] == "win"
    assert bet.metadata["profit_loss"] == 90.91
    assert "placed_at" in bet.metadata

    # Verify the query chain was called correctly
    service.client.table.assert_called_once_with("bet_details")  # Note: using bet_details table
    table_mock = service.client.table.return_value
    table_mock.select.assert_called_once_with("*")
    select_mock = table_mock.select.return_value
    select_mock.eq.assert_called_once_with("user_id", "user123")

@pytest.mark.asyncio
@observe(name="test_supabase_user_stats")
async def test_get_user_stats(supabase_service):
    """Test getting user betting statistics with Langfuse tracing"""
    service, mock_execute = supabase_service
    
    # Set up mock response
    mock_execute.return_value.data = MOCK_USER_STATS
    
    # Call the method
    stats = await service.get_user_stats(
        user_id="user_123"
    )
    
    # Verify the response
    assert len(stats) == 1
    stat = stats[0]
    assert isinstance(stat, UserStats)
    assert stat.user_id == "user_123"
    assert stat.entry_type == "bet"
    assert stat.sport == "basketball"
    assert stat.period == "last_month"
    assert stat.total_entries == 50
    assert stat.won_entries == 28
    assert stat.total_stake == 1000.0
    assert stat.total_payout == 1150.0
    assert stat.roi == 0.15
    assert isinstance(stat.updated_at, datetime)

    # Verify the query chain was called correctly
    service.client.table.assert_called_once_with("user_stats")
    table_mock = service.client.table.return_value
    table_mock.select.assert_called_once_with("*")
    select_mock = table_mock.select.return_value
    select_mock.eq.assert_called_once_with("user_id", "user_123")

@pytest.mark.asyncio
@observe(name="test_supabase_similar_bets")
async def test_get_similar_bets(supabase_service):
    """Test getting similar bets with Langfuse tracing"""
    service, mock_execute = supabase_service
    
    # Set up mock response
    mock_execute.return_value.data = MOCK_SIMILAR_BETS

    # Call the method
    bets = await service.get_similar_bets(
        sport="basketball",
        bet_type="moneyline",
        days_back=30,
        min_odds=1.5,
        max_odds=2.5
    )

    # Verify the response
    assert len(bets) == 1
    bet = bets[0]
    assert isinstance(bet, BetHistory)
    assert bet.entry_id == "bet_789"
    assert bet.sport == "basketball"
    assert bet.bet_type == "moneyline"
    assert bet.game_id == "game_101"
    assert bet.odds == 2.0
    assert bet.boost_applied is False
    assert bet.boost_percentage is None
    assert isinstance(bet.metadata, dict)
    assert bet.metadata["team"] == "Boston Celtics"
    assert bet.metadata["opponent"] == "Miami Heat"
    assert bet.metadata["prediction"] == "win"

    # Verify the query chain was called correctly
    service.client.table.assert_called_with("bet_details")  # Changed from assert_called_once_with
    table_mock = service.client.table.return_value
    table_mock.select.assert_called_with("*")
    select_mock = table_mock.select.return_value
    select_mock.eq.assert_any_call("sport", "basketball")
    select_mock.eq.assert_any_call("bet_type", "moneyline")

@pytest.mark.asyncio
@observe(name="test_supabase_error_handling")
async def test_error_handling(supabase_service):
    """Test error handling in Supabase service with Langfuse tracing"""
    service, mock_execute = supabase_service
    
    # Mock database error
    mock_execute.side_effect = Exception("Database error")
    
    # Test error handling for bet history
    with pytest.raises(Exception) as exc_info:
        await service.get_bet_history("user123", 30)
    assert "Error fetching bet history" in str(exc_info.value)

    # Test error handling for user preferences
    with pytest.raises(Exception) as exc_info:
        await service.get_user_preferences("user123")
    assert "Error fetching user preferences" in str(exc_info.value)

    # Test error handling for user stats
    with pytest.raises(Exception) as exc_info:
        await service.get_user_stats("user123")
    assert "Error fetching user stats" in str(exc_info.value)

    # Test error handling for similar bets
    with pytest.raises(Exception) as exc_info:
        await service.get_similar_bets("basketball", "moneyline")
    assert "Error getting similar bets" in str(exc_info.value)

    # Verify the query chains were called correctly
    assert service.client.table.call_count == 4
    service.client.table.assert_any_call("bet_details")
    service.client.table.assert_any_call("user_preferences")
    service.client.table.assert_any_call("user_stats")
    service.client.table.assert_any_call("bet_details")

@pytest.mark.asyncio
@observe(name="test_supabase_date_filtering")
async def test_date_filtering(supabase_service):
    """Test date filtering in queries with Langfuse tracing"""
    service, mock_execute = supabase_service
    
    # Set up mock response
    mock_execute.return_value.data = MOCK_BET_HISTORY
    
    # Test different date ranges
    days_back_values = [7, 30, 90]
    for days in days_back_values:
        # Reset call counts for each iteration
        service.client.table.reset_mock()
        
        # Call the method
        await service.get_bet_history(
            user_id="test_user",
            days_back=days
        )
        
        # Verify the query chain was called correctly
        service.client.table.assert_called_once_with("bet_details")  # Changed from bet_history
        table_mock = service.client.table.return_value
        table_mock.select.assert_called_once_with("*")
        select_mock = table_mock.select.return_value
        select_mock.eq.assert_called_once_with("user_id", "test_user")
        
        # Verify the date filter was applied
        expected_date = datetime.now(UTC) - timedelta(days=days)
        eq_mock = select_mock.eq.return_value
        eq_mock.gte.assert_called_once()
        date_arg = eq_mock.gte.call_args[0][1]  # Get the date argument
        assert isinstance(date_arg, str)
        assert expected_date.strftime("%Y-%m-%d") in date_arg

@pytest.mark.asyncio
@observe(name="test_supabase_metadata_handling")
async def test_metadata_handling(supabase_service):
    """Test handling of metadata in bet history with Langfuse tracing"""
    service, mock_execute = supabase_service
    
    # Set up mock response with complex metadata
    mock_execute.return_value.data = [{
        **MOCK_BET_HISTORY[0],
        "metadata": {
            "team": "Los Angeles Lakers",
            "opponent": "Golden State Warriors",
            "prediction": "win",
            "analysis": {
                "key_factors": ["home court advantage", "recent form"],
                "confidence": 0.85,
                "sources": ["team stats", "injury report"]
            },
            "odds_history": [
                {"timestamp": "2024-02-23T18:30:00Z", "value": 1.90},
                {"timestamp": "2024-02-23T19:00:00Z", "value": 1.95}
            ]
        }
    }]
    
    # Call the method
    bets = await service.get_bet_history(
        user_id="test_user",
        days_back=30
    )
    
    # Verify the response
    assert len(bets) == 1
    bet = bets[0]
    assert isinstance(bet, BetHistory)
    
    # Verify metadata structure
    assert isinstance(bet.metadata, dict)
    assert bet.metadata["team"] == "Los Angeles Lakers"
    assert bet.metadata["opponent"] == "Golden State Warriors"
    assert bet.metadata["prediction"] == "win"
    
    # Verify nested analysis data
    analysis = bet.metadata["analysis"]
    assert isinstance(analysis, dict)
    assert "key_factors" in analysis
    assert len(analysis["key_factors"]) == 2
    assert analysis["confidence"] == 0.85
    assert len(analysis["sources"]) == 2
    
    # Verify odds history
    odds_history = bet.metadata["odds_history"]
    assert isinstance(odds_history, list)
    assert len(odds_history) == 2
    for odds_entry in odds_history:
        assert "timestamp" in odds_entry
        assert "value" in odds_entry
        assert isinstance(odds_entry["value"], float)
        
    # Verify the query chain was called correctly
    service.client.table.assert_called_once_with("bet_details")  # Changed from bet_history
    table_mock = service.client.table.return_value
    table_mock.select.assert_called_once_with("*")
    select_mock = table_mock.select.return_value
    select_mock.eq.assert_called_once_with("user_id", "test_user")

@pytest.mark.asyncio
@observe(name="test_supabase_roi_calculation")
async def test_roi_calculation(supabase_service):
    """Test ROI calculation in user stats with Langfuse tracing"""
    service, mock_execute = supabase_service
    
    # Set up mock response with different ROI scenarios
    mock_execute.return_value.data = [
        {
            **MOCK_USER_STATS[0],
            "total_stake": 1000.0,
            "total_payout": 1150.0,
            "roi": 0.15,
            "period": "last_month"
        },
        {
            **MOCK_USER_STATS[0],
            "period": "all-time",
            "total_stake": 5000.0,
            "total_payout": 4750.0,
            "roi": -0.05
        }
    ]
    
    # Call the method
    stats = await service.get_user_stats(
        user_id="user_123"
    )
    
    # Verify the response
    assert len(stats) == 2
    assert all(isinstance(stat, UserStats) for stat in stats)
    
    # Verify monthly stats
    monthly_stat = next(stat for stat in stats if stat.period == "last_month")
    assert monthly_stat.total_stake == 1000.0
    assert monthly_stat.total_payout == 1150.0
    assert monthly_stat.roi == 0.15
    assert monthly_stat.total_payout - monthly_stat.total_stake == 150.0
    
    # Verify all-time stats
    all_time_stat = next(stat for stat in stats if stat.period == "all-time")
    assert all_time_stat.total_stake == 5000.0
    assert all_time_stat.total_payout == 4750.0
    assert all_time_stat.roi == -0.05
    assert all_time_stat.total_payout - all_time_stat.total_stake == -250.0
    
    # Verify the query chain was called correctly
    service.client.table.assert_called_once_with("user_stats")
    table_mock = service.client.table.return_value
    table_mock.select.assert_called_once_with("*")
    select_mock = table_mock.select.return_value
    select_mock.eq.assert_called_once_with("user_id", "user_123")

@pytest.mark.asyncio
@observe(name="test_supabase_get_user_preferences")
async def test_get_user_preferences(supabase_service):
    """Test getting user preferences with Langfuse tracing"""
    service, mock_execute = supabase_service
    
    # Set up mock response
    mock_execute.return_value.data = [MOCK_USER_PREFERENCES]

    # Call the method
    prefs = await service.get_user_preferences("user123")

    # Verify the response
    assert isinstance(prefs, UserPreferences)
    assert prefs.user_id == "user123"
    
    # Verify favorite teams and leagues
    assert isinstance(prefs.favorite_teams, list)
    assert len(prefs.favorite_teams) == 2
    assert "Los Angeles Lakers" in prefs.favorite_teams
    assert "Golden State Warriors" in prefs.favorite_teams
    assert isinstance(prefs.favorite_leagues, list)
    assert len(prefs.favorite_leagues) == 1
    assert "NBA" in prefs.favorite_leagues
    
    # Verify stake limits
    assert isinstance(prefs.stake_limits, dict)
    assert prefs.stake_limits["min"] == 10.00
    assert prefs.stake_limits["max"] == 1000.00
    
    # Verify notification preferences
    assert isinstance(prefs.notification_preferences, dict)
    assert prefs.notification_preferences["email"] is True
    assert prefs.notification_preferences["push"] is False
    
    # Verify timestamp
    assert isinstance(prefs.updated_at, datetime)
    
    # Verify the query chain was called correctly
    service.client.table.assert_called_once_with("user_preferences")
    table_mock = service.client.table.return_value
    table_mock.select.assert_called_once_with("*")
    select_mock = table_mock.select.return_value
    select_mock.eq.assert_called_once_with("user_id", "user123")

@pytest.mark.asyncio
@requires_api_keys
@observe(name="test_supabase_live_api")
async def test_live_api_call():
    """Test live API call with Langfuse tracing"""
    async with SupabaseService() as service:
        bets = await service.get_bet_history("test_user", 30)
        assert isinstance(bets, list)
        
        # Test user stats
        stats = await service.get_user_stats("test_user")
        assert isinstance(stats, list)
        
        # Test user preferences
        try:
            prefs = await service.get_user_preferences("test_user")
            assert isinstance(prefs, UserPreferences)
        except Exception as e:
            assert "No preferences found for user" in str(e)
        
        # Test similar bets
        similar = await service.get_similar_bets("basketball", "moneyline")
        assert isinstance(similar, list) 