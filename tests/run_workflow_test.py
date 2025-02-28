#!/usr/bin/env python
"""
Test script for the research workflow and basketball service.
Tests both the research chain and direct basketball service calls.
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from datetime import datetime
from typing import Dict, Any

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.services.basketball_service import BasketballService
from app.workflows.research_chain import ResearchChain
from app.models.research_models import ResearchRequest, ResearchMode, ConversationContext
from app.config import get_logger

# Configure logging
logger = get_logger(__name__)

# Check for required environment variables
REQUIRED_ENV_VARS = [
    "API_SPORTS_KEY",
    "API_SPORTS_HOST"
]

OPTIONAL_ENV_VARS = [
    "REDIS_URL"
]

for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        logger.error(f"Missing required environment variable: {var}")
        sys.exit(1)
logger.debug("All required environment variables are set")

async def test_basketball_service():
    """Test direct basketball service calls"""
    logger.info("Testing basketball service calls...")
    
    async with BasketballService() as basketball:
        tests = [
            # Test team data
            {
                "name": "Team Data Test",
                "func": basketball.get_team_data,
                "args": ["Lakers"]
            },
            # Test player data with team
            {
                "name": "Player Data Test",
                "func": basketball.get_player_data,
                "args": ["LeBron James", "Lakers"]  # Providing team name
            },
            # Test matchup data
            {
                "name": "Matchup Data Test",
                "func": basketball.get_matchup_data,
                "args": ["Lakers", "Warriors"]
            },
            # Test league data
            {
                "name": "League Data Test",
                "func": basketball.get_league_data,
                "args": [None, 5]
            }
        ]
        
        for test in tests:
            try:
                logger.info(f"\nRunning {test['name']}...")
                start_time = datetime.now()
                result = await test["func"](*test["args"])
                duration = (datetime.now() - start_time).total_seconds()
                
                print(f"\n{test['name']} Results:")
                print(f"Duration: {duration:.2f} seconds")
                print("Data:", json.dumps(result, indent=2))
                
            except Exception as e:
                logger.error(f"Error in {test['name']}: {str(e)}")

async def test_research_with_context():
    """Test research chain with specific context"""
    logger.info("Testing research chain with context...")
    
    test_cases = [
        {
            "name": "Team Performance Analysis",
            "query": "How are the Lakers performing this season?",
            "context": ConversationContext(
                teams=["Lakers"],
                sport="basketball"
            )
        },
        {
            "name": "Player Props Analysis",
            "query": "What's LeBron's scoring average in the last 5 games?",
            "context": ConversationContext(
                teams=["Lakers"],
                players=["LeBron James"],
                sport="basketball"
            )
        },
        {
            "name": "Matchup Analysis",
            "query": "Compare the Lakers and Warriors head to head stats this season",
            "context": ConversationContext(
                teams=["Lakers", "Warriors"],
                sport="basketball"
            )
        }
    ]
    
    async with ResearchChain() as chain:
        for test in test_cases:
            logger.info(f"\nRunning {test['name']}...")
            request = ResearchRequest(
                query=test["query"],
                mode=ResearchMode.DEEP,
                context=test["context"]
            )
            
            try:
                start_time = datetime.now()
                response = await chain.process_request(request)
                duration = (datetime.now() - start_time).total_seconds()
                
                print(f"\n{test['name']} Results:")
                print(f"Query: {test['query']}")
                print(f"Response: {response.response}")
                print(f"Duration: {duration:.2f} seconds")
                print("Data Points:", json.dumps([dp.model_dump(mode='json') for dp in response.data_points], indent=2))
                print("Context Updates:", json.dumps(response.context_updates.model_dump(mode='json') if response.context_updates else {}, indent=2))
                
            except Exception as e:
                logger.error(f"Error in {test['name']}: {str(e)}")

async def test_multi_step_analysis():
    """Test multi-step analysis with both services"""
    logger.info("Testing multi-step analysis...")
    
    async with BasketballService() as basketball:
        async with ResearchChain() as chain:
            try:
                # Step 1: Get team data
                logger.info("\nStep 1: Getting Lakers team data...")
                team_data = await basketball.get_team_data("Lakers")
                
                # Step 2: Use team data in research query
                logger.info("\nStep 2: Analyzing team data through research chain...")
                context = ConversationContext(
                    teams=["Lakers"],
                    sport="basketball"
                )
                
                request = ResearchRequest(
                    query="Based on their recent performance, should I bet on the Lakers to win their next game?",
                    mode=ResearchMode.DEEP,
                    context=context
                )
                
                response = await chain.process_request(request)
                
                print("\nMulti-step Analysis Results:")
                print("Team Data:", json.dumps(team_data, indent=2))
                print("\nAnalysis Response:", response.response)
                print("Data Points:", json.dumps([dp.dict() for dp in response.data_points], indent=2))
                
            except Exception as e:
                logger.error(f"Error in multi-step analysis: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run workflow tests")
    parser.add_argument(
        "--test-type",
        type=str,
        choices=["basketball", "research", "multi", "all"],
        help="Type of test to run",
        required=True
    )
    args = parser.parse_args()

    async def main():
        if args.test_type == "basketball" or args.test_type == "all":
            await test_basketball_service()
        if args.test_type == "research" or args.test_type == "all":
            await test_research_with_context()
        if args.test_type == "multi" or args.test_type == "all":
            await test_multi_step_analysis()

    asyncio.run(main())
