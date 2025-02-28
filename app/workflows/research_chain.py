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

    class Prompts:
        QUERY_ANALYSIS = """You are a sports betting query analyzer. Your task is to analyze betting queries and extract structured information.
        
        Extract the following information:
        1. Sport type (e.g., basketball, football, etc.)
        2. Teams mentioned (both teams if available)
        3. Specific players mentioned
        4. Type of bet (spread, moneyline, over/under, etc.)
        5. Any specific odds or lines mentioned
        6. Timeframe (when the game is)
        
        Research Mode Decision Rules:
        - Quick Research: For general news, updates, schedules
        - Deep Research: For odds, stats, analysis, or specific insights
        
        Return ONLY a JSON object with this exact structure (no comments allowed):
        {
            "raw_query": "the original query",
            "sport_type": "basketball",
            "teams": {
                "team1": "full team name",
                "team2": "full team name"
            },
            "players": ["player1", "player2"],
            "bet_type": "spread",
            "odds_mentioned": "-5.5",
            "game_date": "2024-02-24",  # Must be a string in ISO format (YYYY-MM-DD) or descriptive text like "tonight", "tomorrow"
            "required_data": ["team_stats", "player_stats", "odds"],
            "recommended_mode": "quick",
            "confidence_score": 0.85
        }"""

        RESPONSE_GENERATION = """You are a professional sports betting analyst having a conversation with a bettor.
        Convert the gathered data into a natural, conversational response.
        
        Guidelines:
        1. Use a conversational, friendly tone while maintaining professionalism
        2. Directly address the user's specific question
        3. Highlight the most important insights first
        4. Include specific data points that support your analysis
        5. Suggest relevant follow-up questions
        
        Return a JSON object with:
        {
            "response": "Natural language response",
            "suggested_questions": ["question1", "question2"],
            "confidence_score": 0.85,
            "context_updates": {
                "teams": ["team1", "team2"],
                "players": ["player1", "player2"],
                "sport": "basketball",
                "game_date": "2024-02-24",
                "bet_type": "spread"
            }
        }"""

    @observe(name="analyze_query")
    async def _analyze_query(self, request: ResearchRequest) -> QueryAnalysis:
        """[LLM Call 1] Analyze the user's query and determine research mode"""
        try:
            analysis_result = await structured_llm_call(
                prompt=self.Prompts.QUERY_ANALYSIS,
                messages=[{"role": "user", "content": request.query}],
                temperature=0.1
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
            web_result = await self.perplexity.quick_research(
                query=analysis.raw_query,
                search_recency="day"
            )
            if web_result:
                # Handle both object and dictionary cases (for cached results)
                content = web_result.get('content') if isinstance(web_result, dict) else web_result.content
                data_points.append(DataPoint(
                    source="perplexity",
                    content=content,
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
            
            result = await structured_llm_call(
                prompt=self.Prompts.RESPONSE_GENERATION,
                messages=[{"role": "user", "content": json.dumps(data_context)}],
                temperature=0.7
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