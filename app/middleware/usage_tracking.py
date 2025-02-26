"""
Usage tracking middleware for the Sports Research API.
Tracks API usage for monitoring and billing purposes.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.auth import API_KEY_NAME
import logging
import time
import os
import redis
import json
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Redis client if REDIS_URL is set
redis_client = None
if os.getenv("REDIS_URL"):
    try:
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        redis_client.ping()  # Test connection
        logger.info("Redis usage tracking initialized successfully")
    except redis.ConnectionError:
        logger.warning("Failed to connect to Redis for usage tracking. Will log only.")
        redis_client = None
else:
    logger.info("REDIS_URL not set. Usage tracking will log only.")

class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that tracks API usage for monitoring and billing purposes.
    Records request counts, response times, and endpoint usage patterns.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip tracking for static files and health checks
        if request.url.path.startswith("/static") or request.url.path == "/health":
            return await call_next(request)
        
        # Get API key from header
        api_key = request.headers.get(API_KEY_NAME, "anonymous")
        
        # Record start time
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Log the usage
        logger.info(
            f"API Usage: {request.method} {request.url.path} | "
            f"API Key: {api_key} | "
            f"Response Time: {response_time:.4f}s | "
            f"Status: {response.status_code}"
        )
        
        # Track usage in Redis if available
        if redis_client:
            try:
                # Get current date for daily tracking
                today = datetime.now().strftime("%Y-%m-%d")
                
                # Increment daily request count for this API key
                daily_key = f"usage:{api_key}:daily:{today}"
                redis_client.incr(daily_key)
                redis_client.expire(daily_key, 60 * 60 * 24 * 30)  # Keep for 30 days
                
                # Increment endpoint-specific count
                endpoint_key = f"usage:{api_key}:endpoint:{request.url.path}:{today}"
                redis_client.incr(endpoint_key)
                redis_client.expire(endpoint_key, 60 * 60 * 24 * 30)  # Keep for 30 days
                
                # Track response times (store as list of recent times)
                time_key = f"usage:{api_key}:response_times:{request.url.path}:{today}"
                redis_client.lpush(time_key, response_time)
                redis_client.ltrim(time_key, 0, 99)  # Keep only last 100 times
                redis_client.expire(time_key, 60 * 60 * 24 * 7)  # Keep for 7 days
                
                # Track status codes
                status_key = f"usage:{api_key}:status:{response.status_code}:{today}"
                redis_client.incr(status_key)
                redis_client.expire(status_key, 60 * 60 * 24 * 7)  # Keep for 7 days
                
            except Exception as e:
                logger.warning(f"Failed to track usage in Redis: {str(e)}")
        
        return response

async def get_usage_stats(api_key: str = None, days: int = 7):
    """
    Get usage statistics for an API key or all keys.
    
    Args:
        api_key: Optional API key to filter stats for
        days: Number of days to look back
        
    Returns:
        Dictionary with usage statistics
    """
    if not redis_client:
        return {"error": "Redis not available for usage tracking"}
    
    try:
        stats = {
            "total_requests": 0,
            "endpoints": {},
            "daily": {},
            "status_codes": {},
            "avg_response_time": 0
        }
        
        # Calculate date range
        today = datetime.now()
        date_range = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        
        # Get keys to scan based on whether we're filtering by API key
        if api_key:
            key_pattern = f"usage:{api_key}:*"
        else:
            key_pattern = "usage:*"
        
        # Scan all matching keys
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match=key_pattern, count=100)
            
            for key in keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                
                # Parse key to extract components
                parts = key_str.split(':')
                
                # Skip keys that don't match our expected format
                if len(parts) < 3:
                    continue
                
                # Process based on key type
                if "daily" in key_str and any(date in key_str for date in date_range):
                    # Daily counts
                    date = parts[-1]
                    count = int(redis_client.get(key_str) or 0)
                    stats["daily"][date] = stats["daily"].get(date, 0) + count
                    stats["total_requests"] += count
                
                elif "endpoint" in key_str and any(date in key_str for date in date_range):
                    # Endpoint-specific counts
                    endpoint = parts[3]
                    count = int(redis_client.get(key_str) or 0)
                    stats["endpoints"][endpoint] = stats["endpoints"].get(endpoint, 0) + count
                
                elif "status" in key_str and any(date in key_str for date in date_range):
                    # Status code counts
                    status = parts[3]
                    count = int(redis_client.get(key_str) or 0)
                    stats["status_codes"][status] = stats["status_codes"].get(status, 0) + count
                
                elif "response_times" in key_str and any(date in key_str for date in date_range):
                    # Response times
                    times = redis_client.lrange(key_str, 0, -1)
                    if times:
                        times = [float(t) for t in times]
                        endpoint = parts[3]
                        if "response_times" not in stats:
                            stats["response_times"] = {}
                        if endpoint not in stats["response_times"]:
                            stats["response_times"][endpoint] = []
                        stats["response_times"][endpoint].extend(times)
            
            # Exit loop when we've scanned all keys
            if cursor == 0:
                break
        
        # Calculate average response times
        if "response_times" in stats:
            all_times = []
            for endpoint, times in stats["response_times"].items():
                all_times.extend(times)
                stats["response_times"][endpoint] = {
                    "avg": sum(times) / len(times) if times else 0,
                    "min": min(times) if times else 0,
                    "max": max(times) if times else 0,
                    "count": len(times)
                }
            
            if all_times:
                stats["avg_response_time"] = sum(all_times) / len(all_times)
            
        return stats
    
    except Exception as e:
        logger.error(f"Error getting usage stats: {str(e)}", exc_info=True)
        return {"error": str(e)} 