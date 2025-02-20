import os
from dotenv import load_dotenv
from langtrace_python_sdk import langtrace

# Load environment variables
load_dotenv()

# Get API keys from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LANGTRACE_API_KEY = os.getenv("LANGTRACE_API_KEY")

# Initialize LangTrace
if not LANGTRACE_API_KEY:
    raise EnvironmentError("LANGTRACE_API_KEY environment variable is not set")

langtrace.init(api_key=LANGTRACE_API_KEY)

# Verify OpenAI API key
if not OPENAI_API_KEY:
    raise EnvironmentError("OPENAI_API_KEY environment variable is not set") 