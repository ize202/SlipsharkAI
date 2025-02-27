from datetime import datetime
import uuid
import asyncio
from typing import List, Dict, Any
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
    SportType
)
from app.services.perplexity import PerplexityService
from app.services.api_sports_basketball import APISportsBasketballService
from app.services.supabase import SupabaseService
from app.functions.llm_functions import structured_llm_call
from app.config import get_logger

logger = get_logger(__name__)

class ResearchChain:
    """
    Research chain that handles both quick and deep research modes.
    Implements a three-step LLM chain:
    1. Query Analysis
    2. Data Analysis (Quick or Deep)
    3. Response Generation
    """

    # Query Analysis Prompt
    QUERY_ANALYSIS_PROMPT = """You are a sports betting query analyzer. Your task is to analyze betting queries and extract structured information.
    
    Extract the following information:
    1. Sport type (e.g., basketball, football, etc.)
    2. Teams mentioned (both teams if available)
    3. Specific players mentioned
    4. Type of bet (spread, moneyline, over/under, etc.)
    5. Any specific odds or lines mentioned
    6. Timeframe (when the game is)
    7. Any specific matchups or aspects of interest
    
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
        "is_deep_research": true,  // whether this needs deep analysis
        "confidence_score": 0.85,  // how confident we are in this analysis
        "required_data_sources": [
            "team_stats",
            "player_stats",
            "odds",
            "injuries",
            "news"
        ]
    }"""

    # Quick Analysis Prompt
    QUICK_ANALYSIS_PROMPT = """You are a sports betting analyst providing quick insights.
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

    # Deep Analysis Prompt
    DEEP_ANALYSIS_PROMPT = """You are a sports betting analyst providing comprehensive research.
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
        "confidence_score": 0.8
    }"""

    # Response Generation Prompt
    RESPONSE_GENERATION_PROMPT = """You are a professional sports betting analyst having a conversation with a bettor.
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

    def __init__(self):
        """Initialize services and configurations"""
        self.perplexity = PerplexityService()
        self.sports_api = APISportsBasketballService()
        self.supabase = SupabaseService()

    async def _analyze_query(self, request: ResearchRequest) -> QueryAnalysis:
        """
        [LLM Call 1] Analyze the user's query to determine intent and required data.
        """
        try:
            # Call LLM with query analysis prompt
            analysis_result = await structured_llm_call(
                prompt=self.QUERY_ANALYSIS_PROMPT,
                messages=[{"role": "user", "content": request.query}],
                temperature=0.1  # Low temperature for consistent structured output
            )
            
            # Override mode if explicitly specified in request
            if request.mode != ResearchMode.AUTO:
                analysis_result["is_deep_research"] = (request.mode == ResearchMode.DEEP)
            
            # Add recommended_mode based on is_deep_research flag
            analysis_result["recommended_mode"] = ResearchMode.DEEP if analysis_result.get("is_deep_research", False) else ResearchMode.QUICK
            
            # Convert to QueryAnalysis model
            return QueryAnalysis(**analysis_result)
            
        except Exception as e:
            logger.error(f"Error in query analysis: {str(e)}", exc_info=True)
            raise

    async def _gather_data(self, analysis: QueryAnalysis) -> List[DataPoint]:
        """
        Gather data from various sources based on the query analysis.
        Quick research only uses web search, while deep research uses all available sources.
        """
        data_points: List[DataPoint] = []
        tasks = []

        # Always include web search
        tasks.append(self.perplexity.quick_research(
            query=analysis.raw_query,
            search_recency="day"
        ))

        # For deep research, add additional data sources
        if analysis.recommended_mode == ResearchMode.DEEP:
            if analysis.sport_type == SportType.BASKETBALL:
                for team in analysis.teams.values():
                    if team:
                        tasks.extend([
                            self.sports_api.get_team_stats(team),
                            self.sports_api.get_player_stats(team),
                            self.sports_api.get_upcoming_games(team)
                        ])

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error in data gathering task {i}: {str(result)}")
            else:
                # Convert PerplexityResponse to dict if needed
                if hasattr(result, 'model_dump'):
                    content = result.model_dump()
                elif hasattr(result, 'dict'):
                    content = result.dict()
                else:
                    content = result
                    
                data_points.append(DataPoint(
                    source=f"task_{i}",
                    content=content,
                    timestamp=datetime.utcnow(),
                    confidence=0.9
                ))

        return data_points

    async def _analyze_data(
        self,
        request: ResearchRequest,
        analysis: QueryAnalysis,
        data_points: List[DataPoint]
    ) -> Dict[str, Any]:
        """Analyze gathered data using either quick or deep analysis"""
        try:
            # Convert data points to dict and handle datetime serialization
            data_points_dict = []
            for dp in data_points:
                dp_dict = dp.dict()
                # Convert datetime to string
                if 'timestamp' in dp_dict and isinstance(dp_dict['timestamp'], datetime):
                    dp_dict['timestamp'] = dp_dict['timestamp'].isoformat()
                data_points_dict.append(dp_dict)
                
            # Prepare data context
            context = {
                "query": request.query,
                "analysis": analysis.dict(),
                "data_points": data_points_dict
            }
            
            if analysis.recommended_mode == ResearchMode.DEEP:
                # Deep research path
                return await structured_llm_call(
                    prompt=self.DEEP_ANALYSIS_PROMPT,
                    messages=[{"role": "user", "content": json.dumps(context)}],
                    temperature=0.3
                )
            else:
                # Quick research path
                return await structured_llm_call(
                    prompt=self.QUICK_ANALYSIS_PROMPT,
                    messages=[{"role": "user", "content": json.dumps(context)}],
                    temperature=0.3
                )
                
        except Exception as e:
            logger.error(f"Error in data analysis: {str(e)}", exc_info=True)
            raise

    async def _generate_response(
        self,
        request: ResearchRequest,
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate final conversational response"""
        try:
            context = {
                "query": request.query,
                "analysis_result": analysis_result
            }
            
            return await structured_llm_call(
                prompt=self.RESPONSE_GENERATION_PROMPT,
                messages=[{"role": "user", "content": json.dumps(context)}],
                temperature=0.7  # Higher temperature for more natural language
            )
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            raise

    async def process_request(self, request: ResearchRequest) -> ResearchResponse:
        """
        Main entry point for processing research requests.
        Orchestrates the entire research workflow.
        """
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Query Analysis
            analysis = await self._analyze_query(request)
            
            # Step 2: Gather Data
            data_points = await self._gather_data(analysis)
            
            # Step 3: Analyze Data
            analysis_result = await self._analyze_data(request, analysis, data_points)
            
            # Step 4: Generate Response
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            enhanced_result = await self._generate_response(request, analysis_result)
            
            # Create metadata
            metadata = ResearchMetadata(
                query_id=str(uuid.uuid4()),
                mode_used=analysis.recommended_mode,
                processing_time=processing_time,
                confidence_score=analysis_result.get("confidence_score", 0.5),
                timestamp=datetime.utcnow()
            )

            # Convert insights to proper model
            insights = [
                Insight(
                    category=insight.get("category", "general"),
                    content=insight.get("insight", ""),
                    impact=insight.get("impact", ""),
                    confidence=insight.get("confidence", 0.5),
                    supporting_data=insight.get("supporting_data", [])
                ) for insight in analysis_result.get("insights", [])
            ]

            # Convert risk factors to proper model
            risk_factors = [
                RiskFactor(
                    factor=risk.get("factor", ""),
                    severity=risk.get("severity", "medium"),
                    mitigation=risk.get("mitigation", "")
                ) for risk in analysis_result.get("risk_factors", [])
            ]

            # Create sources list
            sources = []
            for data_point in data_points:
                sources.append(Source(
                    name=data_point.source,
                    type="api" if "api" in data_point.source else "web_search",
                    timestamp=data_point.timestamp,
                    confidence=data_point.confidence
                ))

            # Return the final response
            return ResearchResponse(
                summary=enhanced_result.get("conversational_response", analysis_result.get("summary", "")),
                insights=insights,
                recommendations=enhanced_result.get("next_steps", []),
                risk_factors=risk_factors,
                sources=sources,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error processing research request: {str(e)}", exc_info=True)
            raise 