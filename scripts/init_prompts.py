"""
Script to initialize or update prompts in Langfuse.
Run this script when you want to update the prompts in Langfuse.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from app.utils.prompt_manager import initialize_research_prompts
from app.config import get_logger

logger = get_logger(__name__)

def main():
    """Initialize or update prompts in Langfuse"""
    try:
        logger.info("Initializing research prompts in Langfuse...")
        initialize_research_prompts()
        logger.info("Successfully initialized prompts!")
    except Exception as e:
        logger.error(f"Error initializing prompts: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 