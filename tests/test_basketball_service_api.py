import asyncio
from datetime import datetime, timezone, timedelta
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
    DataPoint,
    Message
)
from app.config import get_logger
import json
from app.services.basketball_service import BasketballService
from app.utils.test_utils import create_test_metadata
from loguru import logger

logger = get_logger(__name__)

# Test query patterns
TIME_BASED_QUERIES = [
    "Show me Lakers games tonight",
    "How did the Celtics play yesterday",
    "Show me Nuggets games this Friday",
    "Get me stats from last Wednesday's Suns game",
    "Show me Lakers games this week",
    "How did the Nets perform last week",
    "What games are on this weekend",
    "How did the Warriors do last weekend",
    "Show me Lakers performance from 3 days ago"
]

COMPARISON_QUERIES = [
    "Compare Bucks vs Celtics stats for next week",
    "Compare Lakers performance tonight vs last week",
    "Compare Nuggets vs Suns stats 2 weeks from now"
]

PREDICTION_QUERIES = [
    "Show me Warriors stats from yesterday and predictions for next Friday",
    "Show me upcoming Lakers games",
    "What are the next Warriors games",
    "Get me recent Celtics performance"
]

ERROR_QUERIES = [
    "Show me games from 2025",  # Future date
    "Get me stats for the invalid team",  # Invalid team
    "Compare Lakers vs",  # Incomplete comparison
    "Show me games from last century"  # Out of range date
]

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
        else:
            print(f"Content Type: {type(dp.content)}")

def create_test_metadata(timezone: str = "America/New_York", days_offset: int = 0) -> ClientMetadata:
    """Create test client metadata with configurable date"""
    base_time = datetime.now(pytz.timezone(timezone)) + timedelta(days=days_offset)
    return ClientMetadata(
        timestamp=base_time,
        timezone=timezone,
        locale="en-US"
    )

@pytest.mark.asyncio
async def test_time_based_queries():
    """Test queries with different time references"""
    log_separator("Testing Time-Based Queries")
    
    async with ResearchChain() as chain:
        for query in TIME_BASED_QUERIES:
            log_test_case(query)
            
            # Test with different time offsets
            for days_offset in [0, -1, 1]:  # Today, yesterday, tomorrow
                client_metadata = create_test_metadata(days_offset=days_offset)
                
                request = ResearchRequest(
                    query=query,
                    mode=ResearchMode.QUICK,
                    client_metadata=client_metadata,
                    context=ConversationContext(
                        sport=SportType.BASKETBALL,
                        required_data=["team_stats", "recent_games"]
                    ),
                    trace_id=f"test_time_{days_offset}"
                )
                
                response = await chain.process_request(request)
                log_api_response(response.data_points, f"Response (offset: {days_offset} days)")
                
                # Verify response
                assert response.response, "Response should not be empty"
                assert any(dp.source == "basketball_api" for dp in response.data_points), "Should have basketball API data"
                assert any(dp.source == "perplexity" for dp in response.data_points), "Should have web search data"

@pytest.mark.asyncio
async def test_comparison_queries():
    """Test team comparison queries"""
    log_separator("Testing Comparison Queries")
    
    async with ResearchChain() as chain:
        for query in COMPARISON_QUERIES:
            log_test_case(query)
            
            request = ResearchRequest(
                query=query,
                mode=ResearchMode.DEEP,  # Use DEEP mode for comparisons
                client_metadata=create_test_metadata(),
                context=ConversationContext(
                    sport=SportType.BASKETBALL,
                    required_data=["team_stats", "recent_games", "matchup_history"]
                ),
                trace_id="test_comparison"
            )
            
            response = await chain.process_request(request)
            log_api_response(response.data_points, "Comparison Response")
            
            # Verify comparison data
            basketball_data = [dp for dp in response.data_points if dp.source == "basketball_api"]
            assert len(basketball_data) >= 2, "Should have data for at least two teams"
            
            # Verify transformed data structure
            for dp in basketball_data:
                if isinstance(dp.content, dict):
                    assert any(key in dp.content for key in ["team_data", "game_data", "season_stats"]), \
                        "Should have either team data, game data, or season stats"

