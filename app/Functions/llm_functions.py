from typing import Optional, List
import logging
from datetime import datetime, UTC
from langfuse.decorators import observe
from langfuse import Langfuse
import openai
from ..config.langfuse_init import langfuse  # Use the initialized Langfuse instance
from ..services.perplexity import PerplexityService, PerplexityResponse

from ..models.betting_models import (
    QueryAnalysis,
    QuickResearchResult,
    DeepResearchResult,
    DataPoint,
    SportType,
    Citation
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Using the latest model for best performance
model = "gpt-4o-mini"

@observe(name="analyze_query")
async def analyze_query(user_input: str) -> QueryAnalysis:
    """Initial analysis to determine research path and extract key information"""
    logger.info("Starting query analysis")
    
    try:
        async with PerplexityService() as perplexity:
            analysis = await perplexity.analyze_query(user_input)
            return QueryAnalysis.model_validate_json(analysis)
            
    except Exception as e:
        logger.error(f"Error in analyze_query: {str(e)}", exc_info=True)
        raise

@observe(name="quick_research")
async def quick_research(query: QueryAnalysis) -> QuickResearchResult:
    """
    Perform quick research using Perplexity AI's combined LLM and web search capabilities.
    
    Args:
        query: Analyzed query containing sport type and other metadata
        
    Returns:
        QuickResearchResult with summary, insights, and citations
    """
    logger.info(f"Starting quick research for {query.sport_type}")
    
    try:
        # Construct a focused research query
        research_query = f"""
        Analyze betting opportunities for {query.raw_query}
        Focus on:
        - Current odds and line movements
        - Recent performance metrics
        - Key injuries or roster changes
        - Relevant news that could impact betting
        """
        
        async with PerplexityService() as perplexity:
            result: PerplexityResponse = await perplexity.quick_research(
                query=research_query,
                search_recency="day"  # Focus on very recent information for betting
            )
            
            # Convert Perplexity citations to our Citation model
            citations = []
            if result.citations:
                for cite in result.citations:
                    citations.append(Citation(
                        url=cite.get("url", ""),
                        title=cite.get("title"),
                        snippet=cite.get("snippet"),
                        published_date=cite.get("published_date")
                    ))
            
            # Create the research result
            return QuickResearchResult(
                summary=result.content,
                key_points=extract_key_points(result.content),
                confidence_score=calculate_confidence_score(result),
                deep_research_recommended=should_recommend_deep_research(result),
                citations=citations,
                related_questions=result.related_questions or [],  # Convert None to empty list
                last_updated=datetime.now(UTC).isoformat()  # Use timezone-aware UTC
            )
            
    except Exception as e:
        logger.error(f"Error in quick_research: {str(e)}", exc_info=True)
        raise

def extract_key_points(content: str) -> List[str]:
    """Extract key betting insights from the content"""
    # TODO: Implement more sophisticated key point extraction
    # For now, split on newlines and filter for bullet points
    points = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith(("-", "•", "*")) or line.startswith(("1.", "2.", "3.")):
            points.append(line.lstrip("- •*123456789. "))
    return points or [content]  # Return full content as single point if no clear points found

def calculate_confidence_score(result: PerplexityResponse) -> float:
    """Calculate confidence score based on citations and content"""
    # Start with base confidence
    confidence = 0.7
    
    # Adjust based on citations
    if result.citations:
        confidence += min(len(result.citations) * 0.1, 0.2)  # Up to 0.2 boost for citations
        
    # Cap at 0.95 to leave room for uncertainty
    return min(confidence, 0.95)

def should_recommend_deep_research(result: PerplexityResponse) -> bool:
    """Determine if deep research is recommended based on the quick research results"""
    # Recommend deep research if:
    # 1. We have multiple citations indicating complexity
    # 2. There are related questions suggesting more angles to explore
    # 3. The content suggests uncertainty or multiple factors
    has_many_citations = len(result.citations or []) >= 3
    has_related_questions = len(result.related_questions or []) >= 2
    content_length = len(result.content.split())
    
    return has_many_citations or has_related_questions or content_length > 200

@observe(name="deep_research")
def deep_research(query: QueryAnalysis, data_points: list[DataPoint]) -> DeepResearchResult:
    """Perform comprehensive research using multiple data sources"""
    logger.info(f"Starting deep research for {query.sport_type}")
    
    try:
        # Combine all data points into a coherent context
        data_context = "\n".join([f"Source {dp.source}: {dp.content}" for dp in data_points])
        
        messages = [
            {
                "role": "system",
                "content": "Perform detailed analysis of betting opportunity using all available data. Consider historical performance, current odds, and risk factors."
            },
            {"role": "user", "content": f"Query: {query.model_dump_json()}\nData:\n{data_context}"}
        ]
        
        completion = openai.chat.completions.create(
            model=model,
            messages=messages
        )

        result = completion.choices[0].message.content
        return DeepResearchResult.model_validate_json(result)
            
    except Exception as e:
        logger.error(f"Error in deep_research: {str(e)}", exc_info=True)
        raise 