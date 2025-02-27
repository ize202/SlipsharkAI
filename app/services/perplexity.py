from typing import Optional, Dict, Any, List
import os
import logging
import json
import httpx
from pydantic import BaseModel, Field
from langfuse.decorators import observe
from ..models.research_models import QueryAnalysis, SportType, Citation
from ..utils.cache import redis_cache, memory_cache

# Set up logging
logger = logging.getLogger(__name__)

class Citation(BaseModel):
    """Citation from Perplexity API"""
    url: str
    title: Optional[str] = None
    snippet: Optional[str] = None
    published_date: Optional[str] = None

class PerplexityResponse(BaseModel):
    """Structured response from Perplexity API"""
    content: str
    citations: Optional[List[Citation]] = Field(default=[])
    related_questions: Optional[List[str]] = Field(default=[])
    key_points: Optional[List[str]] = Field(default=[])
    confidence_score: Optional[float] = Field(default=0.5)
    deep_research_recommended: Optional[bool] = Field(default=False)

class PerplexityService:
    """Service for interacting with Perplexity AI API"""
    
    def __init__(self, timeout: float = 120.0):
        """Initialize the service with API configuration"""
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.default_model = "sonar"
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY environment variable must be set")
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=timeout
        )
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.aclose()
    
    # Use Redis cache with a 30-minute TTL for quick research
    # This is appropriate for sports betting where data changes frequently
    @redis_cache(ttl=1800, prefix="perplexity", serialize_json=True)
    @observe(name="perplexity_quick_research")
    async def quick_research(
        self,
        query: str,
        system_prompt: Optional[str] = None,
        search_recency: str = "day"
    ) -> PerplexityResponse:
        """
        Perform quick research using Perplexity AI with web search capabilities.
        
        Args:
            query: The user's query to research
            system_prompt: Optional system prompt to guide the response
            search_recency: Time window for search results ('hour', 'day', 'week', 'month')
            
        Returns:
            PerplexityResponse containing the analysis
        """
        try:
            default_system_prompt = """You are a professional sports betting analyst.
            Analyze the query and provide key insights based on current information.
            Focus on recent performance, odds, and any relevant news that could impact betting decisions.
            Be concise but thorough.
            
            Format your response like this:
            SUMMARY: [Brief summary of findings]
            KEY POINTS:
            - [Point 1]
            - [Point 2]
            - [Point 3]
            CONFIDENCE: [0-1]
            DEEP RESEARCH NEEDED: [yes/no]"""
            
            messages = [
                {"role": "system", "content": system_prompt or default_system_prompt},
                {"role": "user", "content": query}
            ]
            
            payload = {
                "model": self.default_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 500,
                "top_p": 0.9,
                "search_recency_filter": search_recency
            }
            
            try:
                response = await self.client.post(self.base_url, json=payload)
                response.raise_for_status()
            except httpx.TimeoutException as e:
                logger.error(f"Timeout error in quick_research: {str(e)}")
                raise Exception(f"API request timed out after {self.client.timeout} seconds")
            except httpx.HTTPError as e:
                logger.error(f"HTTP error in quick_research: {str(e)}")
                raise Exception(f"HTTP error occurred: {str(e)}")
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse the raw text response
            sections = content.split('\n')
            summary = ""
            key_points = []
            confidence = 0.5
            deep_research_needed = False

            for section in sections:
                if section.startswith('SUMMARY:'):
                    summary = section.replace('SUMMARY:', '').strip()
                elif section.startswith('-'):
                    key_points.append(section.replace('-', '').strip())
                elif section.startswith('CONFIDENCE:'):
                    try:
                        confidence = float(section.replace('CONFIDENCE:', '').strip())
                    except ValueError:
                        pass
                elif section.startswith('DEEP RESEARCH NEEDED:'):
                    deep_research_needed = section.replace('DEEP RESEARCH NEEDED:', '').strip().lower() == 'yes'

            return PerplexityResponse(
                content=summary,
                citations=[],  # We don't get citations in tier 0
                related_questions=[],  # We don't get related questions in tier 0
                key_points=key_points,
                confidence_score=confidence,
                deep_research_recommended=deep_research_needed
            )
                
        except Exception as e:
            logger.error(f"Error in quick_research: {str(e)}")
            raise Exception(f"Error in quick_research: {str(e)}")

    @observe(name="perplexity_analyze_query")
    async def analyze_query(
        self,
        query: str,
        search_recency: str = "day"
    ) -> QueryAnalysis:
        """
        Analyze a user's query to determine intent and required data sources.
        
        Args:
            query: The user's query to analyze
            search_recency: Time window for search results ('hour', 'day', 'week', 'month')
            
        Returns:
            QueryAnalysis object containing structured analysis of the query
        """
        try:
            system_prompt = """You are a query analysis system for sports betting.
            Analyze the user's sports betting query and provide a clear analysis in this format:
            Sport Type: [sport]
            Deep Research Needed: [yes/no]
            Required Data: [comma-separated list of required data sources]
            Confidence Score: [0-1]
            Bet Type: [type of bet]
            
            Example:
            Sport Type: basketball
            Deep Research Needed: yes
            Required Data: team_stats, odds, injuries, news
            Confidence Score: 0.85
            Bet Type: spread"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            
            payload = {
                "model": self.default_model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 500,
                "top_p": 0.9,
                "search_recency_filter": search_recency
            }
            
            try:
                response = await self.client.post(self.base_url, json=payload)
                response.raise_for_status()
            except httpx.TimeoutException as e:
                logger.error(f"Timeout error in analyze_query: {str(e)}")
                raise Exception(f"API request timed out after {self.client.timeout} seconds")
            except httpx.HTTPError as e:
                logger.error(f"HTTP error in analyze_query: {str(e)}")
                raise Exception(f"HTTP error occurred: {str(e)}")
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse the raw text response into structured format
            lines = content.strip().split('\n')
            analysis_dict = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    analysis_dict[key.strip()] = value.strip()

            # Map the parsed text to QueryAnalysis fields
            sport_map = {
                'basketball': SportType.BASKETBALL,
                'football': SportType.FOOTBALL,
                'baseball': SportType.BASEBALL,
                'hockey': SportType.HOCKEY,
                'soccer': SportType.SOCCER
            }

            return QueryAnalysis(
                raw_query=query,
                sport_type=sport_map.get(analysis_dict.get('Sport Type', '').lower(), SportType.OTHER),
                is_deep_research=analysis_dict.get('Deep Research Needed', '').lower() == 'yes',
                confidence_score=float(analysis_dict.get('Confidence Score', '0.5')),
                required_data_sources=[s.strip() for s in analysis_dict.get('Required Data', '').split(',')],
                bet_type=analysis_dict.get('Bet Type', '').lower()
            )
                
        except Exception as e:
            logger.error(f"Error in analyze_query: {str(e)}")
            raise Exception(f"Error in analyze_query: {str(e)}")
