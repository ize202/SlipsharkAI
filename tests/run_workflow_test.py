#!/usr/bin/env python
"""
Test script for the research workflow.
This script tests the entire research chain from query to response.
"""

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from pprint import pprint
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def print_section(title: str, content: any) -> None:
    """Print a formatted section with title and content."""
    print(f"\n{title}:")
    print("=" * (len(title) + 1))
    if isinstance(content, list):
        for item in content:
            print(f"- {item}")
    else:
        print(content)
    print()

# Add the parent directory to the path so we can import the app modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
logger.debug(f"Added parent directory to path: {parent_dir}")
logger.debug(f"Current PYTHONPATH: {sys.path}")

# Check for required environment variables
REQUIRED_ENV_VARS = [
    'OPENAI_API_KEY',
    'SUPABASE_URL',
    'SUPABASE_KEY',
    'PERPLEXITY_API_KEY',
    'API_SPORTS_KEY'
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {missing_vars}")
    sys.exit(1)
else:
    logger.debug("All required environment variables are set")

try:
    from app.models.research_models import ResearchRequest, ResearchMode, SportType, ResearchContext
    from app.workflows.research_chain import ResearchChain
    logger.debug("Successfully imported required modules")
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

# Test queries for different scenarios
TEST_QUERIES = {
    "deep_matchup": "Should I bet on the Lakers vs Warriors game tonight? I need a detailed analysis of their head-to-head matchups, team stats, and current form.",
    "deep_player_impact": "How will LeBron's injury affect the Lakers' chances against the Timberwolves? Need comprehensive analysis of team performance with and without him.",
    "deep_team_form": "Do a deep analysis of the Celtics' current form, their last 5 games performance, and upcoming matchup against the Bucks.",
    "deep_standings": "Analyze the Warriors' playoff chances based on their current standing, remaining schedule, and recent performance trends.",
    "deep_scoring": "Should I bet the over/under for the Nuggets vs Suns game? Need detailed scoring trends and defensive stats for both teams.",
    # Adding new test queries for different endpoints
    "player_stats": "What are Giannis Antetokounmpo's stats in the last 5 games? Need his scoring, rebounds, and efficiency numbers.",
    "team_comparison": "Compare the Nets and Heat's defensive stats this season, especially their points allowed and opponent field goal percentage.",
    "injury_impact": "With Joel Embiid out, how have the 76ers performed in games without him this season?",
    "h2h_analysis": "What's the head-to-head record between the Knicks and Bulls this season? Include scoring margins and key player performances.",
    "season_trends": "How have the Grizzlies performed against the spread in their last 10 home games?",
    "player_props": "What's Luka Doncic's average points, assists, and rebounds in games against the Pelicans this season?",
    "team_streaks": "Are the Thunder on any significant winning or scoring streaks? Need their last 10 games performance.",
    "division_stats": "How are the teams in the Pacific Division performing against each other this season?",
    "league_overview": "Give me a comprehensive overview of the current NBA season standings, including division leaders and recent game results.",
    "season_info": "What NBA seasons are available in the database? I need historical season data.",
    "league_info": "What different NBA leagues and competitions are available in the database?",
    "team_deep_stats": "I need detailed offensive and defensive statistics for the Boston Celtics this season, including fast break points and points in the paint.",
    "game_full_stats": "Show me the complete statistical breakdown of the last Lakers vs Warriors game, including player performances and team stats.",
    "league_standings": "Show me the current NBA standings with win-loss records and streaks",
    "recent_games": "What are the most recent NBA game results?"
}

# Default to deep research mode for all queries to ensure we test the sports API integration
DEFAULT_MODE = ResearchMode.DEEP

async def process_request(query: str, mode: ResearchMode = ResearchMode.AUTO) -> Dict[str, Any]:
    """Process a research request and print the results."""
    logger.info("\n" + "=" * 80)
    logger.info(f"TESTING QUERY: '{query}'")
    logger.info(f"MODE: {mode}")
    logger.info("=" * 80 + "\n")

    # Create research request
    request = ResearchRequest(
        query=query,
        mode=mode,
        context=ResearchContext(
            user_id="test_user_123",
            session_id="test_session_456",
            previous_queries=[],
            preferences={},
            bet_history=[]
        )
    )
    
    logger.debug(f"Created research request: {request}")
    logger.debug("Initializing ResearchChain")
    
    # Initialize chain and process request
    async with ResearchChain() as chain:
        logger.info("Processing request...")
        start_time = time.time()
        result = await chain.process_request(request)
        processing_time = time.time() - start_time
        
        # Log raw data field
        logger.debug(f"Raw data field: {result.data}")
        
        logger.debug("Request processed successfully")
        logger.info(f"\nRESULTS (processed in {processing_time:.2f} seconds):")
        logger.info(f"Mode used: {result.metadata.mode_used}")
        logger.info(f"Confidence score: {result.metadata.confidence_score:.2f}\n")

        # Print sections
        print_section("SUMMARY", result.summary)
        
        if result.recommendations:
            print_section("RECOMMENDATIONS", result.recommendations)
            
        if result.risk_factors:
            print_section("RISK FACTORS", [f"{rf.factor} ({rf.severity}): {rf.mitigation}" for rf in result.risk_factors])
            
        if result.sources:
            print_section("SOURCES", [f"{source.name} ({source.type})" for source in result.sources])
            
            # For league data testing, print detailed standings if available
            if "league_data_basketball" in result.data:
                league_data = result.data["league_data_basketball"]
                standings_data = league_data.get("standings", [])
                if standings_data:
                    print("\nSTANDINGS DATA")
                    print("=" * 80)
                    print(f"{'Team':<30} {'W-L':<10} {'Win%':<8} {'Last 10':<10} {'Streak':<8} {'Conf':<15}")
                    print("-" * 80)
                    
                    # Sort standings by win percentage
                    sorted_standings = sorted(standings_data, 
                                           key=lambda x: x['winPercentage'], 
                                           reverse=True)
                    
                    for team in sorted_standings:
                        print(f"{team['team']:<30} "
                              f"{team['win']}-{team['loss']:<8} "
                              f"{team['winPercentage']:.3f}  "
                              f"{team['lastTenWin']}-{team['lastTenLoss']:<6} "
                              f"{'W' if team['winStreak'] else 'L'}{team['streak']:<6} "
                              f"{team['conference']}")
                    print("=" * 80)
                    
                    # Print recent games if available
                    recent_games = league_data.get("recent_games", [])
                    if recent_games and not isinstance(recent_games, dict):  # Check it's not an error dict
                        print("\nRECENT GAMES")
                        print("=" * 80)
                        for game in recent_games:
                            status = game['status'] or 'Unknown'
                            if game['home_score'] is not None and game['away_score'] is not None:
                                print(f"{game['date']}: {game['away_team']} {game['away_score']} @ {game['home_team']} {game['home_score']} ({status})")
                            else:
                                print(f"{game['date']}: {game['away_team']} @ {game['home_team']} ({status})")
                        print("=" * 80)

        return result

async def run_single_test(query: str, mode: ResearchMode = ResearchMode.AUTO) -> None:
    """Run a single test with the specified query"""
    print_section("TEST QUERY", query)
    
    start_time = time.time()
    result = await process_request(query, mode)
    processing_time = time.time() - start_time
    
    print_section("RESULTS", f"(processed in {processing_time:.2f} seconds):")
    print(f"Mode used: {result.metadata.mode_used}")
    print(f"Confidence score: {result.metadata.confidence_score:.2f}\n")
    
    if result.summary:
        print_section("SUMMARY", result.summary)
    
    if result.recommendations:
        print_section("RECOMMENDATIONS", result.recommendations)
    
    if result.risk_factors:
        print_section("RISK FACTORS", result.risk_factors)
    
    if result.sources:
        print_section("SOURCES", [f"{source.name} ({source.type})" for source in result.sources])
        
        # For league data testing, print detailed standings if available
        if "league_data_basketball" in result.data:
            league_data = result.data["league_data_basketball"]
            standings_data = league_data.get("standings", [])
            if standings_data:
                print("\nSTANDINGS DATA")
                print("=" * 80)
                print(f"{'Team':<30} {'W-L':<10} {'Win%':<8} {'Last 10':<10} {'Streak':<8} {'Conf':<15}")
                print("-" * 80)
                
                # Sort standings by win percentage
                sorted_standings = sorted(standings_data, 
                                       key=lambda x: x['winPercentage'], 
                                       reverse=True)
                
                for team in sorted_standings:
                    print(f"{team['team']:<30} "
                          f"{team['win']}-{team['loss']:<8} "
                          f"{team['winPercentage']:.3f}  "
                          f"{team['lastTenWin']}-{team['lastTenLoss']:<6} "
                          f"{'W' if team['winStreak'] else 'L'}{team['streak']:<6} "
                          f"{team['conference']}")
                print("=" * 80)
                
                # Print recent games if available
                recent_games = league_data.get("recent_games", [])
                if recent_games and not isinstance(recent_games, dict):  # Check it's not an error dict
                    print("\nRECENT GAMES")
                    print("=" * 80)
                    for game in recent_games:
                        status = game['status'] or 'Unknown'
                        if game['home_score'] is not None and game['away_score'] is not None:
                            print(f"{game['date']}: {game['away_team']} {game['away_score']} @ {game['home_team']} {game['home_score']} ({status})")
                        else:
                            print(f"{game['date']}: {game['away_team']} @ {game['home_team']} ({status})")
                    print("=" * 80)

async def run_all_tests() -> None:
    """Run all test queries"""
    for query_name, query in TEST_QUERIES.items():
        logger.info("=" * 80)
        logger.info(f"Testing query: {query_name}")
        logger.info("=" * 80)
        await run_single_test(query)
        logger.info("\n")

if __name__ == "__main__":
    # Get command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Test the research workflow')
    parser.add_argument('--query', type=str, choices=list(TEST_QUERIES.keys()), 
                        help='Specific query to test')
    parser.add_argument('--mode', type=str, choices=['auto', 'quick', 'deep'], default='auto',
                        help='Research mode to use')
    parser.add_argument('--all', action='store_true', help='Run all test queries')
    parser.add_argument('--custom', type=str, help='Custom query to test')
    
    args = parser.parse_args()
    
    # Set up the event loop
    loop = asyncio.get_event_loop()
    
    if args.all:
        # Run all tests
        loop.run_until_complete(run_all_tests())
    elif args.custom:
        # Run with custom query
        mode = ResearchMode.AUTO
        if args.mode == 'quick':
            mode = ResearchMode.QUICK
        elif args.mode == 'deep':
            mode = ResearchMode.DEEP
            
        loop.run_until_complete(process_request(args.custom, mode))
    elif args.query:
        # Run specific test query
        mode = ResearchMode.AUTO
        if args.mode == 'quick':
            mode = ResearchMode.QUICK
        elif args.mode == 'deep':
            mode = ResearchMode.DEEP
            
        loop.run_until_complete(process_request(TEST_QUERIES[args.query], mode))
    else:
        # Default: run quick basketball test
        loop.run_until_complete(run_single_test("quick_basketball"))
