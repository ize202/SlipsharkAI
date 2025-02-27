#!/usr/bin/env python
"""
Test Runner for Research Workflow Tests

This script provides a convenient way to run the research workflow tests
with detailed output and timing information.

Usage:
    python tests/run_workflow_test.py [--full | --query | --data | --analysis | --response | --quick]

Options:
    --full      Run the full workflow test (default if no option is specified)
    --query     Run only the query analyzer test
    --data      Run only the data gathering test
    --analysis  Run only the data analysis test
    --response  Run only the response generation test
    --quick     Run the quick test (only query analyzer, fastest option)
"""

import asyncio
import argparse
import time
import sys
from datetime import datetime

# Add the project root to the Python path
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.workflows.research_chain import ResearchChain
from tests.integration.test_research_workflow import (
    test_full_research_workflow,
    test_query_analyzer,
    test_data_gathering,
    test_data_analysis,
    test_response_generation
)
from tests.integration.test_quick_workflow import test_query_analyzer_quick

def print_header(title):
    """Print a formatted header for test sections"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

async def run_tests(args):
    """Run the selected tests based on command line arguments"""
    research_chain = ResearchChain()
    
    if args.quick:
        print_header("RUNNING QUICK TEST (QUERY ANALYZER ONLY)")
        start_time = time.time()
        await test_query_analyzer_quick(research_chain)
        elapsed = time.time() - start_time
        print(f"\nQuick test completed in {elapsed:.2f} seconds")
        return
    
    if args.full or not any([args.query, args.data, args.analysis, args.response]):
        print_header("RUNNING FULL WORKFLOW TEST")
        start_time = time.time()
        await test_full_research_workflow(research_chain)
        elapsed = time.time() - start_time
        print(f"\nFull workflow test completed in {elapsed:.2f} seconds")
    
    if args.query:
        print_header("RUNNING QUERY ANALYZER TEST")
        start_time = time.time()
        await test_query_analyzer(research_chain)
        elapsed = time.time() - start_time
        print(f"\nQuery analyzer test completed in {elapsed:.2f} seconds")
    
    if args.data:
        print_header("RUNNING DATA GATHERING TEST")
        start_time = time.time()
        await test_data_gathering(research_chain)
        elapsed = time.time() - start_time
        print(f"\nData gathering test completed in {elapsed:.2f} seconds")
    
    if args.analysis:
        print_header("RUNNING DATA ANALYSIS TEST")
        start_time = time.time()
        await test_data_analysis(research_chain)
        elapsed = time.time() - start_time
        print(f"\nData analysis test completed in {elapsed:.2f} seconds")
    
    if args.response:
        print_header("RUNNING RESPONSE GENERATION TEST")
        start_time = time.time()
        await test_response_generation(research_chain)
        elapsed = time.time() - start_time
        print(f"\nResponse generation test completed in {elapsed:.2f} seconds")

def main():
    """Parse arguments and run tests"""
    parser = argparse.ArgumentParser(description="Run research workflow tests")
    parser.add_argument("--full", action="store_true", help="Run the full workflow test")
    parser.add_argument("--query", action="store_true", help="Run only the query analyzer test")
    parser.add_argument("--data", action="store_true", help="Run only the data gathering test")
    parser.add_argument("--analysis", action="store_true", help="Run only the data analysis test")
    parser.add_argument("--response", action="store_true", help="Run only the response generation test")
    parser.add_argument("--quick", action="store_true", help="Run the quick test (only query analyzer, fastest option)")
    
    args = parser.parse_args()
    
    # Print test run information
    print(f"Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        asyncio.run(run_tests(args))
        print("\nAll tests completed successfully!")
        return 0
    except Exception as e:
        print(f"\nTest failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 