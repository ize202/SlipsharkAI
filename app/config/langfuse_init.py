import os
from dotenv import load_dotenv
from langfuse import Langfuse
import openai

# Load environment variables
load_dotenv()

# Get Langfuse credentials from environment
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
    raise ValueError("Langfuse API keys not found in environment variables")
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API key not found in environment variables")

# Initialize Langfuse
langfuse = Langfuse(
    public_key=LANGFUSE_PUBLIC_KEY,
    secret_key=LANGFUSE_SECRET_KEY,
    host="https://us.cloud.langfuse.com"  # Using the US cloud version
)

# Configure OpenAI
openai.api_key = OPENAI_API_KEY 