import pytest
import asyncio
from datetime import datetime
from app.workflows.research_chain import ResearchChain
from app.models.research_models import ResearchRequest, ResearchMode, ConversationContext
from app.utils.cache import get_cache_stats
import logging

logger = logging.getLogger(__name__)

# Test queries for verifying cache behavior
QUICK_TEST_QUERIES = [
    "What are the Lakers odds against the Warriors tonight?",
    "What are the Lakers odds vs Warriors tonight?",  # Similar query
    "What are the Warriors chances against Lakers tonight?",  # Related but different
]

DEEP_TEST_QUERIES = [
    "Should I bet on LeBron James to score over 25.5 points tonight?",
    "Is LeBron James likely to score more than 25.5 points in tonight's game?",  # Similar query
    "What's the probability of LeBron scoring 26+ points tonight?",  # Related but different
]

@pytest.mark.asyncio
async def test_quick_research_caching():
    """Test caching behavior for quick research queries"""
    chain = ResearchChain()
    
    # First query - should be a cache miss
    start_time = datetime.now()
    first_response = await chain.process_request(
        ResearchRequest(query=QUICK_TEST_QUERIES[0], mode=ResearchMode.QUICK)
    )
    first_duration = (datetime.now() - start_time).total_seconds()
    
    # Same query - should be a cache hit
    start_time = datetime.now()
    second_response = await chain.process_request(
        ResearchRequest(query=QUICK_TEST_QUERIES[0], mode=ResearchMode.QUICK)
    )
    second_duration = (datetime.now() - start_time).total_seconds()
    
    # Similar query - might be a cache hit depending on implementation
    start_time = datetime.now()
    similar_response = await chain.process_request(
        ResearchRequest(query=QUICK_TEST_QUERIES[1], mode=ResearchMode.QUICK)
    )
    similar_duration = (datetime.now() - start_time).total_seconds()
    
    # Log timing results
    logger.info(f"First query duration: {first_duration:.2f}s")
    logger.info(f"Second query duration: {second_duration:.2f}s")
    logger.info(f"Similar query duration: {similar_duration:.2f}s")
    
    # Get cache stats
    cache_stats = await get_cache_stats()
    logger.info(f"Cache stats after quick research test: {cache_stats}")
    
    # Assertions
    assert second_duration < first_duration, "Cache hit should be faster than cache miss"
    assert first_response.response == second_response.response, "Cached response should match original"

@pytest.mark.asyncio
async def test_deep_research_caching():
    """Test caching behavior for deep research queries"""
    chain = ResearchChain()
    
    # First deep query - should be a cache miss
    first_response = await chain.process_request(
        ResearchRequest(query=DEEP_TEST_QUERIES[0], mode=ResearchMode.DEEP)
    )
    
    # Same deep query - should be a cache hit
    second_response = await chain.process_request(
        ResearchRequest(query=DEEP_TEST_QUERIES[0], mode=ResearchMode.DEEP)
    )
    
    # Similar deep query - might be a partial cache hit
    similar_response = await chain.process_request(
        ResearchRequest(query=DEEP_TEST_QUERIES[1], mode=ResearchMode.DEEP)
    )
    
    # Get cache stats
    cache_stats = await get_cache_stats()
    logger.info(f"Cache stats after deep research test: {cache_stats}")
    
    # Assertions
    assert first_response.response == second_response.response, "Cache hit should return the same response"
    assert first_response.response != similar_response.response, "Similar but different query should return different response"
    
    # Check that cache stats show at least one hit
    assert cache_stats.get("hits", 0) > 0, "Cache should have at least one hit"

@pytest.mark.asyncio
async def test_cache_ttl():
    """Test that cache respects TTL settings"""
    chain = ResearchChain()
    
    # Make initial request
    first_response = await chain.process_request(
        ResearchRequest(query=QUICK_TEST_QUERIES[0], mode=ResearchMode.QUICK)
    )
    
    # Wait for 2 seconds to ensure cache is still valid
    await asyncio.sleep(2)
    
    # Make same request - should be cache hit
    start_time = datetime.now()
    cached_response = await chain.process_request(
        ResearchRequest(query=QUICK_TEST_QUERIES[0], mode=ResearchMode.QUICK)
    )
    cached_duration = (datetime.now() - start_time).total_seconds()
    
    # Verify cache hit was fast
    assert cached_duration < 1.0, "Cache hit should be very fast"
    assert first_response.response == cached_response.response, "Cached response should match original"

@pytest.mark.asyncio
async def test_context_aware_caching():
    """Test that caching considers conversation context"""
    chain = ResearchChain()
    
    # Create a context
    context = ConversationContext(
        teams=["Lakers"],
        players=["LeBron James"],
        last_query_time=datetime.now()
    )
    
    # Query with context
    first_response = await chain.process_request(
        ResearchRequest(
            query=DEEP_TEST_QUERIES[0],
            mode=ResearchMode.DEEP,
            context=context
        )
    )
    
    # Same query without context - should be different response
    no_context_response = await chain.process_request(
        ResearchRequest(
            query=DEEP_TEST_QUERIES[0],
            mode=ResearchMode.DEEP
        )
    )
    
    # Same query with same context - should be cache hit
    context_response = await chain.process_request(
        ResearchRequest(
            query=DEEP_TEST_QUERIES[0],
            mode=ResearchMode.DEEP,
            context=context
        )
    )
    
    assert first_response.response == context_response.response, "Same query with same context should hit cache"
    assert first_response.response != no_context_response.response, "Same query with different context should miss cache" 