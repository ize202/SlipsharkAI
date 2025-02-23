from typing import Optional, Dict, Any, List
import os
import logging
import httpx
from pydantic import BaseModel
from langfuse.decorators import observe

# Set up logging
logger = logging.getLogger(__name__)

class PerplexityResponse(BaseModel):
    """Structured response from Perplexity API"""
    content: str
    citations: Optional[List[Dict[str, str]]] = None
    related_questions: Optional[List[str]] = None

class PerplexityService:
    """Service for interacting with Perplexity AI API"""
    
    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY environment variable is not set")
        
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.default_model = "sonar"
        
        # Initialize async client
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0  # 30 second timeout
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
                {
                    "role": "system",
                    "content": system_prompt or default_system_prompt
                },
                {"role": "user", "content": query}
            ]
            
            payload = {
                "model": self.default_model,
                "messages": messages,
                "temperature": 0.2,  # Lower temperature for more focused responses
                "return_citations": True,
                "search_recency_filter": search_recency,
                "return_related_questions": True
            }
            
            async with self.client as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Extract citations if available
                citations = data.get("citations", [])
                related_questions = data.get("related_questions", [])
                
                return PerplexityResponse(
                    content=content,
                    citations=citations,
                    related_questions=related_questions
                )
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during Perplexity API call: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error in quick_research: {str(e)}", exc_info=True)
            raise

    @observe(name="perplexity_analyze_query")
    async def analyze_query(
        self,
        query: str,
        search_recency: str = "day"
    ) -> Dict[str, Any]:
        """
        Analyze a sports betting query to determine intent and required data.
        
        Args:
            query: The user's betting query
            search_recency: Time window for search results
            
        Returns:
            Dict containing the analysis results
        """
        try:
            system_prompt = """Analyze this sports betting query.
            Identify:
            1. The sport and teams/players involved
            2. The type of bet or analysis requested
            3. What information would be most relevant
            Format the response as JSON."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            
            payload = {
                "model": self.default_model,
                "messages": messages,
                "temperature": 0.1,  # Very low temperature for consistent analysis
                "search_recency_filter": search_recency
            }
            
            async with self.client as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                return data["choices"][0]["message"]["content"]
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during Perplexity API call: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error in analyze_query: {str(e)}", exc_info=True)
            raise
