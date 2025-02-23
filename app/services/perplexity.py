from typing import Optional, Dict, Any, List
import os
import logging
import json
import httpx
from pydantic import BaseModel, Field
from langfuse.decorators import observe
from ..models.betting_models import QueryAnalysis

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

class PerplexityService:
    """Service for interacting with Perplexity AI API"""
    
    def __init__(self, timeout: float = 30.0):
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
            PerplexityResponse containing the analysis and any citations
        """
        try:
            default_system_prompt = """You are a professional sports betting analyst.
            Analyze the query and provide key insights based on current information.
            Focus on recent performance, odds, and any relevant news that could impact betting decisions.
            Be concise but thorough."""
            
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
            
            response = await self.client.post(self.base_url, json=payload)
            response.raise_for_status()
            
            data = await response.json()
            content = data["choices"][0]["message"]["content"]
            citations = [
                Citation(
                    url=citation,
                    title=None,
                    snippet=None,
                    published_date=None
                )
                for citation in data.get("citations", [])
            ]
            
            return PerplexityResponse(
                content=content,
                citations=citations,
                related_questions=[]
            )
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error in quick_research: {str(e)}")
            raise Exception(f"API request timed out: {str(e)}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in quick_research: {str(e)}")
            raise Exception(f"HTTP error occurred: {str(e)}")
        except Exception as e:
            logger.error(f"Error in quick_research: {str(e)}")
            raise Exception(f"Error in quick_research: {str(e)}")

    @observe(name="perplexity_analyze_query")
    async def analyze_query(
        self,
        query: str,
        search_recency: str = "day"
    ) -> str:
        """
        Analyze a user's query to determine intent and required data sources.
        
        Args:
            query: The user's query to analyze
            search_recency: Time window for search results ('hour', 'day', 'week', 'month')
            
        Returns:
            JSON string containing structured analysis of the query
        """
        try:
            system_prompt = """You are a query analysis system.
            Analyze the user's sports betting query and provide structured information about:
            1. The sport type (e.g., basketball, football)
            2. Whether deep research is needed
            3. Required data sources (e.g., team stats, odds, news)
            4. Confidence score in the analysis
            Return the analysis in JSON format."""
            
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
            
            response = await self.client.post(self.base_url, json=payload)
            response.raise_for_status()
            
            data = await response.json()
            return data["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"Error in analyze_query: {str(e)}")
            raise Exception(f"Error in analyze_query: {str(e)}")
