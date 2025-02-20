from typing import Dict, Any, Optional
import openai
from openai import AsyncOpenAI
import os

class BaseResearchChain:
    def __init__(self, temperature: float = 0.7):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.temperature = temperature

    async def _process_prompt(self, prompt: str) -> str:
        """Process a prompt using OpenAI's API."""
        response = await self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a professional sports analyst and researcher."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature
        )
        return response.choices[0].message.content

    def _format_prompt(self, template: str, **kwargs) -> str:
        """Format a prompt template with the given arguments."""
        return template.format(**kwargs)

    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process the input query through the chain.
        
        Args:
            query (str): The research query to process
            context (Dict[str, Any], optional): Additional context for the chain
            
        Returns:
            Dict[str, Any]: The processed result
        """
        # Format context for the prompt
        context_str = "\n".join(f"{k}: {v}" for k, v in (context or {}).items())
        
        # Create the full prompt
        prompt = f"""
Query: {query}

Context:
{context_str}

Please provide a detailed analysis with:
1. Key insights and findings
2. Supporting evidence and statistics
3. Strategic implications
4. Confidence assessment
"""
        
        result = await self._process_prompt(prompt)
        
        return {
            "result": result,
            "confidence": 0.8,  # We can implement more sophisticated confidence scoring later
            "sources": []  # We can add source tracking later
        } 