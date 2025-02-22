import logging
from langfuse.decorators import observe
from langfuse import Langfuse
import openai
from ..config.langfuse_init import langfuse  # Use the initialized Langfuse instance

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@observe(name="test_llm_connection")
def test_llm_connection():
    """Test basic LLM connection with Langfuse observability"""
    logger.info("Starting basic LLM connection test...")
    
    try:
        response = openai.chat.completions.create(
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