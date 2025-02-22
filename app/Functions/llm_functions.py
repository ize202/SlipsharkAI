from typing import Optional
import logging
from langfuse.decorators import observe
from langfuse import Langfuse
import openai
from ..config.langfuse_init import langfuse  # Use the initialized Langfuse instance

from ..models.betting_models import (
    QueryAnalysis,
    QuickResearchResult,
    DeepResearchResult,
    DataPoint,
    SportType
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Using the latest model for best performance
model = "gpt-4-turbo-preview"

@observe(name="analyze_query")
def analyze_query(user_input: str) -> QueryAnalysis:
    """Initial LLM call to analyze the user's query and determine research path"""
    logger.info("Starting query analysis")
    
    try:
        messages = [
            {
                "role": "system",
                "content": "Analyze the sports betting query to determine required research depth and data sources."
            },
            {"role": "user", "content": user_input}
        ]
        
        completion = openai.chat.completions.create(
            model=model,
            messages=messages
        )
        
        result = completion.choices[0].message.content
        return QueryAnalysis.model_validate_json(result)
            
    except Exception as e:
        logger.error(f"Error in analyze_query: {str(e)}", exc_info=True)
        raise

@observe(name="quick_research")
def quick_research(query: QueryAnalysis) -> QuickResearchResult:
    """Perform quick research using basic web search and simple analysis"""
    logger.info(f"Starting quick research for {query.sport_type}")
    
    try:
        messages = [
            {
                "role": "system",
                "content": "Provide a quick analysis of the betting query using available data. Focus on key insights and whether deeper research is needed."
            },
            {"role": "user", "content": query.model_dump_json()}
        ]
        
        completion = openai.chat.completions.create(
            model=model,
            messages=messages
        )

        result = completion.choices[0].message.content
        return QuickResearchResult.model_validate_json(result)
            
    except Exception as e:
        logger.error(f"Error in quick_research: {str(e)}", exc_info=True)
        raise

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