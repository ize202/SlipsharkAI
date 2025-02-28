"""
Utility functions for LLM operations and response processing.
"""

from typing import Dict, Any, List
import json
from datetime import datetime
import logging
import re
from langfuse.decorators import observe
import openai
from openai import AsyncOpenAI
from app.config import get_logger

logger = get_logger(__name__)

# Using the latest model for best performance
MODEL = "gpt-4o-mini"

# Initialize the async OpenAI client
async_client = AsyncOpenAI()

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def json_serialize(obj):
    """Serialize an object to JSON, handling datetime objects"""
    return json.dumps(obj, cls=DateTimeEncoder)

def parse_datetime(obj):
    """Parse datetime strings in a dictionary"""
    if isinstance(obj, dict):
        return {k: parse_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parse_datetime(item) for item in obj]
    elif isinstance(obj, str):
        try:
            return datetime.fromisoformat(obj)
        except (ValueError, TypeError):
            return obj
    return obj

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
        completion = await async_client.chat.completions.create(
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
        # First parse the JSON normally
        parsed = json.loads(response)
        # Then try to convert any ISO datetime strings to datetime objects
        return parse_datetime(parsed)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {str(e)}")
        logger.error(f"Raw response: {response}")
        raise ValueError("Failed to parse LLM response as JSON") 