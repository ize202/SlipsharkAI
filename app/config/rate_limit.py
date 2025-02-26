"""
Rate limiting configuration for the Sports Research API.
Provides rate limiting for API endpoints to control costs and prevent abuse.
"""
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Environment variables for rate limits
DEFAULT_RATE_LIMIT = os.getenv("DEFAULT_RATE_LIMIT", "60/minute")  # Default: 60 requests per minute
ANALYZE_RATE_LIMIT = os.getenv("ANALYZE_RATE_LIMIT", "30/minute")  # More restrictive for analyze endpoint
EXTEND_RATE_LIMIT = os.getenv("EXTEND_RATE_LIMIT", "10/minute")    # Most restrictive for deep research

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,  # Use IP address as the rate limiting key
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri=os.getenv("REDIS_URL", "memory://"),  # Use Redis if available, otherwise in-memory
)

# Store the default rate limit handler for compatibility
rate_limit_exceeded_handler = _rate_limit_exceeded_handler

# Log rate limit configuration
logger.info(f"Rate limiting configured with default limit: {DEFAULT_RATE_LIMIT}")
logger.info(f"Analyze endpoint limit: {ANALYZE_RATE_LIMIT}")
logger.info(f"Extend endpoint limit: {EXTEND_RATE_LIMIT}")

# Function to get API key from request for per-key rate limiting
def get_api_key(request):
    """
    Extract API key from request headers for per-key rate limiting.
    This allows different rate limits for different API keys.
    """
    from app.config.auth import API_KEY_NAME
    return request.headers.get(API_KEY_NAME, "anonymous") 