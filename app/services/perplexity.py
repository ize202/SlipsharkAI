from typing import Optional, Dict, Any, List
import os
import logging
import json
import httpx
from pydantic import BaseModel, Field
from langfuse.decorators import observe
from ..models.research_models import QueryAnalysis, SportType
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
    """Response from Perplexity API"""
    content: str  # Main response content from Perplexity

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
    @observe(name="perplexity_quick_research", as_type="generation")
    async def quick_research(
        self,
        query: str,
        search_recency: str = "day"
    ) -> PerplexityResponse:
        """
        Perform quick research using Perplexity AI with web search capabilities.
        
        Args:
            query: The search query
            search_recency: Time window for search results ('hour', 'day', 'week', 'month')
        """
        try:
            # Define our consistent system prompt for sports betting analysis
            system_prompt = """You are a professional sports betting analyst.                                                
                                    Format your responses in this structure:
                                    SUMMARY: [A clear, data-driven conclusion]

                                    Tone and Style Rules:
                                    1. Be precise and factual
                                    2. Always include specific numbers and statistics
                                    3. Maintain a professional, analytical tone
                                    4. Present information objectively without speculation
                                    5. Structure information in order of importance"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""Search for and analyze:
                                    1. Recent game results and performance trends
                                    2. Latest injury updates or roster changes
                                    3. Current betting lines and odds movements
                                    4. Key matchup factors and statistics
                                    5. Relevant news from the last 24-48 hours

                                    Query: {query}"""}
            ]
            
            payload = {
                "model": self.default_model,
                "messages": messages,
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
            
            # Update Langfuse with usage information
            usage = data.get("usage", {})
            # The @observe decorator automatically creates the observation
            # No need to explicitly update it as it's handled by the decorator


            return PerplexityResponse(
                content=content
            )
                
        except Exception as e:
            logger.error(f"Error in quick_research: {str(e)}")
            raise Exception(f"Error in quick_research: {str(e)}")



