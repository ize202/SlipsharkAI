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
from ..services.api_sports_basketball import APISportsBasketballService
from ..services.supabase import SupabaseService
from ..config import get_logger

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
logger = get_logger(__name__)

# Using the latest model for best performance
model = "gpt-4o-mini"

# ... existing code ... 

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
        
        IMPORTANT: Only include specific odds, lines, and statistics if you can find them in reliable sources.
        If you cannot find specific data, clearly state what information is unavailable.
        DO NOT make up or hallucinate specific odds, lines, or statistics.
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
async def deep_research(query: QueryAnalysis, data_points: Optional[List[DataPoint]] = None, user_id: Optional[str] = None) -> DeepResearchResult:
    """
    Perform comprehensive research using multiple data sources
    
    Args:
        query: Analyzed query containing sport type and other metadata
        data_points: Optional pre-gathered data points, if None or empty will gather data internally
        user_id: Optional user ID for personalized insights
        
    Returns:
        DeepResearchResult with comprehensive analysis
    """
    logger.info(f"Starting deep research for {query.sport_type}")
    
    try:
        # If data_points were not provided or empty, gather them
        if data_points is None or len(data_points) == 0:
            # Get team names from the query analysis
            teams = [team for team in query.teams.values() if team]  # Filter out empty team names
            if not teams:
                # Fallback for when no teams are specified - use a generic basketball query
                logger.warning("No teams found in query analysis, using generic basketball research")
                teams = ["NBA"]
            
            # Initialize services
            perplexity = PerplexityService()
            basketball = APISportsBasketballService()
            supabase = SupabaseService()
            
            # Gather data from all sources in parallel
            data_points = []
            async with perplexity, basketball:
                # Define all the tasks we want to run in parallel
                tasks = []
                task_metadata = []  # Store metadata about each task for better error handling
                
                # Add Perplexity tasks for general research regardless of team specificity
                tasks.append(
                    perplexity.quick_research(
                        query=f"Latest basketball betting information for {query.raw_query}",
                        search_recency="day"
                    )
                )
                task_metadata.append({
                    "type": "perplexity_research",
                    "description": "General basketball betting information",
                    "critical": False  # This task is not critical, we can proceed without it
                })
                
                # Add tasks for each team
                for team in teams:
                    if team != "NBA":  # Skip team-specific queries for generic NBA
                        # Add Perplexity search for this team regardless of API-Sports availability
                        # This ensures we always have some data even if API-Sports fails
                        tasks.append(
                            perplexity.quick_research(
                                query=f"Latest news, injuries, and betting trends for {team}",
                                search_recency="day"
                            )
                        )
                        task_metadata.append({
                            "type": "perplexity_team_research",
                            "team": team,
                            "description": f"Team-specific news and trends for {team}",
                            "critical": False
                        })
                        
                        # Try to get team-specific data from API-Sports
                        try:
                            # Try to get team ID first to validate the team exists
                            team_id = basketball.get_team_id(team)
                            if team_id:
                                # Add API-Sports NBA data tasks
                                tasks.append(basketball.get_team_stats(team))
                                task_metadata.append({
                                    "type": "api_sports_team_stats",
                                    "team": team,
                                    "description": f"Team statistics for {team}",
                                    "critical": False
                                })
                                
                                tasks.append(basketball.get_player_stats(team))
                                task_metadata.append({
                                    "type": "api_sports_player_stats",
                                    "team": team,
                                    "description": f"Player statistics for {team}",
                                    "critical": False
                                })
                                
                                # Note: API-Sports doesn't have a direct injuries endpoint,
                                # so we'll rely on Perplexity for injury information
                        except Exception as e:
                            logger.warning(f"Could not add team-specific API-Sports tasks for {team}: {str(e)}")
                            # We already added the Perplexity fallback above, so no need to add it again
                
                # Add common tasks
                try:
                    tasks.append(basketball.get_upcoming_games(teams[0]))
                    task_metadata.append({
                        "type": "api_sports_upcoming_games",
                        "description": "Upcoming NBA games",
                        "critical": False
                    })
                except Exception as e:
                    logger.warning(f"Could not add upcoming games task: {str(e)}")
                    # Add a fallback Perplexity search for upcoming games
                    tasks.append(
                        perplexity.quick_research(
                            query=f"Upcoming NBA games schedule for {teams[0]}",
                            search_recency="day"
                        )
                    )
                    task_metadata.append({
                        "type": "perplexity_upcoming_games",
                        "description": "Upcoming NBA games (fallback)",
                        "critical": False
                    })
                
                # Add user history tasks if user_id is provided
                if user_id:
                    try:
                        tasks.append(supabase.get_user_bets(user_id, sport="basketball", days_back=30))
                        task_metadata.append({
                            "type": "supabase_user_bets",
                            "description": "User's recent basketball bets",
                            "critical": False
                        })
                        
                        tasks.append(supabase.get_user_stats(user_id, sport="basketball"))
                        task_metadata.append({
                            "type": "supabase_user_stats",
                            "description": "User's basketball betting statistics",
                            "critical": False
                        })
                        
                        tasks.append(
                            supabase.get_similar_bets(
                                sport="basketball",
                                bet_type=query.bet_type if query.bet_type else "any",
                                days_back=30
                            )
                        )
                        task_metadata.append({
                            "type": "supabase_similar_bets",
                            "description": "Similar basketball bets",
                            "critical": False
                        })
                    except Exception as e:
                        logger.warning(f"Could not add user history tasks: {str(e)}")
                
                # Execute all tasks in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and handle any exceptions
                successful_tasks = 0
                failed_tasks = 0
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        failed_tasks += 1
                        task_info = task_metadata[i] if i < len(task_metadata) else {"description": f"Task {i}"}
                        logger.error(f"Error in {task_info['description']}: {str(result)}")
                        
                        # For critical tasks, we might want to raise an exception
                        if i < len(task_metadata) and task_metadata[i].get("critical", False):
                            raise ValueError(f"Critical task failed: {task_info['description']}")
                    else:
                        successful_tasks += 1
                        # Add successful results to data points
                        if result:
                            task_info = task_metadata[i] if i < len(task_metadata) else {"type": f"task_{i}"}
                            data_points.append(DataPoint(
                                source=task_info.get("type", tasks[i].__qualname__),
                                content=result.model_dump() if hasattr(result, 'model_dump') else str(result)
                            ))
                
                logger.info(f"Completed {successful_tasks} tasks successfully, {failed_tasks} tasks failed")
        
        # Check if we have enough data to proceed
        if len(data_points) == 0:
            logger.error("No data points were collected, cannot proceed with analysis")
            raise ValueError("Failed to collect any data for analysis")
        
        # Combine all data into a coherent context for the LLM
        context = create_analysis_context(query, data_points)
        
        # Use GPT-4o-mini to analyze the data and return the result
        return await generate_analysis_result(context)

    except Exception as e:
        logger.error(f"Error in deep research: {str(e)}", exc_info=True)
        raise ValueError("Error performing deep research") from e

