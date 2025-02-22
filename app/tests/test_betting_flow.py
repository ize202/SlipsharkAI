import logging
import os
from langtrace_python_sdk import langtrace
from opentelemetry import trace
from ..config import LANGTRACE_API_KEY

# Initialize LangTrace before importing OpenAI
langtrace.init(api_key=LANGTRACE_API_KEY)

from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get tracer
tracer = trace.get_tracer(__name__)

def test_llm_connection():
    """Test basic LLM connection with LangTrace observability"""
    logger.info("Starting basic LLM connection test...")
    
    try:
        with tracer.start_as_current_span("test.llm_connection") as span:
            client = OpenAI()
            
            # Add test metadata
            span.set_attribute("test_type", "connection_check")
            
            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "user", "content": "Say hello!"}
                ]
            )
            
            result = response.choices[0].message.content
            
            # Add response to trace
            span.set_attribute("response", result)
            
            logger.info(f"LLM Response: {result}")
            logger.info("Basic LLM connection test completed successfully!")
            
    except Exception as e:
        logger.error(f"Error in LLM connection test: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    test_llm_connection() 