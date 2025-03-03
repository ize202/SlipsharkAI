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
    ConversationContext
)
from app.config import get_logger
import json
from app.services.basketball_service import BasketballService

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

def create_test_metadata() -> ClientMetadata:
    """Create test client metadata"""
    return ClientMetadata(
        user_id="test_user",
        timezone="America/New_York",
        preferences={
            "favorite_teams": ["Los Angeles Lakers", "Boston Celtics"],
            "favorite_players": ["LeBron James", "Jayson Tatum"]
        }
    )

@pytest.mark.asyncio
async def test_team_queries():
    log_separator("TESTING TEAM QUERIES")
    client_metadata = create_test_metadata()
    
    async with ResearchChain() as chain:
        test_cases = [
            ("Lakers today", "Lakers", None, "today"),
            ("Celtics next game", "Celtics", None, "next game"),
            ("Warriors last 5 games", "Warriors", None, "last 5 games"),
            ("Nets upcoming schedule", "Nets", None, "upcoming schedule"),
        ]
        
        for description, team, player, date_ref in test_cases:
            log_test_case(description)
            try:
                logger.info(f"Creating analysis for team: {team}, date_ref: {date_ref}")
                
                # Create analysis object
                analysis = QueryAnalysis(
                    raw_query=f"How are the {team} playing {date_ref}?",
                    teams={"team1": team},
                    players=[],
                    game_date=date_ref,
                    recommended_mode=ResearchMode.DEEP,
                    sport_type=SportType.BASKETBALL,
                    query_type="team_performance",
                    confidence_score=0.9
                )
                
                # Create research request
                request = ResearchRequest(
                    query=f"How are the {team} playing {date_ref}?",
                    mode=ResearchMode.DEEP,
                    client_metadata=client_metadata,
                    context=ConversationContext()
                )
                
                logger.info("Making API request...")
                data_points = await chain._gather_data(analysis, request)
                logger.info(f"Received {len(data_points)} data points")
                
                log_api_response(data_points)
                
                # Validate response data
                for dp in data_points:
                    if isinstance(dp.content, dict) and "games" in dp.content:
                        if not dp.content["games"]:
                            logger.warning(f"No games found for {team} with date_ref: {date_ref}")
                        else:
                            logger.info(f"Successfully found {len(dp.content['games'])} games")
                            
            except Exception as e:
                logger.error(f"Error in test case {description}: {str(e)}", exc_info=True)
                raise

@pytest.mark.asyncio
async def test_player_queries():
    log_separator("TESTING PLAYER QUERIES")
    client_metadata = create_test_metadata()
    
    async with ResearchChain() as chain:
        test_cases = [
            ("LeBron recent", "Lakers", "LeBron James", "last 5 games"),
            ("Tatum stats", "Celtics", "Jayson Tatum", "this season"),
            ("Curry performance", "Warriors", "Stephen Curry", "recent"),
            ("Durant analysis", "Suns", "Kevin Durant", "today"),
        ]
        
        for description, team, player, date_ref in test_cases:
            log_test_case(description)
            try:
                logger.info(f"Creating analysis for player: {player}, team: {team}, date_ref: {date_ref}")
                
                # Create analysis object
                analysis = QueryAnalysis(
                    raw_query=f"How is {player} playing {date_ref}?",
                    teams={"team1": team},
                    players=[player],
                    game_date=date_ref,
                    recommended_mode=ResearchMode.DEEP,
                    sport_type=SportType.BASKETBALL,
                    query_type="player_performance",
                    confidence_score=0.9
                )
                
                # Create research request
                request = ResearchRequest(
                    query=f"How is {player} playing {date_ref}?",
                    mode=ResearchMode.DEEP,
                    client_metadata=client_metadata,
                    context=ConversationContext()
                )
                
                logger.info("Making API request...")
                data_points = await chain._gather_data(analysis, request)
                logger.info(f"Received {len(data_points)} data points")
                
                log_api_response(data_points)
                
                # Validate player statistics
                for dp in data_points:
                    if isinstance(dp.content, dict):
                        if "player" in dp.content and "statistics" in dp.content:
                            logger.info(f"Successfully found statistics for {player}")
                        else:
                            logger.warning(f"Missing player statistics for {player}")
                            
            except Exception as e:
                logger.error(f"Error in test case {description}: {str(e)}", exc_info=True)
                raise