def create_analysis_context(query: QueryAnalysis, data_points: List[DataPoint]) -> str:
    """Create a structured context for the LLM to analyze"""
    # Organize data by category for easier analysis
    organized_data = {
        "query_info": query.model_dump(),
        "odds_data": {},
        "team_stats": {},
        "player_stats": {},
        "injuries": {},
        "news": {},
        "historical_data": {},
        "user_data": {}
    }
    
    # Categorize data points
    for dp in data_points:
        source = dp.source
        content = dp.content
        
        # Categorize based on source name patterns
        if "odds" in source.lower():
            organized_data["odds_data"][source] = content
        elif "team_stats" in source.lower():
            organized_data["team_stats"][source] = content
        elif "player_stats" in source.lower() or "stats" in source.lower():
            organized_data["player_stats"][source] = content
        elif "injuries" in source.lower():
            organized_data["injuries"][source] = content
        elif "news" in source.lower() or "perplexity" in source.lower():
            organized_data["news"][source] = content
        elif "history" in source.lower() or "historical" in source.lower():
            organized_data["historical_data"][source] = content
        elif "user" in source.lower() or "bets" in source.lower():
            organized_data["user_data"][source] = content
        else:
            # If it doesn't fit a category, put it in the appropriate one based on content inspection
            # or create a new category
            if not organized_data.get("other_data"):
                organized_data["other_data"] = {}
            organized_data["other_data"][source] = content
    
    # Add data availability flags to help the model know what's available
    data_availability = {
        "has_odds_data": len(organized_data["odds_data"]) > 0,
        "has_team_stats": len(organized_data["team_stats"]) > 0,
        "has_player_stats": len(organized_data["player_stats"]) > 0,
        "has_injuries_data": len(organized_data["injuries"]) > 0,
        "has_news_data": len(organized_data["news"]) > 0,
        "has_historical_data": len(organized_data["historical_data"]) > 0,
        "has_user_data": len(organized_data["user_data"]) > 0
    }
    
    organized_data["data_availability"] = data_availability
    
    # Add instructions about data limitations
    organized_data["instructions"] = """
    IMPORTANT INSTRUCTIONS:
    1. Only use the data provided in this context for your analysis.
    2. If specific data (like current odds or lines) is not available, use null values and clearly state the limitation.
    3. Do not hallucinate or invent specific odds, statistics, or other numerical values.
    4. Reduce confidence scores when working with limited data.
    5. Be transparent about what information is and isn't available.
    """
    
    return str(organized_data)  # Convert to string for LLM input

