import logging
from langtrace_python_sdk import langtrace
from langtrace_python_sdk.utils.with_root_span import with_langtrace_root_span
from ..config import LANGTRACE_API_KEY

# Initialize LangTrace before importing OpenAI
langtrace.init(api_key=LANGTRACE_API_KEY)

from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@with_langtrace_root_span()
def test_llm_connection():
    """Test basic LLM connection with LangTrace observability"""
    logger.info("Starting basic LLM connection test...")
    
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "user", "content": "Say hello!"}
            ]
        )
        
        result = response.choices[0].message.content
        logger.info(f"LLM Response: {result}")
        logger.info("Basic LLM connection test completed successfully!")
            
    except Exception as e:
        logger.error(f"Error in LLM connection test: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    test_llm_connection() 