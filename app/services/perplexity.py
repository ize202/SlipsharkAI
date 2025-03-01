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
    content: str  # Main response content, either structured or unstructured
    key_points: Optional[List[str]] = Field(default_factory=list)  # Key insights if provided in structured format
    citations: Optional[List[Citation]] = Field(default_factory=list)  # Source citations if available
    related_questions: Optional[List[str]] = Field(default_factory=list)  # Related questions if available

class PerplexityService:
    """Service for interacting with Perplexity AI API"""
    
    def __init__(self, timeout: float = 120.0):
        """Initialize the service with API configuration"""
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.default_model = "sonar"  # Using sonar-pro for deeper research capabilities
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
        Note: While we request structured output, the free tier may not always provide it.
        
        Args:
            query: The user's query to research
            system_prompt: Optional system prompt to guide the response
            search_recency: Time window for search results ('hour', 'day', 'week', 'month')
            
        Returns:
            PerplexityResponse containing the research results. If structured format is not 
            followed, the entire response will be in the content field with empty key_points.
        """
        try:
            default_system_prompt = """You are a professional sports betting analyst providing real-time research.
            Your task is to search for and analyze the most recent and relevant information about the query.
            
            Focus on:
            1. Recent game results and performance trends
            2. Latest injury updates or roster changes
            3. Current betting lines and odds movements
            4. Key matchup factors and statistics
            5. Relevant news that could impact betting decisions (weather, venue changes, etc.)
            
            Keep your analysis factual and data-driven. Include specific numbers, dates, and sources when available.
            Prioritize information from the last 24-48 hours, but include relevant historical context if important.
            
            Try to format your response like this (but provide useful information even if you can't follow this format exactly):
            SUMMARY: [Concise overview of the most important findings]
            KEY POINTS:
            - [Recent fact/update with specific details]
            - [Key statistic or trend]
            - [Important news or development]
            - [Any other critical information]"""
            
            messages = [
                {"role": "system", "content": system_prompt or default_system_prompt},
                {"role": "user", "content": query}
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
            langfuse.update_current_observation(
                input=messages,
                model=self.default_model,
                metadata={
                    "search_recency": search_recency
                },
                usage_details={
                    "input": usage.get("prompt_tokens", 0),
                    "output": usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0)
                }
            )

            # Try to parse structured format, but fall back to raw content if not possible
            sections = content.split('\n')
            summary = ""
            key_points = []
            found_structured = False

            for section in sections:
                if section.startswith('SUMMARY:'):
                    summary = section.replace('SUMMARY:', '').strip()
                    found_structured = True
                elif section.startswith('-'):
                    key_points.append(section.replace('-', '').strip())
                    found_structured = True

            # If we couldn't find structured format, use the whole content as summary
            if not found_structured:
                summary = content

            return PerplexityResponse(
                content=summary,
                key_points=key_points if found_structured else [],
                citations=[],  # We don't get citations in tier 0
                related_questions=[]  # We don't get related questions in tier 0
            )
                
        except Exception as e:
            logger.error(f"Error in quick_research: {str(e)}")
            raise Exception(f"Error in quick_research: {str(e)}")
