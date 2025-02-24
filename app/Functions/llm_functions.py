from typing import Optional, List, Dict, Any, Union
import logging
from datetime import datetime, UTC
import asyncio
import re
import json
from langfuse.decorators import observe
from langfuse import Langfuse
import openai
from ..config.langfuse_init import langfuse  # Use the initialized Langfuse instance
from ..services.perplexity import PerplexityService, PerplexityResponse
from ..services.goalserve import GoalserveNBAService
from ..services.supabase import SupabaseService

from ..models.betting_models import (
    QueryAnalysis,
    QuickResearchResult,
    DeepResearchResult,
    DataPoint,
    SportType,
    Citation,
    BettingInsight,
    RiskFactor
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Using the latest model for best performance
model = "gpt-4o-mini"

@observe(name="analyze_query")
async def analyze_query(user_input: str) -> QueryAnalysis:
    """Initial analysis to determine research path and extract key information"""
    logger.info("Starting query analysis")
    
    try:
        # Create a system prompt that guides the model to extract structured information
        system_prompt = """You are a sports betting query analyzer. Your task is to analyze betting queries and extract structured information.
        
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
        }
        
        DO NOT include any explanatory text, just the JSON object.
        Ensure all team names are complete and standardized (e.g., "Denver Nuggets" not just "Nuggets").
        Set is_deep_research to true if the query asks about specific matchups, trends, or detailed analysis.
        
        For NBA teams, always use the official team names:
        - Denver Nuggets, Indiana Pacers, Miami Heat, Atlanta Hawks, Brooklyn Nets
        - Washington Wizards, LA Clippers, Detroit Pistons, Charlotte Hornets
        - Sacramento Kings, Portland Trail Blazers, Utah Jazz, Minnesota Timberwolves
        - Oklahoma City Thunder, Chicago Bulls, Philadelphia 76ers, Golden State Warriors
        - Los Angeles Lakers, Boston Celtics, New York Knicks, Toronto Raptors
        - Cleveland Cavaliers, Dallas Mavericks, Houston Rockets, San Antonio Spurs
        - Phoenix Suns, Memphis Grizzlies, Milwaukee Bucks, New Orleans Pelicans
        - Orlando Magic
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        # Get analysis from GPT-4o-mini
        completion = openai.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1  # Low temperature for consistent structured output
        )
        
        # Extract and parse the JSON response
        analysis_json = completion.choices[0].message.content.strip()
        
        # Clean the JSON response
        if analysis_json.startswith("```"):
            analysis_json = analysis_json.split("```")[1]
        if analysis_json.startswith("json"):
            analysis_json = analysis_json[4:]
        analysis_json = analysis_json.strip()
        
        # Parse the cleaned JSON into our QueryAnalysis model
        analysis_dict = json.loads(analysis_json)
        
        # Map the sport type to our SportType enum
        sport_map = {
            "basketball": SportType.BASKETBALL,
            "football": SportType.FOOTBALL,
            "baseball": SportType.BASEBALL,
            "hockey": SportType.HOCKEY,
            "soccer": SportType.SOCCER
        }
        
        # Create the QueryAnalysis object
        return QueryAnalysis(
            raw_query=analysis_dict["raw_query"],
            sport_type=sport_map.get(analysis_dict.get("sport_type", "").lower(), SportType.OTHER),
            teams=analysis_dict.get("teams", {}),
            players=analysis_dict.get("players", []),
            bet_type=analysis_dict.get("bet_type", ""),
            odds_mentioned=analysis_dict.get("odds_mentioned"),
            game_date=analysis_dict.get("game_date"),
            matchup_focus=analysis_dict.get("matchup_focus"),
            is_deep_research=analysis_dict.get("is_deep_research", False),
            confidence_score=analysis_dict.get("confidence_score", 0.5),
            required_data_sources=analysis_dict.get("required_data_sources", [])
        )
            
    except Exception as e:
        logger.error(f"Error in analyze_query: {str(e)}", exc_info=True)
        raise

@observe(name="quick_research")
async def quick_research(query: QueryAnalysis) -> QuickResearchResult:
    """
    Perform quick research using Perplexity AI's combined LLM and web search capabilities.
    
    Args:
        query: Analyzed query containing sport type and other metadata
        
    Returns:
        QuickResearchResult with summary, insights, and citations
    """
    logger.info(f"Starting quick research for {query.sport_type}")
    
    try:
        # Construct a focused research query
        research_query = f"""
        Analyze betting opportunities for {query.raw_query}
        Focus on:
        - Current odds and line movements
        - Recent performance metrics
        - Key injuries or roster changes
        - Relevant news that could impact betting
        """
        
        async with PerplexityService() as perplexity:
            result: PerplexityResponse = await perplexity.quick_research(
                query=research_query,
                search_recency="day"  # Focus on very recent information for betting
            )
            
            # Convert Perplexity citations to our Citation model
            citations = []
            if result.citations:
                for cite in result.citations:
                    citations.append(Citation(
                        url=cite.url,
                        title=cite.title,
                        snippet=cite.snippet,
                        published_date=cite.published_date
                    ))
            
            # Create the research result
            return QuickResearchResult(
                summary=result.content,
                key_points=extract_key_points(result.content),
                confidence_score=calculate_confidence_score(result),
                deep_research_recommended=should_recommend_deep_research(result),
                citations=citations,
                related_questions=result.related_questions or [],  # Convert None to empty list
                last_updated=datetime.now(UTC).isoformat()  # Use timezone-aware UTC
            )
            
    except Exception as e:
        logger.error(f"Error in quick_research: {str(e)}", exc_info=True)
        raise

def extract_key_points(content: str) -> List[str]:
    """Extract key betting insights from the content"""
    points = []
    
    # Handle empty content case
    if not content.strip():
        return ["No content available"]
        
    for line in content.split("\n"):
        line = line.strip()
        # Match bullet points, numbered lists, or lines starting with key betting terms
        if (line.startswith(("-", "•", "*")) or 
            any(line.startswith(f"{i}.") for i in range(1, 10)) or
            any(line.lower().startswith(term) for term in ["odds:", "line:", "injury:", "update:"])):
            # Clean up the line by removing bullet points and other markers
            clean_line = line.lstrip("- •*1234567890. ")
            if clean_line:  # Only add non-empty lines
                points.append(clean_line)
    
    # If no bullet points found, try to break content into meaningful segments
    if not points and content.strip():
        sentences = [s.strip() for s in content.split(".") if s.strip()]
        points = [s + "." for s in sentences if len(s) > 20]  # Only include substantial sentences
        
        # If still no points, use the entire content as one point
        if not points:
            points = [content.strip()]
    
    return points

def calculate_confidence_score(result: PerplexityResponse) -> float:
    """Calculate confidence score based on citations and content"""
    # Start with base confidence
    confidence = 0.7
    
    # Adjust based on citations
    if result.citations:
        confidence += min(len(result.citations) * 0.1, 0.2)  # Up to 0.2 boost for citations
        
    # Cap at 0.95 to leave room for uncertainty
    return min(confidence, 0.95)

def should_recommend_deep_research(result: PerplexityResponse) -> bool:
    """Determine if deep research is recommended based on the quick research results"""
    # Recommend deep research if:
    # 1. We have multiple citations indicating complexity
    # 2. There are related questions suggesting more angles to explore
    # 3. The content suggests uncertainty or multiple factors
    has_many_citations = len(result.citations or []) >= 3
    has_related_questions = len(result.related_questions or []) >= 2
    content_length = len(result.content.split())
    
    return has_many_citations or has_related_questions or content_length > 200

@observe(name="deep_research")
async def deep_research(query: QueryAnalysis, user_id: Optional[str] = None) -> DeepResearchResult:
    """
    Perform comprehensive research using multiple data sources
    
    Args:
        query: Analyzed query containing sport type and other metadata
        user_id: Optional user ID for personalized insights
        
    Returns:
        DeepResearchResult with comprehensive analysis
    """
    logger.info(f"Starting deep research for {query.sport_type}")
    
    try:
        # Get team names from the query analysis
        teams = list(query.teams.values())
        if not teams:
            raise ValueError("No teams found in query analysis")
        
        # Initialize services
        perplexity = PerplexityService()
        goalserve = GoalserveNBAService()
        supabase = SupabaseService()
        
        # Gather data from all sources in parallel
        data_points = []
        async with perplexity, goalserve:
            # Define all the tasks we want to run in parallel
            tasks = []
            
            # Add tasks for each team
            for team in teams:
                tasks.extend([
                    # Perplexity web search for each team
                    perplexity.quick_research(
                        query=f"Latest news, injuries, and betting trends for {team}",
                        search_recency="day"
                    ),
                    
                    # Goalserve NBA data - using all available endpoints
                    goalserve.get_team_stats(team),  # {team_id}_team_stats
                    goalserve.get_player_stats(team),  # {team_id}_stats
                    goalserve.get_injuries(team),  # {team_id}_injuries
                ])
            
            # Add common tasks
            tasks.extend([
                goalserve.get_upcoming_games(teams[0]),  # nba-schedule
            ])
            
            # Add user history tasks if user_id is provided
            if user_id:
                tasks.extend([
                    supabase.get_user_bets(user_id, sport="basketball", days_back=30),
                    supabase.get_user_stats(user_id, sport="basketball"),
                    supabase.get_similar_bets(
                        sport="basketball",
                        bet_type=query.bet_type if query.bet_type else "any",
                        days_back=30
                    )
                ])
            
            # Execute all tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error in task {i}: {str(result)}")
                    continue
                
                # Add successful results to data points
                if result:
                    data_points.append(DataPoint(
                        source=tasks[i].__qualname__,
                        content=result.model_dump() if hasattr(result, 'model_dump') else str(result)
                    ))
        
        # Combine all data into a coherent context for the LLM
        context = create_analysis_context(query, data_points)
        
        # Use GPT-4o-mini to analyze the data
        messages = [
            {
                "role": "system",
                "content": """You are an expert sports betting analyst specializing in NBA betting analysis.
                Analyze the provided data and generate comprehensive betting insights.
                Focus on:
                1. Current odds and line movements
                2. Team performance metrics and trends
                3. Player availability and impact
                4. Historical betting patterns
                5. Risk factors and confidence level
                
                IMPORTANT: Return ONLY a raw JSON object matching the DeepResearchResult model with the following structure:
                {
                    "summary": "Brief executive summary of the analysis",
                    "insights": [
                        {
                            "category": "odds",  // Category can be: odds, performance, injury, etc.
                            "insight": "Key insight about the betting opportunity",
                            "impact": "How this affects betting decisions",
                            "confidence": 0.85,  // Float between 0 and 1
                            "supporting_data": ["Data point 1", "Data point 2"]  // Optional
                        }
                    ],
                    "risk_factors": [
                        {
                            "factor": "Description of the risk factor",
                            "severity": "high",  // Must be: "low", "medium", or "high"
                            "mitigation": "Possible ways to mitigate this risk"  // Optional
                        }
                    ],
                    "recommended_bet": "Recommended betting action based on analysis",
                    "odds_analysis": {
                        "current_line": -5.5,
                        "line_movement": "stable",
                        "market_sentiment": "balanced"
                    },
                    "historical_context": "Relevant historical betting patterns and trends",
                    "confidence_score": 0.75,  // Float between 0 and 1
                    "citations": [
                        {
                            "url": "https://example.com/source",
                            "title": "Source Title",
                            "snippet": "Relevant excerpt",
                            "published_date": "2024-02-23T00:00:00Z"
                        }
                    ],
                    "last_updated": "2024-02-23T12:34:56Z"
                }
                
                DO NOT wrap the JSON in markdown code blocks or any other formatting.
                DO NOT include any explanatory text before or after the JSON.
                The JSON should start with { and end with } with no other characters.
                ENSURE all required fields are present and properly formatted.
                For risk_factors, severity MUST be one of: "low", "medium", "high" as a string."""
            },
            {"role": "user", "content": context}
        ]
        
        # The new OpenAI client doesn't use await with create()
        completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2  # Lower temperature for more focused analysis
        )

        # Parse the LLM response into our result model
        analysis = completion.choices[0].message.content
        
        # Clean the JSON response
        # Remove any markdown code block markers and whitespace
        cleaned_json = analysis.strip()
        if cleaned_json.startswith("```"):
            cleaned_json = cleaned_json.split("```")[1]
        if cleaned_json.startswith("json"):
            cleaned_json = cleaned_json[4:]
        cleaned_json = cleaned_json.strip()
        
        try:
            return DeepResearchResult.model_validate_json(cleaned_json)
        except Exception as e:
            logger.error(f"Error parsing JSON response: {cleaned_json}")
            logger.error(f"Validation error: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error in deep_research: {str(e)}", exc_info=True)
        raise

def create_analysis_context(query: QueryAnalysis, data_points: List[DataPoint]) -> str:
    """Create a structured context for the LLM to analyze"""
    context = {
        "query": query.model_dump(),
        "data": {dp.source: dp.content for dp in data_points}
    }
    return str(context)  # Convert to string for LLM input

@observe(name="generate_final_response")
async def generate_final_response(
    query: str,
    research_result: Union[QuickResearchResult, DeepResearchResult],
    is_deep_research: bool
) -> Dict[str, Any]:
    """
    Final LLM call to generate a more natural, conversational response based on the research results.
    
    Args:
        query: The original user query
        research_result: The structured research result (either quick or deep)
        is_deep_research: Whether this is a deep research result
        
    Returns:
        Enhanced response with natural language elements
    """
    logger.info("Generating final conversational response")
    
    try:
        # Create a system prompt that guides the model to generate a conversational response
        system_prompt = """You are a professional sports betting analyst having a conversation with a bettor.
        Your task is to take structured research results and convert them into a natural, conversational response.
        
        Guidelines:
        1. Use a conversational, friendly tone while maintaining professionalism
        2. Directly address the user's specific question
        3. Highlight the most important insights first
        4. Explain your confidence level and reasoning
        5. Include specific data points that support your recommendation
        6. Acknowledge uncertainties and risks
        7. End with a clear recommendation
        
        The user's original query and the structured research results will be provided.
        Your response should feel like advice from a knowledgeable friend rather than a data dump.
        """
        
        # Convert the research result to a JSON string
        result_json = research_result.model_dump_json()
        
        # Create the user message with the query and research results
        user_message = f"""
        Original Query: {query}
        
        Research Results: {result_json}
        
        Please convert this into a natural, conversational response that directly answers the query.
        """
        
        # Make the OpenAI API call
        response = await openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,  # Slightly higher temperature for more natural language
            max_tokens=1000
        )
        
        # Extract the response content
        conversational_response = response.choices[0].message.content
        
        # Create an enhanced version of the original result
        enhanced_result = research_result.model_dump()
        enhanced_result["conversational_response"] = conversational_response
        
        return enhanced_result
        
    except Exception as e:
        logger.error(f"Error generating final response: {str(e)}", exc_info=True)
        # Return the original result if there's an error
        return research_result.model_dump() 