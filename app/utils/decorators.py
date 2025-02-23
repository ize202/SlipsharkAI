import os
import functools
import pytest

def requires_api_keys(func):
    """
    Decorator to skip tests that require API keys if they are not present in the environment.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check for required API keys
        required_keys = [
            "GOALSERVE_API_KEY",
            "PERPLEXITY_API_KEY",
            "SUPABASE_URL",
            "SUPABASE_KEY"
        ]
        
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        
        if missing_keys:
            pytest.skip(f"Missing required API keys: {', '.join(missing_keys)}")
        
        return func(*args, **kwargs)
    
    return wrapper 