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

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    "quick_basketball": "How are the Lakers performing recently?",
    "deep_basketball": "Should I bet on the Lakers considering their last 5 games, current injuries, and their matchup against the Warriors?",
    "player_focused": "How has LeBron James been performing in his recent games?",
    "team_comparison": "Compare the Celtics and Bucks for betting purposes.",
    "season_specific": "How have the Nuggets performed this season?",
    "explicit_mode_quick": "Give me a quick overview of the Suns' recent performance.",
    "explicit_mode_deep": "Do a deep analysis of the Heat's chances against the Knicks tomorrow."
}

async def test_research_workflow(query: str, mode: ResearchMode = ResearchMode.AUTO):
    """Test the research workflow with a given query and mode"""
    logger.info(f"\n{'='*80}")
    logger.info(f"TESTING QUERY: '{query}'")
    logger.info(f"MODE: {mode}")
    logger.info(f"{'='*80}\n")
    
    try:
        # Create a request
        request = ResearchRequest(
            query=query,
            mode=mode,
            context=ResearchContext(
                user_id="test_user_123",  # Use a test user ID
                session_id="test_session_456"
            )
        )
        logger.debug(f"Created research request: {request}")
        
        # Create a research chain
        logger.debug("Initializing ResearchChain")
        async with ResearchChain() as chain:
            # Start timing
            start_time = datetime.now()
            
            # Process the request
            logger.info("Processing request...")
            try:
                response = await chain.process_request(request)
                logger.debug("Request processed successfully")
            except Exception as e:
                logger.error(f"Error processing request: {str(e)}", exc_info=True)
                raise
            
            # End timing
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Print results
            logger.info(f"\nRESULTS (processed in {processing_time:.2f} seconds):")
            logger.info(f"Mode used: {response.metadata.mode_used}")
            logger.info(f"Confidence score: {response.metadata.confidence_score:.2f}")
            
            print(f"\nSUMMARY:")
            print(response.summary)
            
            print(f"\nINSIGHTS ({len(response.insights)}):")
            for i, insight in enumerate(response.insights, 1):
                print(f"{i}. [{insight.category}] {insight.insight} (Confidence: {insight.confidence:.2f})")
            
            print(f"\nRISK FACTORS ({len(response.risk_factors)}):")
            for i, risk in enumerate(response.risk_factors, 1):
                print(f"{i}. [{risk.severity.upper()}] {risk.factor} - {risk.mitigation}")
            
            print(f"\nRECOMMENDATIONS ({len(response.recommendations)}):")
            for i, rec in enumerate(response.recommendations, 1):
                print(f"{i}. {rec}")
            
            print(f"\nSOURCES ({len(response.sources)}):")
            for i, source in enumerate(response.sources, 1):
                print(f"{i}. [{source.type}] {source.name}")
            
            return response
    except Exception as e:
        logger.error(f"Test workflow failed: {str(e)}", exc_info=True)
        raise

async def run_all_tests():
    """Run all test queries"""
    results = {}
    
    # Test auto mode with different queries
    for name, query in TEST_QUERIES.items():
        if name != "explicit_mode_quick" and name != "explicit_mode_deep":
            results[f"auto_{name}"] = await test_research_workflow(query)
    
    # Test explicit quick mode
    results["explicit_quick"] = await test_research_workflow(
        TEST_QUERIES["explicit_mode_quick"], 
        mode=ResearchMode.QUICK
    )
    
    # Test explicit deep mode
    results["explicit_deep"] = await test_research_workflow(
        TEST_QUERIES["explicit_mode_deep"], 
        mode=ResearchMode.DEEP
    )
    
    # Print summary of all tests
    print("\n\nTEST SUMMARY:")
    print(f"{'='*80}")
    for name, response in results.items():
        print(f"{name}: Mode={response.metadata.mode_used}, Time={response.metadata.processing_time:.2f}s, Confidence={response.metadata.confidence_score:.2f}")
    
    return results

async def run_single_test(query_type: str = "quick_basketball"):
    """Run a single test query"""
    if query_type in TEST_QUERIES:
        return await test_research_workflow(TEST_QUERIES[query_type])
    else:
        print(f"Query type '{query_type}' not found. Available types: {list(TEST_QUERIES.keys())}")
        return None

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
            
        loop.run_until_complete(test_research_workflow(args.custom, mode))
    elif args.query:
        # Run specific test query
        mode = ResearchMode.AUTO
        if args.mode == 'quick':
            mode = ResearchMode.QUICK
        elif args.mode == 'deep':
            mode = ResearchMode.DEEP
            
        loop.run_until_complete(test_research_workflow(TEST_QUERIES[args.query], mode))
    else:
        # Default: run quick basketball test
        loop.run_until_complete(run_single_test("quick_basketball"))
