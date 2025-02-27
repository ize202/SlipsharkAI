from datetime import datetime
import uuid
import asyncio
from typing import List, Dict, Any, Union
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
from app.services.api_sports_basketball import APISportsBasketballService
from app.services.supabase import SupabaseService
from app.functions.llm_functions import structured_llm_call, raw_llm_call, generate_final_response
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
        self.sports_api = APISportsBasketballService()
        self.supabase = SupabaseService()
        self._sports_api_context = None

    async def _ensure_sports_api(self):
        """Ensure sports API is initialized in async context"""
        if not self._sports_api_context:
            self._sports_api_context = await self.sports_api.__aenter__()
        return self._sports_api_context

    async def _cleanup_sports_api(self):
        """Cleanup sports API context if initialized"""
        if self._sports_api_context:
            await self.sports_api.__aexit__(None, None, None)
            self._sports_api_context = None

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
        
        Also determine if this query requires:
        - Quick Research: Basic odds and recent performance
        - Deep Research: Detailed analysis, historical data, multiple data sources
        
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
            "confidence_score": 0.8
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
            "citations": []
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
        tasks = []

        # Always start with web search
        tasks.append(self.perplexity.quick_research(
            query=analysis.raw_query,
            search_recency="day"
        ))

        # For deep research, add additional data sources
        if analysis.recommended_mode == ResearchMode.DEEP:
            if analysis.sport_type == SportType.BASKETBALL:
                # Initialize sports API context
                await self._ensure_sports_api()
                
                # Add sports API tasks for each team
                for team in analysis.teams.values():
                    if team:
                        tasks.extend([
                            self.sports_api.get_team_stats(team),
                            self.sports_api.get_player_stats(team),
                            self.sports_api.get_upcoming_games(team)
                        ])
                
                # Add user data if context is available
                if request.context and request.context.user_id:
                    tasks.extend([
                        self.supabase.get_user_bets(
                            request.context.user_id,
                            sport="basketball",
                            days_back=30
                        ),
                        self.supabase.get_user_stats(
                            request.context.user_id,
                            sport="basketball"
                        ),
                        self.supabase.get_similar_bets(
                            sport="basketball",
                            bet_type=analysis.bet_type if analysis.bet_type else "any",
                            days_back=30
                        )
                    ])

        try:
            # Execute all tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error in data gathering task {i}: {str(result)}")
                else:
                    content = result.model_dump() if hasattr(result, 'model_dump') else result
                    data_points.append(DataPoint(
                        source=f"task_{i}",
                        content=content,
                        timestamp=datetime.utcnow(),
                        confidence=0.9
                    ))

            return data_points
        finally:
            # Always cleanup sports API context after use
            await self._cleanup_sports_api()

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
                messages=[{"role": "user", "content": json.dumps(context)}],
                temperature=0.3
            )
            
            # Convert to appropriate response type
            if analysis.recommended_mode == ResearchMode.DEEP:
                return DeepResearchResponse(**result)
            else:
                return QuickResearchResponse(**result)
                
        except Exception as e:
            logger.error(f"Error in data analysis: {str(e)}", exc_info=True)
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
            enhanced_result = await generate_final_response(
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

            # Create sources
            sources = [
                Source(
                    name=dp.source,
                    type="api" if "api" in dp.source else "web_search",
                    timestamp=dp.timestamp,
                    confidence=dp.confidence
                ) for dp in data_points
            ]

            # Return final response
            return ResearchResponse(
                summary=enhanced_result.get("conversational_response", analysis_result.summary),
                insights=analysis_result.insights if hasattr(analysis_result, 'insights') else [],
                recommendations=enhanced_result.get("next_steps", []),
                risk_factors=analysis_result.risk_factors if hasattr(analysis_result, 'risk_factors') else [],
                sources=sources,
                metadata=metadata
            )
        
        except Exception as e:
            logger.error(f"Error processing research request: {str(e)}", exc_info=True)
            raise