@pytest.mark.asyncio
async def test_matchup_queries():
    log_separator("TESTING MATCHUP QUERIES")
    client_metadata = create_test_metadata()
    
    async with ResearchChain() as chain:
        test_cases = [
            ("Lakers vs Celtics", "Lakers", "Celtics", "head to head"),
            ("Warriors vs Suns", "Warriors", "Suns", "last 5 matchups"),
            ("Bucks vs Heat", "Bucks", "Heat", "next game"),
        ]
        
        for description, team1, team2, date_ref in test_cases:
            log_test_case(description)
            try:
                logger.info(f"Creating analysis for matchup: {team1} vs {team2}, date_ref: {date_ref}")
                
                # Create analysis object
                analysis = QueryAnalysis(
                    raw_query=f"Compare {team1} vs {team2} {date_ref}",
                    teams={"team1": team1, "team2": team2},
                    players=[],
                    game_date=date_ref,
                    recommended_mode=ResearchMode.DEEP,
                    sport_type=SportType.BASKETBALL,
                    query_type="matchup_analysis",
                    confidence_score=0.9
                )
                
                # Create research request
                request = ResearchRequest(
                    query=f"Compare {team1} vs {team2} {date_ref}",
                    mode=ResearchMode.DEEP,
                    client_metadata=client_metadata,
                    context=ConversationContext()
                )
                
                logger.info("Making API request...")
                data_points = await chain._gather_data(analysis, request)
                logger.info(f"Received {len(data_points)} data points")
                
                log_api_response(data_points)
                
                # Validate matchup data
                for dp in data_points:
                    if isinstance(dp.content, dict) and "games" in dp.content:
                        if not dp.content["games"]:
                            logger.warning(f"No matchup data found for {team1} vs {team2} with date_ref: {date_ref}")
                        else:
                            logger.info(f"Successfully found {len(dp.content['games'])} matchups")
                            
            except Exception as e:
                logger.error(f"Error in test case {description}: {str(e)}", exc_info=True)
                raise

@pytest.mark.asyncio
async def test_get_team_data():
    """Test retrieving team data"""
    log_test_case("Team Data Retrieval")

    metadata = create_test_metadata()
    
    async with BasketballService() as service:
        # Test getting Lakers team data
        team_data = await service.get_team_data("Los Angeles Lakers", metadata)
        log_api_response(team_data, "Lakers Team Data")

        assert team_data is not None
        assert "id" in team_data

@pytest.mark.asyncio
async def test_get_player_data():
    """Test retrieving player data"""
    log_test_case("Player Data Retrieval")

    metadata = create_test_metadata()
    
    async with BasketballService() as service:
        # Test getting LeBron James data
        player_data = await service.get_player_data(
            player_name="LeBron James",
            team_name="Los Angeles Lakers",
            client_metadata=metadata
        )
        log_api_response(player_data, "LeBron James Player Data")

        assert player_data is not None
        assert "error" not in player_data
        assert "player" in player_data
        assert "statistics" in player_data
        assert isinstance(player_data["statistics"], list)
        
        # Verify player info
        assert player_data["player"]["firstname"] == "LeBron"
        assert player_data["player"]["lastname"] == "James"

@pytest.mark.asyncio
async def test_get_game_data():
    """Test retrieving game data"""
    log_test_case("Game Data Retrieval")

    metadata = create_test_metadata()
    
    async with BasketballService() as service:
        # Test getting recent games
        games = await service.get_games("recent", metadata)
        log_api_response({"games": games}, "Recent Games")

        assert games is not None
        assert isinstance(games, list)
        assert len(games) > 0

@pytest.mark.asyncio
async def test_get_matchups():
    """Test retrieving matchup data"""
    log_test_case("Matchup Data Retrieval")
    
    service = BasketballService()
    metadata = create_test_metadata()
    
    # Test getting matchups between Lakers and Celtics
    matchups = await service.get_matchups("Los Angeles Lakers", "Boston Celtics", metadata)
    log_api_response({"matchups": matchups}, "Lakers vs Celtics Matchups")
    
    assert matchups is not None
    assert isinstance(matchups, list)
    
    if len(matchups) > 0:
        matchup = matchups[0]
        assert "id" in matchup
        assert "date" in matchup
        assert "teams" in matchup
        assert "home" in matchup["teams"]
        assert "away" in matchup["teams"]
        assert "scores" in matchup
        
        # Verify teams are correct
        teams = {matchup["teams"]["home"]["name"], matchup["teams"]["away"]["name"]}
        assert "Los Angeles Lakers" in teams
        assert "Boston Celtics" in teams

@pytest.mark.asyncio
async def test_get_league_data():
    """Test retrieving league data"""
    log_test_case("League Data Retrieval")

    metadata = create_test_metadata()
    
    async with BasketballService() as service:
        # Test getting NBA league data
        league_data = await service.get_league_data(metadata)
        log_api_response(league_data, "NBA League Data")

        assert league_data is not None
        assert "id" in league_data

