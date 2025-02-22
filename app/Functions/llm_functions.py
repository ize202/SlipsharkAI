from typing import Optional
import os
import logging
from openai import OpenAI
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

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model = "gpt-4o-mini"  

async def analyze_query(user_input: str) -> QueryAnalysis:
    """Initial LLM call to analyze the user's query and determine research path"""
    logger.info("Starting query analysis")
    logger.debug(f"Input text: {user_input}")

    completion = await client.chat.completions.create(
        model=model,
        response_model=QueryAnalysis,
        messages=[
            {
                "role": "system",
                "content": "Analyze the sports betting query to determine required research depth and data sources."
            },
            {"role": "user", "content": user_input}
        ]
    )
    
    result = completion.choices[0].message.model_dump()
    logger.info(f"Query analysis complete - Sport: {result.sport_type}, Deep Research: {result.is_deep_research}")
    return QueryAnalysis(**result)

async def quick_research(query: QueryAnalysis) -> QuickResearchResult:
    """Perform quick research using basic web search and simple analysis"""
    logger.info(f"Starting quick research for {query.sport_type}")

    completion = await client.chat.completions.create(
        model=model,
        response_model=QuickResearchResult,
        messages=[
            {
                "role": "system",
                "content": "Provide a quick analysis of the betting query using available data. Focus on key insights and whether deeper research is needed."
            },
            {"role": "user", "content": query.model_dump_json()}
        ]
    )

    result = completion.choices[0].message.model_dump()
    logger.info("Quick research complete")
    return QuickResearchResult(**result)

async def deep_research(query: QueryAnalysis, data_points: list[DataPoint]) -> DeepResearchResult:
    """Perform comprehensive research using multiple data sources"""
    logger.info(f"Starting deep research for {query.sport_type}")

    # Combine all data points into a coherent context
    data_context = "\n".join([f"Source {dp.source}: {dp.content}" for dp in data_points])

    completion = await client.chat.completions.create(
        model=model,
        response_model=DeepResearchResult,
        messages=[
            {
                "role": "system",
                "content": "Perform detailed analysis of betting opportunity using all available data. Consider historical performance, current odds, and risk factors."
            },
            {"role": "user", "content": f"Query: {query.model_dump_json()}\nData:\n{data_context}"}
        ]
    )

    result = completion.choices[0].message.model_dump()
    logger.info("Deep research complete")
    return DeepResearchResult(**result) 