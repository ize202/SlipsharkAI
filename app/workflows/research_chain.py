from datetime import datetime, timezone
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
    ConversationContext,
    ClientMetadata
)
from app.services.perplexity import PerplexityService
from app.services.basketball_service import BasketballService
from app.services.supabase import SupabaseService
from app.services.client_metadata_service import ClientMetadataService
from app.services.transformer_service import TransformerService
from app.utils.llm_utils import structured_llm_call, json_serialize
from app.utils.prompt_manager import get_query_analysis_prompt, get_response_generation_prompt
from app.config import get_logger, get_settings
from langfuse.decorators import observe
from app.utils.cache import redis_cache, get_cache_client
from app.services.date_resolution_service import DateResolutionService
from app.utils.langfuse import get_langfuse_client
from app.utils.prompt_manager import PromptManager

logger = get_logger(__name__)
settings = get_settings()
cache = get_cache_client()

class ResearchChain:
    """
    Research chain that handles both quick and deep research modes.
    Orchestrates the workflow between different services and LLM calls.
    
    Flow:
    1. Query Analysis (LLM Call 1)
    2. Data Gathering (Web Search + Sports API)
    3. Data Transformation (Sport-specific transformers)
    4. Response Generation (LLM Call 2)
    """

    def __init__(self):
        """Initialize service instances"""
        self.perplexity = PerplexityService()
        self.basketball = None  # Lazy initialization
        self.supabase = SupabaseService()
        self.client_metadata_service = ClientMetadataService()
        self.date_resolution_service = DateResolutionService()
        self.transformer_service = TransformerService()
        self.prompt_manager = PromptManager()

    async def _ensure_basketball_service(self):
        """Ensure basketball service is initialized in async context"""
        if not self.basketball:
            self.basketball = BasketballService()
            await self.basketball.__aenter__()
        return self.basketball

    @observe(name="analyze_query")
    async def _analyze_query(self, request: ResearchRequest) -> QueryAnalysis:
        """[LLM Call 1] Analyze the user's query"""
        try:
            # Get the current production prompt from Langfuse
            prompt = get_query_analysis_prompt()
            
            # Add client metadata to the context
            client_time = self.client_metadata_service.get_current_time_for_client(
                request.client_metadata
            )
            
            # Compile the prompt with variables including client time context
            compiled_prompt = prompt.compile(
                query=request.query,
                client_time=client_time.isoformat(),
                client_timezone=request.client_metadata.timezone
            )
            
            # Pre-process any date references in the query
            analysis_result = await structured_llm_call(
                prompt=compiled_prompt,
                messages=[{"role": "user", "content": request.query}]
            )
            
            # Resolve any relative dates in the analysis result
            if analysis_result.get("game_date"):
                if self.date_resolution_service.is_relative_date(analysis_result["game_date"]):
                    resolved_date = self.date_resolution_service.resolve_relative_date(
                        analysis_result["game_date"],
                        request.client_metadata
                    )
                    if resolved_date:
                        analysis_result["game_date"] = self.date_resolution_service.format_date_for_api(resolved_date)
            
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
        required_data = request.context.required_data if request.context else []
        
        try:
            # Ensure we have valid client metadata
            if not request.client_metadata:
                request.client_metadata = self.client_metadata_service.create_metadata(
                    timezone=request.timezone if hasattr(request, 'timezone') else None
                )
            
            # Always get web search data first
            perplexity_response = await self.perplexity.quick_research(
                query=analysis.raw_query
            )
            
            data_points.append(DataPoint(
                source="perplexity",
                content=perplexity_response.content,
                confidence=0.8
            ))
            
            # For deep mode or if sports data is explicitly required, get sports data
            if analysis.recommended_mode == ResearchMode.DEEP or (required_data and any(data_type in required_data for data_type in ["team_stats", "recent_games", "player_stats", "matchups"])):
                basketball = await self._ensure_basketball_service()
                
                # Get team data for each team
                raw_data = {"team_data": {}, "game_data": {}, "player_data": {}}
                
                for team_key, team in analysis.teams.items():
                    if team:
                        # Pass client metadata for proper time context in sports API calls
                        team_data = await basketball.get_team_data(
                            team_name=team,
                            client_metadata=request.client_metadata,
                            game_date=analysis.game_date,
                            include_games="recent_games" in required_data or analysis.recommended_mode == ResearchMode.DEEP,
                            include_stats="team_stats" in required_data or analysis.recommended_mode == ResearchMode.DEEP
                        )
                        
                        # Add team data to raw_data
                        raw_data["team_data"][team] = team_data
                        
                        # Also add it directly as a data point for immediate access
                        data_points.append(DataPoint(
                            source="basketball_api",
                            content=team_data,
                            confidence=0.9
                        ))
                
                # If in deep mode or player stats required, get player data
                if "player_stats" in required_data or analysis.recommended_mode == ResearchMode.DEEP:
                    for player in analysis.players:
                        if player:
                            # Get team for this player if available
                            team = next((team for team_key, team in analysis.teams.items() if team), None)
                            
                            # Pass client metadata for proper time context in sports API calls
                            player_data = await basketball.get_player_data(
                                player_name=player,
                                client_metadata=request.client_metadata,
                                team_name=team,
                                game_date=analysis.game_date
                            )
                            
                            # Add player data to raw_data
                            raw_data["player_data"][player] = player_data
                            
                            # Also add it directly as a data point
                            data_points.append(DataPoint(
                                source="basketball_api",
                                content=player_data,
                                confidence=0.9
                            ))
                
                # If in deep mode or matchups required, get matchup data
                if len(analysis.teams) >= 2 and ("matchups" in required_data or analysis.recommended_mode == ResearchMode.DEEP):
                    teams = list(analysis.teams.values())
                    matchup_data = await basketball.get_matchup_data(
                        team1_name=teams[0],
                        team2_name=teams[1],
                        client_metadata=request.client_metadata,
                        game_date=analysis.game_date
                    )
                    if matchup_data:
                        data_points.append(DataPoint(
                            source="basketball_api",
                            content={"matchup_data": matchup_data},
                            confidence=0.9
                        ))
                
                # Transform the raw data using our transformer service
                transformed_data = await self.transformer_service.transform_data(
                    sport=analysis.sport_type.lower(),
                    raw_data=raw_data,
                    required_data=required_data,
                    trace_id=request.trace_id
                )
                
                # Add transformed data to data points
                if transformed_data.team_data:
                    for team, team_data in transformed_data.team_data.items():
                        data_points.append(DataPoint(
                            source="basketball_api",
                            content=team_data,
                            confidence=0.9
                        ))
                
                if transformed_data.player_data:
                    for player, player_data in transformed_data.player_data.items():
                        data_points.append(DataPoint(
                            source="basketball_api",
                            content=player_data,
                            confidence=0.9
                        ))
                
                if transformed_data.game_data:
                    data_points.append(DataPoint(
                        source="basketball_api",
                        content={"games": transformed_data.game_data},
                        confidence=0.9
                    ))
            
            return data_points
                
        except Exception as e:
            logger.error(f"Error gathering data: {str(e)}")
            raise
        finally:
            if self.basketball:
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
            # Data points are already filtered and transformed by the transformer service
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
                data_points=data_points,  # Return original data points in response
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
        """Clean up basketball service if initialized"""
        if self.basketball:
            await self.basketball.__aexit__(None, None, None)
            self.basketball = None