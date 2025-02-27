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

@observe(name="raw_llm_call")
async def raw_llm_call(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    model: str = MODEL
) -> str:
    """
    Make a raw LLM call for cases where we just want text output.
    
    Args:
        system_prompt: System message that sets up the context
        user_prompt: User message/query
        temperature: Controls randomness (0.0-1.0)
        max_tokens: Maximum tokens in response
        model: Model to use
        
    Returns:
        Raw text response
    """
    try:
        completion = await openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return completion.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error in raw_llm_call: {str(e)}", exc_info=True)
        raise

@observe(name="stream_llm_call")
async def stream_llm_call(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    model: str = MODEL
):
    """
    Stream LLM responses for real-time output.
    
    Args:
        system_prompt: System message that sets up the context
        user_prompt: User message/query
        temperature: Controls randomness (0.0-1.0)
        model: Model to use
        
    Yields:
        Chunks of the response as they arrive
    """
    try:
        stream = await openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        logger.error(f"Error in stream_llm_call: {str(e)}", exc_info=True)
        raise

def calculate_confidence_score(result: Any, citations: List[Any] = None) -> float:
    """
    Calculate confidence score based on available data and citations.
    
    Args:
        result: The analysis result to evaluate
        citations: Optional list of citations that support the result
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Start with base confidence
    confidence = 0.7
    
    # Adjust based on citations if provided
    if citations:
        confidence += min(len(citations) * 0.1, 0.2)  # Up to 0.2 boost for citations
    
    # If result has its own confidence score, factor it in
    if hasattr(result, 'confidence_score'):
        confidence = (confidence + float(result.confidence_score)) / 2
    
    # Cap at 0.95 to leave room for uncertainty
    return min(confidence, 0.95)

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