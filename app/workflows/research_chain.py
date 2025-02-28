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
    Insight,
    RiskFactor,
    Source,
    ResearchMetadata,
    ResearchMode,
    SportType,
    Citation,
    QuickResearchResponse,
    DeepResearchResponse
)
from app.services.perplexity import PerplexityService
from app.services.basketball_service import BasketballService
from app.services.supabase import SupabaseService
from app.utils.llm_utils import structured_llm_call, json_serialize
from app.config import get_logger
from langfuse.decorators import observe

logger = get_logger(__name__)

class ResearchChain:
    """
    Research chain that handles both quick and deep research modes.
    Orchestrates the workflow between different services and LLM calls.
    
    Flow:
    1. Query Analysis (LLM Call 1)
    2. Mode Decision
    3. Data Gathering (Quick: Web Search, Deep: Web Search + Sports API + User Data)
    4. Analysis (LLM Call 2)
    5. Response Generation (LLM Call 3)
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

    async def _cleanup_basketball_service(self):
        """Cleanup basketball service if initialized"""
        if self.basketball:
            await self.basketball.__aexit__(None, None, None)
            self.basketball = None

    # Prompts moved to a separate section for better organization
    class Prompts:
        QUERY_ANALYSIS = """You are a sports betting query analyzer. Your task is to analyze betting queries and extract structured information.
        
        Extract the following information:
        1. Sport type (e.g., basketball, football, etc.)
        2. Teams mentioned (both teams if available)
        3. Specific players mentioned
        4. Type of bet (spread, moneyline, over/under, etc.)
        5. Any specific odds or lines mentioned
        6. Timeframe (when the game is)
        7. Any specific matchups or aspects of interest
        8. Season or year mentioned (e.g., "2022-2023 season" or "last season")
        
        Research Mode Decision Rules:
        Quick Research (ONLY for these cases):
        - General news or updates about teams/players without needing specific stats
        - Simple yes/no questions that can be answered with recent news
        - Basic information that can be found through web search
        - Questions about game schedules or times
        
        Deep Research (Required for ANY of these cases):
        - Anything involving odds, lines, or betting markets
        - Requests for standings, statistics, or records
        - Team performance analysis or comparisons
        - Player statistics or performance metrics
        - Historical data or trends
        - Matchup analysis
        - Injury impact assessment
        - League-wide data or standings
        - Win/loss records or streaks
        - Specific game or player props
        - Questions about betting strategy or patterns
        
        Return ONLY a JSON object with this exact structure:
        {
            "raw_query": "the original query",
            "sport_type": "basketball",  // lowercase sport name
            "teams": {
                "team1": "full team name",
                "team2": "full team name"  // if mentioned
            },
            "players": ["player1", "player2"],  // if mentioned
            "bet_type": "spread",  // or appropriate bet type
            "odds_mentioned": "-5.5",  // if any odds are mentioned
            "game_date": "2024-02-24",  // if mentioned
            "season_mentioned": "2023",  // if a specific season is mentioned (use starting year)
            "matchup_focus": "specific matchup or aspect of interest",
            "required_data": ["team_stats", "player_stats", "odds"],
            "recommended_mode": "quick",  // or "deep"
            "confidence_score": 0.85  // how confident we are in this analysis
        }"""

        QUICK_ANALYSIS = """You are a sports betting analyst providing quick insights.
        Analyze the provided data and generate quick betting insights.
        
        Focus on:
        1. Current odds and lines
        2. Basic team/player information
        3. Recent performance
        4. Key injuries or changes
        
        Return a JSON object with:
        {
            "summary": "Brief analysis summary",
            "insights": [
                {
                    "category": "odds/performance/injuries",
                    "insight": "Key insight",
                    "impact": "Betting impact",
                    "confidence": 0.8,
                    "supporting_data": ["data1", "data2"]
                }
            ],
            "risk_factors": [
                {
                    "factor": "Risk name",
                    "severity": "high/medium/low",
                    "mitigation": "How to handle this risk"
                }
            ],
            "confidence_score": 0.8,
            "deep_research_recommended": false,
            "last_updated": "2024-02-27T23:37:45Z"
        }"""

        DEEP_ANALYSIS = """You are a sports betting analyst providing comprehensive research.
        Analyze all available data sources to generate detailed betting insights.
        
        Consider:
        1. Historical performance and trends
        2. Team and player statistics
        3. Matchup analysis
        4. Injury impacts
        5. Recent news and developments
        6. Betting patterns and line movements
        
        Return a JSON object with:
        {
            "summary": "Comprehensive analysis",
            "insights": [
                {
                    "category": "category",
                    "insight": "Detailed insight",
                    "impact": "Betting impact",
                    "confidence": 0.8,
                    "supporting_data": ["data1", "data2"]
                }
            ],
            "risk_factors": [
                {
                    "factor": "Risk name",
                    "severity": "high/medium/low",
                    "mitigation": "Risk mitigation strategy"
                }
            ],
            "recommended_bet": "Specific bet recommendation",
            "odds_analysis": {
                "current_odds": "Current odds if available",
                "line_movement": "Recent line movement",
                "value_assessment": "Value analysis"
            },
            "confidence_score": 0.8,
            "citations": [],
            "metadata": {},
            "last_updated": "2024-02-27T23:37:45Z",
            "conversational_response": "Natural language version of the analysis"
        }"""

        RESPONSE_GENERATION = """You are a professional sports betting analyst having a conversation with a bettor.
        Convert the structured analysis into a natural, conversational response.
        
        Guidelines:
        1. Use a conversational, friendly tone while maintaining professionalism
        2. Directly address the user's specific question
        3. Highlight the most important insights first
        4. Explain your confidence level and reasoning
        5. Include specific data points that support your recommendation
        6. Acknowledge uncertainties and risks
        
        Return a JSON object with:
        {
            "conversational_response": "Natural language response",
            "key_points": ["point1", "point2"],
            "confidence_explanation": "Why we're confident/uncertain",
            "next_steps": ["suggestion1", "suggestion2"]
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
                # User explicitly specified mode
                analysis_result["recommended_mode"] = request.mode
            else:
                # Auto mode: Use LLM's recommendation
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
                content = web_result.model_dump() if hasattr(web_result, 'model_dump') else web_result
                data_points.append(DataPoint(
                    source="web_search",
                    content=content,
                    timestamp=datetime.utcnow(),
                    confidence=0.8
                ))
        except Exception as e:
            logger.error(f"Error in web search: {str(e)}")

        # For deep research, add additional data sources
        if analysis.recommended_mode == ResearchMode.DEEP:
            if analysis.sport_type == SportType.BASKETBALL:
                # Initialize basketball service
                basketball = await self._ensure_basketball_service()
                
                try:
                    # Determine the season to use
                    season = basketball.determine_season(analysis.game_date)
                    logger.info(f"Using basketball season: {season}")
                    
                    # Process teams
                    team1 = analysis.teams.get("team1")
                    team2 = analysis.teams.get("team2")
                    
                    # If we have both teams, get matchup data
                    if team1 and team2:
                        matchup_data = await basketball.get_matchup_data(team1, team2, season)
                        data_points.append(DataPoint(
                            source=f"matchup_{team1}_vs_{team2}",
                            content=matchup_data,
                            timestamp=datetime.utcnow(),
                            confidence=0.9
                        ))
                    else:
                        # Process individual teams
                        for team_key, team_name in analysis.teams.items():
                            if team_name:
                                team_data = await basketball.get_team_data(team_name, season)
                                data_points.append(DataPoint(
                                    source=f"team_data_{team_name}",
                                    content=team_data,
                                    timestamp=datetime.utcnow(),
                                    confidence=0.9
                                ))
                    
                    # Process players
                    for player_name in analysis.players:
                        # Try to associate player with a team if possible
                        team_name = None
                        if len(analysis.teams.values()) == 1:
                            # If only one team mentioned, assume player is on that team
                            team_name = next(iter(analysis.teams.values()))
                            
                        player_data = await basketball.get_player_data(
                            player_name, 
                            season,
                            team_name
                        )
                        data_points.append(DataPoint(
                            source=f"player_data_{player_name}",
                            content=player_data,
                            timestamp=datetime.utcnow(),
                            confidence=0.8
                        ))
                    
                    # If no specific teams or players mentioned, get league data
                    if not analysis.teams and not analysis.players:
                        league_data = await basketball.get_league_data(season)
                        data_points.append(DataPoint(
                            source=f"league_data_basketball",
                            content=league_data,
                            timestamp=datetime.utcnow(),
                            confidence=0.7
                        ))
                        
                except Exception as e:
                    logger.error(f"Error gathering basketball data: {str(e)}", exc_info=True)
                finally:
                    # We don't cleanup the basketball service here to allow reuse
                    pass
            
            # Add user data if context is available
            # if request.context and request.context.user_id:
            #     try:
            #         user_tasks = [
            #             self.supabase.get_user_bets(
            #                 request.context.user_id,
            #                 sport=str(analysis.sport_type),
            #                 days_back=30
            #             ),
            #             self.supabase.get_user_stats(
            #                 request.context.user_id,
            #                 sport=str(analysis.sport_type)
            #             ),
            #             self.supabase.get_similar_bets(
            #                 sport=str(analysis.sport_type),
            #                 bet_type=analysis.bet_type if analysis.bet_type else "any",
            #                 days_back=30
            #             )
            #         ]
                    
            #         # Execute user data tasks
            #         user_results = await asyncio.gather(*user_tasks, return_exceptions=True)
                    
            #         # Process user results
            #         for i, result in enumerate(user_results):
            #             if isinstance(result, Exception):
            #                 logger.error(f"Error in user data task {i}: {str(result)}")
            #             else:
            #                 source_name = ["user_bets", "user_stats", "similar_bets"][i]
            #                 data_points.append(DataPoint(
            #                     source=source_name,
            #                     content=result,
            #                     timestamp=datetime.utcnow(),
            #                     confidence=0.7
            #                 ))
            #     except Exception as e:
            #         logger.error(f"Error gathering user data: {str(e)}", exc_info=True)

        return data_points

    @observe(name="analyze_data")
    async def _analyze_data(
        self,
        request: ResearchRequest,
        analysis: QueryAnalysis,
        data_points: List[DataPoint]
    ) -> Union[QuickResearchResponse, DeepResearchResponse]:
        """[LLM Call 2] Analyze gathered data based on research mode"""
        try:
            # Prepare data context
            context = {
                "query": request.query,
                "analysis": analysis.model_dump(),
                "data_points": [dp.model_dump() for dp in data_points]
            }
            
            # Choose analysis prompt based on mode
            prompt = self.Prompts.DEEP_ANALYSIS if analysis.recommended_mode == ResearchMode.DEEP else self.Prompts.QUICK_ANALYSIS
            
            # Get analysis result
            result = await structured_llm_call(
                prompt=prompt,
                messages=[{"role": "user", "content": json_serialize(context)}],
                temperature=0.3
            )
            
            # Add current timestamp
            result["last_updated"] = datetime.utcnow().isoformat() + "Z"
            
            # Convert to appropriate response type
            if analysis.recommended_mode == ResearchMode.DEEP:
                return DeepResearchResponse(**result)
            else:
                return QuickResearchResponse(**result)
                
        except Exception as e:
            logger.error(f"Error in data analysis: {str(e)}", exc_info=True)
            raise

    @observe(name="generate_final_response")
    async def _generate_final_response(
        self,
        query: str,
        research_result: Union[QuickResearchResponse, DeepResearchResponse],
        is_deep_research: bool
    ) -> Dict[str, Any]:
        """[LLM Call 3] Generate natural conversational response from structured analysis"""
        try:
            # Prepare context for response generation
            context = {
                "original_query": query,
                "analysis_result": research_result.model_dump(),
                "mode": "deep" if is_deep_research else "quick"
            }
            
            # Generate conversational response
            result = await structured_llm_call(
                prompt=self.Prompts.RESPONSE_GENERATION,
                messages=[{"role": "user", "content": json_serialize(context)}],
                temperature=0.7  # Slightly higher temperature for more natural language
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in response generation: {str(e)}", exc_info=True)
            raise

    @observe(name="process_request")
    async def process_request(self, request: ResearchRequest) -> ResearchResponse:
        """Main entry point for processing research requests"""
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Query Analysis (LLM Call 1)
            analysis = await self._analyze_query(request)
            logger.info(f"Query analyzed. Recommended mode: {analysis.recommended_mode}")
            
            # Step 2: Gather Data
            data_points = await self._gather_data(analysis, request)
            logger.info(f"Gathered {len(data_points)} data points")
            
            # Step 3: Analyze Data (LLM Call 2)
            analysis_result = await self._analyze_data(request, analysis, data_points)
            
            # Step 4: Generate Final Response (LLM Call 3)
            enhanced_result = await self._generate_final_response(
                query=request.query,
                research_result=analysis_result,
                is_deep_research=(analysis.recommended_mode == ResearchMode.DEEP)
            )
            
            # Create metadata
            metadata = ResearchMetadata(
                query_id=str(uuid.uuid4()),
                mode_used=analysis.recommended_mode,
                processing_time=(datetime.utcnow() - start_time).total_seconds(),
                confidence_score=analysis_result.confidence_score,
                timestamp=datetime.utcnow()
            )

            # Return final response
            return ResearchResponse(
                summary=enhanced_result.get("conversational_response", analysis_result.summary),
                insights=analysis_result.insights if hasattr(analysis_result, 'insights') else [],
                recommendations=enhanced_result.get("next_steps", []),
                risk_factors=analysis_result.risk_factors if hasattr(analysis_result, 'risk_factors') else [],
                sources=[
                    Source(
                        name=dp.source,
                        type="api" if "api" in dp.source else "web_search",
                        timestamp=dp.timestamp,
                        data=dp.content if isinstance(dp.content, dict) else None
                    ) for dp in data_points
                ],
                metadata=metadata,
                data={
                    dp.source: dp.content
                    for dp in data_points
                    if isinstance(dp.content, dict)
                }
            )
        
        except Exception as e:
            logger.error(f"Error processing research request: {str(e)}", exc_info=True)
            raise
            
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Clean up the basketball service
        await self._cleanup_basketball_service()