@pytest.mark.asyncio
async def test_prediction_queries():
    """Test prediction and upcoming game queries"""
    log_separator("Testing Prediction Queries")
    
    async with ResearchChain() as chain:
        for query in PREDICTION_QUERIES:
            log_test_case(query)
            
            request = ResearchRequest(
                query=query,
                mode=ResearchMode.DEEP,
                client_metadata=create_test_metadata(),
                context=ConversationContext(
                    sport=SportType.BASKETBALL,
                    required_data=["team_stats", "recent_games", "upcoming_games"]
                ),
                trace_id="test_prediction"
            )
            
            response = await chain.process_request(request)
            log_api_response(response.data_points, "Prediction Response")
            
            # Verify prediction data
            assert response.response, "Response should not be empty"
            assert any(dp.source == "basketball_api" for dp in response.data_points), "Should have basketball API data"
            assert any(dp.source == "perplexity" for dp in response.data_points), "Should have web search data"
            
            # Check for suggested questions
            assert response.suggested_questions, "Should have suggested follow-up questions"
            assert len(response.suggested_questions) >= 2, "Should have at least 2 suggested questions"

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling for various edge cases"""
    log_separator("Testing Error Handling")
    
    async with ResearchChain() as chain:
        for query in ERROR_QUERIES:
            log_test_case(query)
            
            request = ResearchRequest(
                query=query,
                mode=ResearchMode.QUICK,
                client_metadata=create_test_metadata(),
                context=ConversationContext(
                    sport=SportType.BASKETBALL,
                    required_data=["team_stats"]
                ),
                trace_id="test_error"
            )
            
            try:
                response = await chain.process_request(request)
                log_api_response(response.data_points, "Error Case Response")
                
                # Verify error handling
                assert response.response, "Should have a response even for error cases"
                assert response.confidence_score < 0.7, "Confidence should be lower for error cases"
                
                # Check for error indicators in data points
                error_found = False
                for dp in response.data_points:
                    if isinstance(dp.content, dict) and "error" in dp.content:
                        error_found = True
                        break
                assert error_found, "Should have error indication in data points"
                
            except Exception as e:
                # Some errors should be caught and handled gracefully
                logger.error(f"Expected error in error test case: {str(e)}")
                assert str(e), "Error should have a message"

@pytest.mark.asyncio
async def test_mode_switching():
    """Test automatic mode switching based on query complexity"""
    log_separator("Testing Mode Switching")
    
    async with ResearchChain() as chain:
        # Test simple query that should use QUICK mode
        simple_request = ResearchRequest(
            query="Show me Lakers games tonight",
            mode=ResearchMode.AUTO,
            client_metadata=create_test_metadata(),
            context=ConversationContext(sport=SportType.BASKETBALL),
            trace_id="test_mode_simple"
        )
        
        simple_response = await chain.process_request(simple_request)
        log_api_response(simple_response.data_points, "Simple Query Response")
        
        # Test complex query that should use DEEP mode
        complex_request = ResearchRequest(
            query="Compare Lakers vs Warriors performance trends and predict their next matchup outcome based on recent games",
            mode=ResearchMode.AUTO,
            client_metadata=create_test_metadata(),
            context=ConversationContext(sport=SportType.BASKETBALL),
            trace_id="test_mode_complex"
        )
        
        complex_response = await chain.process_request(complex_request)
        log_api_response(complex_response.data_points, "Complex Query Response")
        
        # Verify mode selection
        assert len(simple_response.data_points) <= len(complex_response.data_points), \
            "Complex query should have more data points"
        
        # Verify data transformation
        assert any(dp.source == "basketball_api" for dp in simple_response.data_points), \
            "Simple query should have basketball API data"
        assert any(dp.source == "perplexity" for dp in complex_response.data_points), \
            "Complex query should have web search data"

@pytest.mark.asyncio
async def test_conversation_context():
    """Test conversation context handling and updates"""
    log_separator("Testing Conversation Context")
    
    async with ResearchChain() as chain:
        # Initial query
        context = ConversationContext(
            teams=["Los Angeles Lakers"],
            sport=SportType.BASKETBALL,
            required_data=["team_stats"]
        )
        
        initial_request = ResearchRequest(
            query="How are the Lakers playing?",
            mode=ResearchMode.QUICK,
            client_metadata=create_test_metadata(),
            context=context,
            trace_id="test_context_1"
        )
        
        initial_response = await chain.process_request(initial_request)
        
        # Follow-up query using context
        follow_up_request = ResearchRequest(
            query="What about their next game?",
            mode=ResearchMode.QUICK,
            client_metadata=create_test_metadata(),
            context=initial_response.context_updates,  # Use context updates from previous response
            conversation_history=[
                Message(role="user", content="How are the Lakers playing?"),
                Message(role="assistant", content=initial_response.response)
            ],
            trace_id="test_context_2"
        )
        
        follow_up_response = await chain.process_request(follow_up_request)
        
        # Verify context handling
        assert follow_up_response.response, "Follow-up response should not be empty"
        assert "Lakers" in str(follow_up_response.response), "Follow-up should maintain team context"
        assert any(dp.source == "basketball_api" for dp in follow_up_response.data_points), \
            "Should have basketball API data in follow-up"

@pytest.mark.asyncio
async def test_schedule_query():
    """Test a single schedule query to debug data flow"""
    log_separator("Testing Schedule Query")
    
    async with BasketballService() as service:
        # Test dates
        test_dates = ["2025-03-04", "2025-03-07", "2025-03-10"]
        current_season = "2024"  # 2023-24 season
        
        # First try without team filter to see all games
        for test_date in test_dates:
            games = await service.games.list_games(
                date=test_date,
                league="standard",
                season=current_season
            )
            print(f"\nFound {len(games)} total games for {test_date}")
            
            if games:
                # Print first game details for debugging
                game = games[0]
                print("\nGame details:")
                print(f"Game ID: {game.id}")
                print(f"Date: {game.date}")
                print(f"Teams: {game.teams}")
                print(f"Status: {game.status}")
                
                # Validate game structure
                assert isinstance(game.id, int), "Game ID should be an integer"
                assert isinstance(game.date.get('start'), str), "Game start date should be a string"
                assert isinstance(game.teams, dict), "Teams should be a dictionary"
                assert 'visitors' in game.teams, "Game should have visitors team"
                assert 'home' in game.teams, "Game should have home team"
                assert isinstance(game.teams['visitors'].get('name'), str), "Team name should be a string"
                assert isinstance(game.teams['home'].get('name'), str), "Team name should be a string"
        
        # Now try with Lakers filter
        lakers_games = []
        for test_date in test_dates:
            games = await service.games.list_games(
                date=test_date,
                league="standard",
                season=current_season,
                team_id=17
            )
            print(f"\nFound {len(games)} Lakers games for {test_date}")
            lakers_games.extend(games)
        
        # Verify we found at least one Lakers game
        assert len(lakers_games) > 0, "Should have found at least one Lakers game"
        
        # Verify Lakers game structure
        lakers_game = lakers_games[0]
        assert any(team.get('name') == "Los Angeles Lakers" 
                  for team in [lakers_game.teams['visitors'], lakers_game.teams['home']]), \
            "Should have found Lakers in the teams"

async def main():
    """Run all test functions"""
    try:
        await test_time_based_queries()
        await test_comparison_queries()
        await test_prediction_queries()
        await test_error_handling()
        await test_mode_switching()
        await test_conversation_context()
        await test_schedule_query()
    except Exception as e:
        logger.error("Test suite failed", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 