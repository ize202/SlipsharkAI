# Initialize Functions package
"""
This package contains LLM function implementations for the sports research API.
"""

try:
    from .llm_functions import (
        analyze_query,
        quick_research,
        deep_research,
        generate_final_response
    )
    
    __all__ = [
        'analyze_query',
        'quick_research',
        'deep_research',
        'generate_final_response'
    ]
except ImportError as e:
    import logging
    logging.getLogger(__name__).error(f"Error importing from llm_functions: {str(e)}") 