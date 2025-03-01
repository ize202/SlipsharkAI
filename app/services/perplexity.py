from typing import Optional, Dict, Any, List
import os
import logging
import json
import httpx
from pydantic import BaseModel, Field
from langfuse.decorators import observe
from langfuse import Langfuse
from ..models.research_models import QueryAnalysis, SportType
from ..utils.cache import redis_cache, memory_cache
from app.config.langfuse_init import langfuse

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
    @observe(name="perplexity_quick_research", as_type="generation")
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
            
            # Update Langfuse with usage information
            usage = data.get("usage", {})
            langfuse.update_current_observation(
                input=messages,
                model=self.default_model,
                metadata={
                    "temperature": 0.2,
                    "max_tokens": 500,
                    "search_recency": search_recency
                },
                usage_details={
                    "input": usage.get("prompt_tokens", 0),
                    "output": usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0)
                }
            )

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
