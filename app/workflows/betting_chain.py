import logging
from typing import Optional, Union
from ..models.betting_models import (
    QueryAnalysis,
    QuickResearchResult,
    DeepResearchResult,
    DataPoint
)
from ..Functions.llm_functions import analyze_query, quick_research, deep_research

# Set up logging
logger = logging.getLogger(__name__)

class BettingResearchChain:
    """Main chain for orchestrating the betting research workflow"""

    def __init__(self):
        self.data_providers = []  # Initialize with your data providers (sports APIs, etc.)

    async def _gather_data(self, query: QueryAnalysis) -> list[DataPoint]:
        """Gather data from various sources based on query requirements"""
        data_points = []
        
        # TODO: Implement parallel data gathering from various sources
        # This is where you'd integrate with sports APIs, web search, etc.
        
        return data_points

    async def process_query(
        self, user_input: str, force_deep_research: bool = False
    ) -> Union[QuickResearchResult, DeepResearchResult]:
        """
        Main entry point for processing betting research queries.
        
        Args:
            user_input: The user's betting research query
            force_deep_research: Whether to skip quick research and go straight to deep research
            
        Returns:
            Either a QuickResearchResult or DeepResearchResult depending on the analysis
        """
        try:
            # Step 1: Analyze the query
            query_analysis = await analyze_query(user_input)
            logger.info(f"Query analysis complete: {query_analysis.model_dump_json()}")

            # Override analysis if deep research is forced
            if force_deep_research:
                query_analysis.is_deep_research = True

            # Step 2: Choose research path
            if not query_analysis.is_deep_research:
                # Quick Research Path
                logger.info("Starting quick research path")
                result = await quick_research(query_analysis)
                
                # Check if deep research is recommended
                if result.deep_research_recommended:
                    logger.info("Quick research suggests deep research is needed")
                    return result  # Return quick result with recommendation for deep research
                
                return result

            # Deep Research Path
            logger.info("Starting deep research path")
            
            # Step 3: Gather data from all required sources
            data_points = await self._gather_data(query_analysis)
            logger.info(f"Gathered {len(data_points)} data points")

            # Step 4: Perform deep research
            result = await deep_research(query_analysis, data_points)
            return result

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            raise

    async def extend_research(
        self, quick_result: QuickResearchResult, original_query: str
    ) -> DeepResearchResult:
        """
        Extend a quick research result into a deep research analysis
        
        Args:
            quick_result: The original quick research result
            original_query: The original user query
            
        Returns:
            A comprehensive DeepResearchResult
        """
        try:
            # Re-analyze query with forced deep research
            return await self.process_query(original_query, force_deep_research=True)
        except Exception as e:
            logger.error(f"Error extending research: {str(e)}", exc_info=True)
            raise 