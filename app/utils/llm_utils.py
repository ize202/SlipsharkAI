"""
Utility functions for LLM operations and response processing.
"""

from typing import Dict, Any, List
import json
import logging
import re
from langfuse.decorators import observe
import openai
from app.config import get_logger

logger = get_logger(__name__)

# Using the latest model for best performance
MODEL = "gpt-4o-mini"

@observe(name="structured_llm_call")
async def structured_llm_call(
    prompt: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    model: str = MODEL,
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
            # Clean and parse JSON response
            cleaned_json = clean_json_string(response_text)
            return validate_json_response(cleaned_json)
        else:
            # Return raw response for non-JSON cases
            return {"response": response_text}
            
    except Exception as e:
        logger.error(f"Error in structured_llm_call: {str(e)}", exc_info=True)
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
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {str(e)}")
        logger.error(f"Raw response: {response}")
        raise ValueError("Failed to parse LLM response as JSON") 