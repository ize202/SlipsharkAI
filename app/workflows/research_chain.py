from datetime import datetime
import uuid
import asyncio
from typing import List, Dict, Any, Union, Optional
import json
from app.models.research_models import (
    ResearchRequest,
    ResearchResponse,
    QueryAnalysis,
    DataPoint,
    ResearchMode,
    SportType,
    ConversationContext
)
from app.services.perplexity import PerplexityService
from app.services.basketball_service import BasketballService
from app.services.supabase import SupabaseService
from app.utils.llm_utils import structured_llm_call, json_serialize
from app.utils.prompt_manager import get_query_analysis_prompt, get_response_generation_prompt
from app.config import get_logger
from langfuse.decorators import observe
from app.utils.cache import redis_cache

logger = get_logger(__name__)

class ResearchChain:
    """
    Research chain that handles both quick and deep research modes.
    Orchestrates the workflow between different services and LLM calls.
    
    Flow:
    1. Query Analysis (LLM Call 1)
    2. Data Gathering (Web Search + Sports API)
    3. Response Generation (LLM Call 2)
    """

    def __init__(self):
        """Initialize service instances"""
        self.perplexity = PerplexityService()
        self.basketball = None  # Lazy initialization
        self.supabase = SupabaseService()

    async def _ensure_basketball_service(self):
        """Ensure basketball service is initialized in async context"""
        if not self.basketball:
            self.basketball = BasketballService()
            await self.basketball.__aenter__()
        return self.basketball

    @observe(name="analyze_query")
    async def _analyze_query(self, request: ResearchRequest) -> QueryAnalysis:
        """[LLM Call 1] Analyze the user's query and determine research mode"""
        try:
            # Get the current production prompt from Langfuse
            prompt = get_query_analysis_prompt()
            
            # Compile the prompt with variables
            compiled_prompt = prompt.compile(query=request.query)
            
            analysis_result = await structured_llm_call(
                prompt=compiled_prompt,
                messages=[{"role": "user", "content": request.query}]
            )
            
            # Mode Decision Logic
            if request.mode != ResearchMode.AUTO:
                analysis_result["recommended_mode"] = request.mode
            else:
                recommended_mode = analysis_result.get("recommended_mode", "quick").lower()
                analysis_result["recommended_mode"] = (
                    ResearchMode.DEEP if recommended_mode == "deep" else ResearchMode.QUICK
                )
            
            return QueryAnalysis(**analysis_result)
            
        except Exception as e:
            logger.error(f"Error in query analysis: {str(e)}", exc_info=True)
            raise

    @observe(name="gather_data")
    async def _gather_data(self, analysis: QueryAnalysis, request: ResearchRequest) -> List[DataPoint]:
        """Gather data based on determined research mode"""
        data_points: List[DataPoint] = []
        
        # Always start with web search
        try:
            # Let PerplexityService handle all the search details
            perplexity_response = await self.perplexity.quick_research(query=analysis.raw_query)
            data_points.append(DataPoint(
                source="perplexity",
                content=perplexity_response.content,
                confidence=0.8
            ))
            
            # For deep research, add sports API data
            if analysis.recommended_mode == ResearchMode.DEEP:
                basketball = await self._ensure_basketball_service()
                
                # Get team data if teams are mentioned
                team_data = {}
                for team_key, team in analysis.teams.items():
                    if team:
                        team_data[team] = await basketball.get_team_data(team)
                        if team_data[team]:
                            data_points.append(DataPoint(
                                source="basketball_api",
                                content=team_data[team],
                                confidence=0.9
                            ))
                
                # Get player data if players are mentioned
                for player in analysis.players:
                    # Try to find the player's team from context or analysis
                    player_team = None
                    if request.context and request.context.teams:
                        player_team = request.context.teams[0]
                    elif team_data:
                        player_team = list(team_data.keys())[0]
                    
                    if player_team:
                        try:
                            player_data = await basketball.get_player_data(player, player_team)
                            if player_data:
                                data_points.append(DataPoint(
                                    source="basketball_api",
                                    content=player_data,
                                    confidence=0.9
                                ))
                        except Exception as e:
                            logger.error(f"Error getting data for player {player}: {str(e)}")
                            data_points.append(DataPoint(
                                source="basketball_api",
                                content={"error": f"Failed to get data for player {player}: {str(e)}"},
                                confidence=0.9
                            ))
            
            return data_points
                
        except Exception as e:
            logger.error(f"Error gathering data: {str(e)}")
            raise
        finally:
            if analysis.recommended_mode == ResearchMode.DEEP and self.basketball:
                await self._cleanup_basketball_service()

    @observe(name="generate_response")
    async def _generate_response(
        self,
        query: str,
        data_points: List[DataPoint],
        context: Optional[ConversationContext] = None
    ) -> ResearchResponse:
        """[LLM Call 2] Generate the final response"""
        try:
            # Prepare data for the LLM
            data_context = {
                "query": query,
                "data_points": [dp.model_dump(mode='json') for dp in data_points],
                "context": context.model_dump(mode='json') if context else {}
            }
            
            # Get the current production prompt from Langfuse
            prompt = get_response_generation_prompt()
            
            # Compile the prompt with variables
            compiled_prompt = prompt.compile(data_context=json.dumps(data_context))
            
            result = await structured_llm_call(
                prompt=compiled_prompt,
                messages=[{"role": "user", "content": json.dumps(data_context)}]
            )
            
            # Ensure all datetime objects in context_updates are converted to strings
            if "context_updates" in result:
                for key, value in result["context_updates"].items():
                    if isinstance(value, datetime):
                        result["context_updates"][key] = value.isoformat()
            
            return ResearchResponse(
                response=result["response"],
                data_points=data_points,
                suggested_questions=result["suggested_questions"],
                context_updates=ConversationContext(**result["context_updates"]),
                confidence_score=result["confidence_score"]
            )
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    @observe(name="process_request")
    @redis_cache(ttl=3600, prefix="research_chain", serialize_json=True)
    async def process_request(self, request: ResearchRequest) -> ResearchResponse:
        """Process a research request"""
        try:
            # Step 1: Analyze Query
            analysis = await self._analyze_query(request)
            
            # Step 2: Gather Data
            data_points = await self._gather_data(analysis, request)
            
            # Step 3: Generate Response
            response = await self._generate_response(
                query=request.query,
                data_points=data_points,
                context=request.context
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}", exc_info=True)
            raise

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup_basketball_service()

    async def _cleanup_basketball_service(self):
        """Clean up basketball service resources"""
        if self.basketball:
            try:
                await self.basketball.__aexit__(None, None, None)
                self.basketball = None
            except Exception as e:
                logger.error(f"Error cleaning up basketball service: {str(e)}")