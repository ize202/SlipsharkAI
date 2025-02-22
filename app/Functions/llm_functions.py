from typing import Optional
import os
import logging
from langtrace_python_sdk import langtrace
from opentelemetry import trace
from openai import OpenAI
from ..config import OPENAI_API_KEY, LANGTRACE_API_KEY

# Initialize LangTrace
langtrace.init(api_key=LANGTRACE_API_KEY)

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

# Get tracer
tracer = trace.get_tracer(__name__)

# Initialize OpenAI client
client = OpenAI()  # It will automatically use OPENAI_API_KEY from environment
model = "gpt-4-turbo-preview"  # Using the latest model for best performance

def analyze_query(user_input: str) -> QueryAnalysis:
    """Initial LLM call to analyze the user's query and determine research path"""
    logger.info("Starting query analysis")
    
    try:
        with tracer.start_as_current_span("sports_betting.analyze_query") as span:
            # Add context about the operation
            span.set_attribute("operation", "query_analysis")
            span.set_attribute("model", model)
            span.set_attribute("input", user_input)
            
            messages = [
                {
                    "role": "system",
                    "content": "Analyze the sports betting query to determine required research depth and data sources."
                },
                {"role": "user", "content": user_input}
            ]
            
            # Track the prompt being sent
            span.set_attribute("messages", str(messages))
            
            completion = client.chat.completions.create(
                model=model,
                messages=messages
            )
            
            result = completion.choices[0].message.content
            
            # Track the complete response
            span.set_attribute("completion", result)
            span.set_attribute("success", True)
            
            return QueryAnalysis.model_validate_json(result)
            
    except Exception as e:
        logger.error(f"Error in analyze_query: {str(e)}", exc_info=True)
        if 'span' in locals():
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
        raise

def quick_research(query: QueryAnalysis) -> QuickResearchResult:
    """Perform quick research using basic web search and simple analysis"""
    logger.info(f"Starting quick research for {query.sport_type}")
    
    try:
        with tracer.start_as_current_span("sports_betting.quick_research") as span:
            # Add context about the operation
            span.set_attribute("operation", "quick_research")
            span.set_attribute("model", model)
            span.set_attribute("sport_type", str(query.sport_type))
            
            messages = [
                {
                    "role": "system",
                    "content": "Provide a quick analysis of the betting query using available data. Focus on key insights and whether deeper research is needed."
                },
                {"role": "user", "content": query.model_dump_json()}
            ]
            
            # Track the prompt being sent
            span.set_attribute("messages", str(messages))
            span.set_attribute("input_query", query.model_dump_json())
            
            completion = client.chat.completions.create(
                model=model,
                messages=messages
            )

            result = completion.choices[0].message.content
            
            # Track the complete response
            span.set_attribute("completion", result)
            span.set_attribute("success", True)
            
            return QuickResearchResult.model_validate_json(result)
            
    except Exception as e:
        logger.error(f"Error in quick_research: {str(e)}", exc_info=True)
        if 'span' in locals():
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
        raise

def deep_research(query: QueryAnalysis, data_points: list[DataPoint]) -> DeepResearchResult:
    """Perform comprehensive research using multiple data sources"""
    logger.info(f"Starting deep research for {query.sport_type}")
    
    try:
        with tracer.start_as_current_span("sports_betting.deep_research") as span:
            # Add context about the operation
            span.set_attribute("operation", "deep_research")
            span.set_attribute("model", model)
            span.set_attribute("sport_type", str(query.sport_type))
            span.set_attribute("data_points_count", len(data_points))
            
            # Combine all data points into a coherent context
            data_context = "\n".join([f"Source {dp.source}: {dp.content}" for dp in data_points])
            
            messages = [
                {
                    "role": "system",
                    "content": "Perform detailed analysis of betting opportunity using all available data. Consider historical performance, current odds, and risk factors."
                },
                {"role": "user", "content": f"Query: {query.model_dump_json()}\nData:\n{data_context}"}
            ]
            
            # Track the prompt being sent
            span.set_attribute("messages", str(messages))
            span.set_attribute("input_query", query.model_dump_json())
            span.set_attribute("input_data_points", str([dp.model_dump() for dp in data_points]))
            
            completion = client.chat.completions.create(
                model=model,
                messages=messages
            )

            result = completion.choices[0].message.content
            
            # Track the complete response
            span.set_attribute("completion", result)
            span.set_attribute("success", True)
            
            return DeepResearchResult.model_validate_json(result)
            
    except Exception as e:
        logger.error(f"Error in deep_research: {str(e)}", exc_info=True)
        if 'span' in locals():
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
        raise 