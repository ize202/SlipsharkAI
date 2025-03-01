"""
Utility functions for managing prompts with Langfuse.
"""

from langfuse import Langfuse
from typing import Dict, Any, List
import logging
from app.config import get_logger

logger = get_logger(__name__)
langfuse = Langfuse()

# Initialize prompts in Langfuse
def initialize_research_prompts():
    """Initialize or update the research chain prompts in Langfuse"""
    try:
        # Create query analysis prompt
        langfuse.create_prompt(
            name="research-query-analysis",
            type="text",
            prompt="""You are a sports betting query analyzer. Your task is to analyze betting queries and extract structured information.
            
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
                "raw_query": "{{query}}",
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
            }""",
            labels=["production"],
            config={
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "max_tokens": 2000
            }
        )

        # Create response generation prompt
        langfuse.create_prompt(
            name="research-response-generation",
            type="text",
            prompt="""You are a professional sports betting analyst having a conversation with a bettor.
            Convert the gathered data into a natural, conversational response.
            
            Data Context:
            {{data_context}}
            
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
            }""",
            labels=["production"],
            config={
                "model": "gpt-4o-mini",
                "temperature": 0.7,
                "max_tokens": 2000
            }
        )
        
        logger.info("Successfully initialized research prompts in Langfuse")
    except Exception as e:
        logger.error(f"Error initializing prompts in Langfuse: {str(e)}")
        raise

def get_query_analysis_prompt() -> str:
    """Get the current production version of the query analysis prompt"""
    try:
        prompt = langfuse.get_prompt("research-query-analysis")
        return prompt
    except Exception as e:
        logger.error(f"Error fetching query analysis prompt: {str(e)}")
        raise

def get_response_generation_prompt() -> str:
    """Get the current production version of the response generation prompt"""
    try:
        prompt = langfuse.get_prompt("research-response-generation")
        return prompt
    except Exception as e:
        logger.error(f"Error fetching response generation prompt: {str(e)}")
        raise