@observe(name="generate_analysis_result")
async def generate_analysis_result(context: str) -> DeepResearchResult:
    """
    Use the LLM to analyze the collected data and generate insights.
    
    Args:
        context: Structured context containing all collected data
        
    Returns:
        DeepResearchResult with comprehensive analysis
    """
    logger.info("Generating deep analysis from collected data")
    
    try:
        # Create a system prompt that guides the model to analyze the data
        system_prompt = """You are a professional sports betting analyst.
        Your task is to analyze the provided data and generate comprehensive betting insights.
        
        Guidelines:
        1. Focus on the specific query and sport mentioned
        2. Analyze all available data sources (odds, team stats, player stats, injuries, news)
        3. Identify key trends, matchups, and factors that could influence betting outcomes
        4. Assess the strength of different betting options
        5. Provide a confidence score for each insight
        6. Identify potential risk factors
        
        CRITICAL DATA INTEGRITY RULES:
        1. NEVER invent or hallucinate specific odds, lines, statistics, or other numerical values
        2. If specific data is not available, clearly state this limitation
        3. Use phrases like "odds data isn't available" or "we don't have current line information" when appropriate
        4. Be transparent about confidence levels - lower confidence when data is limited
        5. Focus on what IS known rather than making up what isn't
        
        Return a JSON object with this structure:
        {
            "summary": "Overall analysis summary",
            "insights": [
                {
                    "category": "odds",
                    "insight": "Key insight description",
                    "impact": "How this affects betting decisions",
                    "confidence": 0.85,
                    "supporting_data": ["Data point 1", "Data point 2"]
                }
            ],
            "risk_factors": [
                {
                    "factor": "Risk factor name",
                    "severity": "high/medium/low",
                    "mitigation": "How to mitigate this risk"
                }
            ],
            "recommended_bet": "Specific bet recommendation",
            "odds_analysis": {
                "current_odds": "Current odds if available",
                "line_movement": "Recent line movement",
                "value_assessment": "Assessment of betting value"
            },
            "historical_context": "Relevant historical betting patterns",
            "confidence_score": 0.8,
            "citations": [
                {
                    "url": "https://example.com",
                    "title": "Source title",
                    "snippet": "Relevant excerpt",
                    "published_date": "2023-01-01"
                }
            ]
        }
        
        DO NOT include any explanatory text, just the JSON object.
        """
        
        # Make the OpenAI API call
        completion = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.2,  # Low temperature for consistent structured output
            max_tokens=2000
        )
        
        # Extract and parse the JSON response
        analysis_json = completion.choices[0].message.content.strip()
        
        # Clean the JSON response
        if analysis_json.startswith("```"):
            analysis_json = analysis_json.split("```")[1]
        if analysis_json.startswith("json"):
            analysis_json = analysis_json[4:]
        analysis_json = analysis_json.strip()
        
        # Parse the cleaned JSON
        analysis_dict = json.loads(analysis_json)
        
        # Convert the insights to BettingInsight objects
        insights = []
        for insight in analysis_dict.get("insights", []):
            insights.append(BettingInsight(
                category=insight.get("category", "general"),
                insight=insight.get("insight", ""),
                impact=insight.get("impact", ""),
                confidence=insight.get("confidence", 0.5),
                supporting_data=insight.get("supporting_data", [])
            ))
        
        # Convert the risk factors to RiskFactor objects
        risk_factors = []
        for risk in analysis_dict.get("risk_factors", []):
            risk_factors.append(RiskFactor(
                factor=risk.get("factor", ""),
                severity=risk.get("severity", "medium"),
                mitigation=risk.get("mitigation", "")
            ))
        
        # Convert the citations to Citation objects
        citations = []
        for citation in analysis_dict.get("citations", []):
            citations.append(Citation(
                url=citation.get("url", "https://example.com"),
                title=citation.get("title", ""),
                snippet=citation.get("snippet", ""),
                published_date=citation.get("published_date", "")
            ))
        
        # Create the DeepResearchResult object
        return DeepResearchResult(
            summary=analysis_dict.get("summary", "Analysis based on available data"),
            insights=insights,
            risk_factors=risk_factors,
            recommended_bet=analysis_dict.get("recommended_bet", "No specific recommendation available"),
            odds_analysis=analysis_dict.get("odds_analysis", {"note": "Odds data not available"}),
            historical_context=analysis_dict.get("historical_context", "No historical context available"),
            confidence_score=analysis_dict.get("confidence_score", 0.5),
            citations=citations,
            last_updated=datetime.now(UTC).isoformat(),
            metadata={"data_sources": analysis_dict.get("data_sources", [])}
        )
            
    except Exception as e:
        logger.error(f"Error in generate_analysis_result: {str(e)}", exc_info=True)
        
        # Create a minimal result with error information
        return DeepResearchResult(
            summary=f"Error generating analysis: {str(e)}",
            insights=[],
            risk_factors=[],
            recommended_bet="Unable to provide recommendation due to error",
            odds_analysis={"error": str(e)},
            historical_context="Not available due to error",
            confidence_score=0.1,
            citations=[],
            last_updated=datetime.now(UTC).isoformat()
        )

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
        
        CRITICAL DATA INTEGRITY RULES:
        1. NEVER invent or hallucinate specific odds, lines, statistics, or other numerical values
        2. If the research results indicate missing or unavailable data, acknowledge this limitation clearly
        3. Use phrases like "odds data isn't available" or "we don't have current line information" when appropriate
        4. Be transparent about confidence levels - lower confidence when data is limited
        5. Focus on what IS known rather than making up what isn't
        
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
        response = openai.chat.completions.create(
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
        
        # Create a fallback conversational response
        research_type = "deep" if is_deep_research else "quick"
        summary = research_result.summary if hasattr(research_result, "summary") else "Analysis of your query"
        
        fallback_response = f"""
        Hey there! Thanks for your question about "{query}".
        
        Based on my {research_type} research, here's what I found: {summary}
        
        I apologize that I couldn't generate a more detailed conversational response at this time. 
        The structured data in the results section below should still provide you with valuable insights.
        
        If you have any specific follow-up questions, feel free to ask!
        """
        
        # Return the original result with the fallback conversational response
        result_dict = research_result.model_dump()
        result_dict["conversational_response"] = fallback_response
        return result_dict 

async def structured_llm_call(
    prompt: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    model: str = model,
    should_validate_json: bool = True
) -> Dict[str, Any]:
    """
    Make a structured LLM call that expects and validates JSON responses.
    
    Args:
        prompt: System prompt that sets up the context and requirements
        messages: List of message dictionaries with role and content
        temperature: Controls randomness (0.0-1.0)
        max_tokens: Maximum tokens in response
        model: Model to use
        should_validate_json: Whether to validate and parse JSON response
        
    Returns:
        Parsed JSON response as dictionary
    """
    try:
        # Construct the messages array with system prompt
        full_messages = [
            {"role": "system", "content": prompt},
            *messages
        ]
        
        # Make the OpenAI API call
        completion = await openai.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Extract the response content
        response_text = completion.choices[0].message.content.strip()
        
        if should_validate_json:
            # Clean the JSON response
            if response_text.startswith("```"):
                # Extract JSON from code blocks
                matches = re.findall(r"```(?:json)?\n(.*?)```", response_text, re.DOTALL)
                if matches:
                    response_text = matches[0]
                else:
                    response_text = response_text.replace("```", "")
            
            # Remove any json language identifier
            if response_text.startswith("json"):
                response_text = response_text[4:]
            
            response_text = response_text.strip()
            
            try:
                # Parse and validate JSON
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw response: {response_text}")
                raise ValueError("LLM response was not valid JSON")
        else:
            # Return raw response for non-JSON cases
            return {"response": response_text}
            
    except Exception as e:
        logger.error(f"Error in structured_llm_call: {str(e)}", exc_info=True)
        raise

async def raw_llm_call(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    model: str = model
) -> str:
    """
    Make a raw LLM call for cases where we just want text output.
    
    Args:
        system_prompt: System message that sets up the context
        user_prompt: User message/query
        temperature: Controls randomness (0.0-1.0)
        max_tokens: Maximum tokens in response
        model: Model to use
        
    Returns:
        Raw text response
    """
    try:
        completion = await openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return completion.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error in raw_llm_call: {str(e)}", exc_info=True)
        raise

async def stream_llm_call(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    model: str = model
):
    """
    Stream LLM responses for real-time output.
    
    Args:
        system_prompt: System message that sets up the context
        user_prompt: User message/query
        temperature: Controls randomness (0.0-1.0)
        model: Model to use
        
    Yields:
        Chunks of the response as they arrive
    """
    try:
        stream = await openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        logger.error(f"Error in stream_llm_call: {str(e)}", exc_info=True)
        raise

def clean_json_string(json_str: str) -> str:
    """Clean and prepare a string for JSON parsing"""
    # Remove code block markers
    json_str = re.sub(r"```json\s*|\s*```", "", json_str)
    
    # Remove any json language identifier
    if json_str.startswith("json"):
        json_str = json_str[4:]
    
    return json_str.strip()

def validate_json_response(response: str) -> Dict[str, Any]:
    """Validate and parse a JSON response string"""
    try:
        cleaned = clean_json_string(response)
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {str(e)}")
        logger.error(f"Raw response: {response}")
        raise ValueError("Failed to parse LLM response as JSON") 