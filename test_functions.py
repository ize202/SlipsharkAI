import asyncio
import json
import logging
from app.functions.llm_functions import analyze_query, quick_research, deep_research, generate_final_response
from app.models.betting_models import QueryAnalysis, QuickResearchResult, DeepResearchResult

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def test_analyze_query(query_text: str):
    """Test the analyze_query function"""
    logger.info(f"Testing analyze_query with: {query_text}")
    try:
        result = await analyze_query(query_text)
        logger.info(f"Query analysis result: {result.model_dump_json(indent=2)}")
        return result
    except Exception as e:
        logger.error(f"Error in analyze_query: {str(e)}", exc_info=True)
        return None

async def test_quick_research(query_analysis: QueryAnalysis):
    """Test the quick_research function"""
    logger.info(f"Testing quick_research with: {query_analysis.raw_query}")
    try:
        result = await quick_research(query_analysis)
        logger.info(f"Quick research result: {result.model_dump_json(indent=2)}")
        return result
    except Exception as e:
        logger.error(f"Error in quick_research: {str(e)}", exc_info=True)
        return None

async def test_generate_final_response(query_text: str, research_result, is_deep_research: bool = False):
    """Test the generate_final_response function"""
    logger.info(f"Testing generate_final_response with: {query_text}")
    try:
        result = await generate_final_response(query_text, research_result, is_deep_research)
        logger.info(f"Final response: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        logger.error(f"Error in generate_final_response: {str(e)}", exc_info=True)
        return None

async def run_full_test(query_text: str):
    """Run a full test of the workflow"""
    logger.info(f"Running full test with query: {query_text}")
    
    # Step 1: Analyze query
    query_analysis = await test_analyze_query(query_text)
    if not query_analysis:
        logger.error("Query analysis failed, stopping test")
        return
    
    # Step 2: Quick research
    quick_result = await test_quick_research(query_analysis)
    if not quick_result:
        logger.error("Quick research failed, stopping test")
        return
    
    # Step 3: Generate final response
    final_result = await test_generate_final_response(query_text, quick_result, False)
    if not final_result:
        logger.error("Final response generation failed, stopping test")
        return
    
    # Print the conversational response
    logger.info("CONVERSATIONAL RESPONSE:")
    logger.info(final_result.get("conversational_response", "No conversational response generated"))
    
    return final_result

async def main():
    """Main test function"""
    # Test queries
    test_queries = [
        "How are the Lakers playing this season?",
        "Should I bet on the Celtics to cover the spread against the Bucks?",
        "What's the best bet for the Warriors game tonight?",
        "Are there any good player prop bets for LeBron James?"
    ]
    
    # Run tests
    for query in test_queries:
        logger.info(f"\n\n{'='*50}\nTESTING QUERY: {query}\n{'='*50}")
        await run_full_test(query)
        logger.info(f"{'='*50}\nTEST COMPLETED\n{'='*50}\n\n")

if __name__ == "__main__":
    asyncio.run(main()) 