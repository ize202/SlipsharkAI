#!/usr/bin/env python
"""
Test script for the research workflow.
This script tests the entire research chain from query to response.
"""

import os
import sys

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

import json
import asyncio
import logging
import argparse
from datetime import datetime
import time
from typing import Dict, Any
from app.services.basketball_service import BasketballService
from app.config import get_logger

# Configure logging
logger = get_logger(__name__)

# Check for required environment variables
REQUIRED_ENV_VARS = [
    "NBA_API_KEY",
    "NBA_API_HOST",
    "REDIS_URL"
]

for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        logger.error(f"Missing required environment variable: {var}")
        sys.exit(1)
logger.debug("All required environment variables are set")

async def test_league_standings():
    """Test getting league standings"""
    async with BasketballService() as basketball_service:
        # Get league standings
        league_data = await basketball_service.get_league_data(limit_games=1)
        if isinstance(league_data, dict) and "response" in league_data:
            standings_data = league_data.get("response", [])
            if standings_data and len(standings_data) > 0:
                print("Current NBA Standings:")
                print(json.dumps(standings_data, indent=2))
            else:
                print("No standings data found")
                sys.exit(1)
        else:
            print("Failed to get league data")
            sys.exit(1)

async def test_game_statistics():
    """Test getting game statistics"""
    async with BasketballService() as basketball_service:
        # First get a recent game ID
        league_data = await basketball_service.get_league_data(limit_games=1)
        if isinstance(league_data, dict) and "response" in league_data:
            standings_data = league_data.get("response", [])
            if standings_data and len(standings_data) > 0:
                # Use a hardcoded game ID for testing
                game_id = 10403  # Example game ID from the API documentation
                # Get game statistics
                game_stats = await basketball_service.get_game_statistics(game_id)
                print(f"Game statistics for game {game_id}:")
                print(json.dumps(game_stats, indent=2))
            else:
                print("No standings data found")
                sys.exit(1)
        else:
            print("Failed to get league data")
            sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run workflow tests")
    parser.add_argument("--query", type=str, help="Query type to test", required=True)
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    
    async def main():
        if args.query == "league_standings":
            await test_league_standings()
        elif args.query == "game_stats":
            await test_game_statistics()
        else:
            print(f"Invalid query type: {args.query}")
            sys.exit(2)
    
    loop.run_until_complete(main())
