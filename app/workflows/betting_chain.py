import logging
from typing import Optional, Union
from app.models.betting_models import (
    QueryAnalysis,
    QuickResearchResult,
    DeepResearchResult,
    DataPoint
)
import asyncio
from datetime import datetime, UTC

# Import LLM functions with a single preferred path
try:
    # Prefer lowercase functions path for consistency
    from app.functions.llm_functions import analyze_query, quick_research, deep_research, generate_final_response
except ImportError as e:
    logging.error(f"Failed to import llm_functions: {str(e)}")
    # Define placeholder functions that will raise clear errors if called
    async def analyze_query(*args, **kwargs):
        raise ImportError("LLM functions not properly imported")
    async def quick_research(*args, **kwargs):
        raise ImportError("LLM functions not properly imported")
    async def deep_research(*args, **kwargs):
        raise ImportError("LLM functions not properly imported")
    async def generate_final_response(*args, **kwargs):
        raise ImportError("LLM functions not properly imported")

# Set up logging
logger = logging.getLogger(__name__)

class BettingResearchChain:
    """Main chain for orchestrating the betting research workflow"""

    def __init__(self):
        self.data_providers = []  # Initialize with your data providers (sports APIs, etc.)

    async def _gather_data(self, query: QueryAnalysis) -> list[DataPoint]:
        """Gather data from various sources based on query requirements"""
        logger.info(f"Gathering data for {query.sport_type} query")
        data_points = []
        
        # Extract team names from the query analysis
        teams = [team for team in query.teams.values() if team]
        
        if not teams:
            logger.warning("No teams found in query analysis, using generic research")
            # If no specific teams, we'll still try to gather general data
            if query.sport_type == SportType.BASKETBALL:
                teams = ["NBA"]  # Use generic NBA as fallback
            elif query.sport_type == SportType.FOOTBALL:
                teams = ["NFL"]
            elif query.sport_type == SportType.BASEBALL:
                teams = ["MLB"]
            elif query.sport_type == SportType.HOCKEY:
                teams = ["NHL"]
            elif query.sport_type == SportType.SOCCER:
                teams = ["Soccer"]
        
        # Initialize services based on the sport type
        if query.sport_type == SportType.BASKETBALL:
            # Import services here to avoid circular imports
            from app.services.perplexity import PerplexityService
            from app.services.api_sports_basketball import APISportsBasketballService
            from app.services.supabase import SupabaseService
            
            # Gather data from all sources in parallel
            async with PerplexityService() as perplexity, APISportsBasketballService() as basketball:
                # Define all the tasks we want to run in parallel
                tasks = []
                
                # Add Perplexity tasks for general research
                tasks.append(
                    perplexity.quick_research(
                        query=f"Latest {query.sport_type.value} betting information for {query.raw_query}",
                        search_recency="day"
                    )
                )
                
                # Add tasks for each team
                for team in teams:
                    if team != "NBA":  # Skip team-specific queries for generic NBA
                        # Add Perplexity search for this team
                        tasks.append(
                            perplexity.quick_research(
                                query=f"Latest news, injuries, and betting trends for {team}",
                                search_recency="day"
                            )
                        )
                        
                        # Try to get team-specific data from API-Sports
                        try:
                            # Get team stats
                            tasks.append(basketball.get_team_stats(team))
                            
                            # Get player stats
                            tasks.append(basketball.get_player_stats(team))
                            
                            # Get upcoming games
                            tasks.append(basketball.get_upcoming_games(team))
                        except Exception as e:
                            logger.warning(f"Could not add team-specific API-Sports tasks for {team}: {str(e)}")
                
                # Execute all tasks in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and handle any exceptions
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Error in data gathering task {i}: {str(result)}")
                    else:
                        # Add successful results to data points
                        if result:
                            source_name = tasks[i].__qualname__ if hasattr(tasks[i], '__qualname__') else f"task_{i}"
                            data_points.append(DataPoint(
                                source=source_name,
                                content=result.model_dump() if hasattr(result, 'model_dump') else str(result),
                                timestamp=datetime.now(UTC)
                            ))
        
        elif query.sport_type in [SportType.FOOTBALL, SportType.BASEBALL, SportType.HOCKEY, SportType.SOCCER]:
            # For other sports, we'll use Perplexity for now
            from app.services.perplexity import PerplexityService
            
            async with PerplexityService() as perplexity:
                # Add Perplexity tasks for general research
                tasks = []
                
                tasks.append(
                    perplexity.quick_research(
                        query=f"Latest {query.sport_type.value} betting information for {query.raw_query}",
                        search_recency="day"
                    )
                )
                
                # Add tasks for each team
                for team in teams:
                    if team not in ["NFL", "MLB", "NHL", "Soccer"]:  # Skip team-specific queries for generic sports
                        tasks.append(
                            perplexity.quick_research(
                                query=f"Latest news, injuries, and betting trends for {team} in {query.sport_type.value}",
                                search_recency="day"
                            )
                        )
                
                # Execute all tasks in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and handle any exceptions
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Error in data gathering task {i}: {str(result)}")
                    else:
                        # Add successful results to data points
                        if result:
                            source_name = tasks[i].__qualname__ if hasattr(tasks[i], '__qualname__') else f"task_{i}"
                            data_points.append(DataPoint(
                                source=source_name,
                                content=result.model_dump() if hasattr(result, 'model_dump') else str(result),
                                timestamp=datetime.now(UTC)
                            ))
        
        logger.info(f"Gathered {len(data_points)} data points")
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
                
                # Step 3: Generate final conversational response
                enhanced_result = await generate_final_response(
                    user_input, 
                    result, 
                    is_deep_research=False
                )
                
                # Convert back to QuickResearchResult with the added conversational_response field
                # We'll handle this in the API response
                
                # Check if deep research is recommended
                if result.deep_research_recommended:
                    logger.info("Quick research suggests deep research is needed")
                    return enhanced_result  # Return quick result with recommendation for deep research
                
                return enhanced_result

            # Deep Research Path
            logger.info("Starting deep research path")
            
            # Step 3: Gather data from all required sources
            data_points = await self._gather_data(query_analysis)
            logger.info(f"Gathered {len(data_points)} data points")

            # Step 4: Perform deep research
            result = await deep_research(query_analysis, data_points)
            
            # Step 5: Generate final conversational response
            enhanced_result = await generate_final_response(
                user_input, 
                result, 
                is_deep_research=True
            )
            
            return enhanced_result

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
            result = await self.process_query(original_query, force_deep_research=True)
            return result
        except Exception as e:
            logger.error(f"Error extending research: {str(e)}", exc_info=True)
            raise 