import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, MagicMock
from langfuse.decorators import observe
from app.services.supabase import SupabaseService, BetHistory, UserStats

# Mock API responses
MOCK_BET_HISTORY = [
    {
        "entry_id": "bet_123",
        "bet_type": "moneyline",
        "sport": "basketball",
        "game_id": "game_456",
        "odds": 1.95,
        "boost_applied": True,
        "boost_percentage": 0.1,
        "metadata": {
            "team": "Los Angeles Lakers",
            "opponent": "Golden State Warriors",
            "prediction": "win"
        },
        "created_at": "2024-02-23T19:30:00Z"
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

@pytest.fixture
def supabase_service():
    """Create a SupabaseService instance with mocked client"""
    with patch("app.services.supabase.create_client") as mock_create_client:
        # Create mock Supabase client
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Create service instance
        service = SupabaseService()
        service.client = mock_client
        yield service

@pytest.mark.asyncio
@observe(name="test_supabase_user_bets")
async def test_get_user_bets(supabase_service):
    """Test getting user betting history with Langfuse tracing"""
    # Mock the Supabase response
    mock_response = MagicMock()
    mock_response.data = MOCK_BET_HISTORY
    supabase_service.client.table().select().eq().gte().execute.return_value = mock_response
    
    # Call the method
    bets = await supabase_service.get_user_bets(
        user_id="user_123",
        sport="basketball",
        days_back=30
    )
    
    # Verify the response
    assert len(bets) == 1
    bet = bets[0]
    assert isinstance(bet, BetHistory)
    assert bet.entry_id == "bet_123"
    assert bet.bet_type == "moneyline"
    assert bet.odds == 1.95
    assert bet.boost_applied is True
    assert bet.metadata["team"] == "Los Angeles Lakers"

@pytest.mark.asyncio
@observe(name="test_supabase_user_stats")
async def test_get_user_stats(supabase_service):
    """Test getting user statistics with Langfuse tracing"""
    # Mock the Supabase response
    mock_response = MagicMock()
    mock_response.data = MOCK_USER_STATS
    supabase_service.client.table().select().eq().eq().execute.return_value = mock_response
    
    # Call the method
    stats = await supabase_service.get_user_stats(
        user_id="user_123",
        sport="basketball"
    )
    
    # Verify the response
    assert len(stats) == 1
    stat = stats[0]
    assert isinstance(stat, UserStats)
    assert stat.user_id == "user_123"
    assert stat.total_entries == 50
    assert stat.won_entries == 28
    assert stat.roi == 0.15

@pytest.mark.asyncio
@observe(name="test_supabase_similar_bets")
async def test_get_similar_bets(supabase_service):
    """Test getting similar bets with Langfuse tracing"""
    # Mock the Supabase response
    mock_response = MagicMock()
    mock_response.data = MOCK_SIMILAR_BETS
    supabase_service.client.table().select().eq().eq().gte().execute.return_value = mock_response
    
    # Call the method
    bets = await supabase_service.get_similar_bets(
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
    assert bet.odds == 2.0
    assert bet.metadata["team"] == "Boston Celtics"

@pytest.mark.asyncio
@observe(name="test_supabase_error_handling")
async def test_error_handling(supabase_service):
    """Test error handling in the service with Langfuse tracing"""
    # Mock a database error
    supabase_service.client.table().select().eq().gte().execute.side_effect = Exception("Database Error")
    
    # Test error handling for each method
    with pytest.raises(Exception):
        await supabase_service.get_user_bets("user_123")
    
    with pytest.raises(Exception):
        await supabase_service.get_user_stats("user_123")
    
    with pytest.raises(Exception):
        await supabase_service.get_similar_bets("basketball", "moneyline")

@pytest.mark.asyncio
@observe(name="test_supabase_date_filtering")
async def test_date_filtering(supabase_service):
    """Test date filtering in queries with Langfuse tracing"""
    # Mock the Supabase response
    mock_response = MagicMock()
    mock_response.data = MOCK_BET_HISTORY
    supabase_service.client.table().select().eq().gte().execute.return_value = mock_response
    
    # Test different date ranges
    days_back_values = [7, 30, 90]
    for days in days_back_values:
        await supabase_service.get_user_bets(
            user_id="user_123",
            sport="basketball",
            days_back=days
        )
        
        # Verify the date filter was applied
        expected_date = datetime.now(UTC) - timedelta(days=days)
        calls = supabase_service.client.table().select().eq().gte.call_args_list
        assert expected_date.strftime("%Y-%m-%d") in str(calls[-1])

@pytest.mark.asyncio
@observe(name="test_supabase_metadata_handling")
async def test_metadata_handling(supabase_service):
    """Test handling of metadata in bet history with Langfuse tracing"""
    # Mock the Supabase response with complex metadata
    mock_response = MagicMock()
    mock_response.data = [{
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
    supabase_service.client.table().select().eq().gte().execute.return_value = mock_response
    
    # Call the method
    bets = await supabase_service.get_user_bets(
        user_id="user_123",
        sport="basketball",
        days_back=30
    )
    
    # Verify metadata handling
    bet = bets[0]
    assert isinstance(bet.metadata, dict)
    assert bet.metadata["team"] == "Los Angeles Lakers"
    assert isinstance(bet.metadata["analysis"], dict)
    assert isinstance(bet.metadata["odds_history"], list)
    assert len(bet.metadata["odds_history"]) == 2

@pytest.mark.asyncio
@observe(name="test_supabase_roi_calculation")
async def test_roi_calculation(supabase_service):
    """Test ROI calculation in user stats with Langfuse tracing"""
    # Mock the Supabase response with different ROI scenarios
    mock_response = MagicMock()
    mock_response.data = [
        {
            **MOCK_USER_STATS[0],
            "total_stake": 1000.0,
            "total_payout": 1150.0,
            "roi": 0.15
        },
        {
            **MOCK_USER_STATS[0],
            "period": "all_time",
            "total_stake": 5000.0,
            "total_payout": 4750.0,
            "roi": -0.05
        }
    ]
    supabase_service.client.table().select().eq().eq().execute.return_value = mock_response
    
    # Call the method
    stats = await supabase_service.get_user_stats(
        user_id="user_123",
        sport="basketball"
    )
    
    # Verify ROI calculations
    assert len(stats) == 2
    assert stats[0].roi == 0.15  # Positive ROI
    assert stats[1].roi == -0.05  # Negative ROI
    assert stats[0].total_payout - stats[0].total_stake == 150.0  # Profit
    assert stats[1].total_payout - stats[1].total_stake == -250.0  # Loss 