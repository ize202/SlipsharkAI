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
        # Skip datetime parsing for game_date field
        if "game_date" in obj:
            return {k: parse_datetime(v) if k != "game_date" else v for k, v in obj.items()}
        return {k: parse_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parse_datetime(item) for item in obj]
    elif isinstance(obj, str):
        try:
            return datetime.fromisoformat(obj)
        except (ValueError, TypeError):
            return obj
    return obj

@observe(name="structured_llm_call", as_type="generation")
async def structured_llm_call(
    prompt: str,
    messages: List[Dict[str, str]],
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
        )
        
        # Extract usage information for Langfuse
        usage = completion.usage
        # The @observe decorator automatically creates the observation
        # No need to explicitly update it as it's handled by the decorator
        
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
    """Clean a JSON string to ensure it can be properly parsed.
    
    Steps:
    1. Remove code block markers and any JSON language identifier
    2. Replace smart quotes with regular quotes
    3. Handle escaped backslashes
    4. Handle mixed escaped and unescaped quotes
    5. Ensure proper escaping of quotes in keys and values
    
    Args:
        json_str: The JSON string to clean
        
    Returns:
        The cleaned JSON string
    """
    # Remove code block markers and language identifier
    json_str = re.sub(r'```(?:json)?\s*|\s*```', '', json_str)
    
    # Replace smart quotes with regular quotes
    json_str = json_str.replace('"', '"').replace('"', '"')
    
    try:
        # First try to parse it as is
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        # If that fails, try to clean it up
        try:
            # Replace escaped backslashes with a temporary marker
            json_str = json_str.replace('\\\\', '\x00')
            
            # Replace escaped quotes with a temporary marker
            json_str = json_str.replace('\\"', '\x01')
            
            # Remove any remaining backslashes before quotes
            json_str = json_str.replace('\"', '"')
            
            # Convert single quotes to double quotes
            json_str = json_str.replace("'", '"')
            
            # Restore escaped quotes and backslashes
            json_str = json_str.replace('\x01', '\\"')
            json_str = json_str.replace('\x00', '\\\\')
            
            # Clean up any remaining invalid escapes
            json_str = re.sub(r'\\([^"\\])', r'\1', json_str)
            
            # Validate that we can parse it
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            # If that fails too, try one more approach
            try:
                # Try to parse it as raw string
                return str(json.loads(json_str.encode('utf-8').decode('unicode-escape')))
            except:
                # If all else fails, return the original string
                return json_str

def validate_json_response(response: str) -> Dict[str, Any]:
    """Validate and parse a JSON response string"""
    try:
        # First parse the JSON normally
        parsed = json.loads(response)
        logger.debug(f"Initial JSON parse result: {parsed}")
        
        # Then try to convert any ISO datetime strings to datetime objects
        parsed_with_dates = parse_datetime(parsed)
        logger.debug(f"After datetime parsing: {parsed_with_dates}")
        
        return parsed_with_dates
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {str(e)}")
        logger.error(f"Raw response: {response}")
        raise ValueError("Failed to parse LLM response as JSON") 