@pytest.mark.asyncio
async def test_date_handling():
    """Test date handling in game queries"""
    log_test_case("Date Handling in Game Queries")
    
    service = BasketballService()
    metadata = create_test_metadata()
    
    # Test different date references
    date_refs = [
        "today",
        "yesterday",
        "tomorrow",
        "last 5 games",
        "next 3 games",
        "this season"
    ]
    
    for date_ref in date_refs:
        games = await service.get_games(date_ref, metadata)
        log_api_response({"games": games}, f"Games for date reference: {date_ref}")
        
        assert games is not None
        assert isinstance(games, list)
        
        if len(games) > 0:
            game = games[0]
            assert "id" in game
            assert "date" in game
            
            # Verify date is within current season
            game_date = datetime.fromisoformat(game["date"].replace("Z", "+00:00"))
            current_date = datetime.now(timezone.utc)
            
            # Game should not be more than a year old
            date_diff = current_date - game_date
            assert date_diff.days <= 365, f"Game date {game_date} is too old for reference {date_ref}"

@pytest.mark.asyncio
async def test_api_error_handling():
    """Test error handling for API calls"""
    log_separator("TESTING API ERROR HANDLING")

    metadata = create_test_metadata()
    
    async with BasketballService() as service:
        # Test invalid team name
        log_test_case("Invalid Team Name")
        team_data = await service.get_team_data("Invalid Team Name", metadata)
        log_api_response(team_data, "Invalid Team Data")
        assert "error" in team_data

@pytest.mark.asyncio
async def test_season_handling():
    """Test season determination and boundaries"""
    log_separator("TESTING SEASON HANDLING")

    metadata = create_test_metadata()
    
    async with BasketballService() as service:
        # Test current season data
        log_test_case("Current Season")
        league_data = await service.get_league_data(metadata)
        log_api_response(league_data, "Current Season Data")
        assert "season" in league_data

@pytest.mark.asyncio
async def test_game_statistics():
    """Test game statistics retrieval"""
    log_separator("TESTING GAME STATISTICS")
    
    service = BasketballService()
    metadata = create_test_metadata()
    
    # Get a recent game first
    games = await service.get_games("recent", metadata)
    if not games:
        logger.warning("No recent games found to test statistics")
        return
        
    game_id = games[0]["id"]
    
    # Test getting game statistics
    log_test_case(f"Game Statistics for ID: {game_id}")
    game_stats = await service.get_game_statistics(game_id)
    log_api_response(game_stats, "Game Statistics")
    
    assert game_stats is not None
    assert "game_id" in game_stats
    assert "statistics" in game_stats
    assert "timestamp" in game_stats
    assert "confidence" in game_stats
    
    # Verify statistics structure
    stats = game_stats["statistics"]
    if stats and not isinstance(stats, dict):  # If not error response
        for team_stats in stats:
            assert "team" in team_stats
            assert "statistics" in team_stats
            team_game_stats = team_stats["statistics"][0]
            
            # Check for required statistical fields
            required_fields = [
                "fastBreakPoints", "pointsInPaint", "biggestLead",
                "points", "fgm", "fga", "fgp", "ftm", "fta", "ftp",
                "tpm", "tpa", "tpp", "offReb", "defReb", "totReb",
                "assists", "pFouls", "steals", "turnovers", "blocks"
            ]
            
            for field in required_fields:
                assert field in team_game_stats

@pytest.mark.asyncio
async def test_player_statistics():
    """Test player statistics retrieval with various filters"""
    log_separator("TESTING PLAYER STATISTICS")

    metadata = create_test_metadata()
    
    async with BasketballService() as service:
        # Test cases for different player statistics scenarios
        test_cases = [
            ("LeBron James", "Los Angeles Lakers", "today"),
            ("Jayson Tatum", "Boston Celtics", "last 5 games"),
            ("Stephen Curry", "Golden State Warriors", "this season"),
        ]

        for player_name, team_name, date_ref in test_cases:
            log_test_case(f"Player Stats: {player_name} - {date_ref}")

            try:
                player_data = await service.get_player_data(
                    player_name=player_name,
                    team_name=team_name,
                    game_date=date_ref,
                    client_metadata=metadata
                )

                log_api_response(player_data, f"{player_name} Stats")
                assert player_data is not None
                assert "error" not in player_data
                assert "player" in player_data
                assert "statistics" in player_data
                assert isinstance(player_data["statistics"], list)

                # Verify player info
                player_info = player_data["player"]
                assert player_info["firstname"] in player_name
                assert player_info["lastname"] in player_name

            except Exception as e:
                logger.error(f"Error testing player statistics for {player_name}: {str(e)}")
                raise

async def main():
    """Run all test functions including new ones"""
    try:
        # Existing tests
        await test_team_queries()
        await test_player_queries()
        await test_matchup_queries()
        await test_get_team_data()
        await test_get_player_data()
        await test_get_game_data()
        await test_get_matchups()
        await test_get_league_data()
        await test_date_handling()
        
        # New tests
        await test_api_error_handling()
        await test_season_handling()
        await test_game_statistics()
        await test_player_statistics()
    except Exception as e:
        logger.error("Test suite failed", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 