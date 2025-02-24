import redis
import json
import os
import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast
import hashlib
import pickle
from datetime import timedelta
import asyncio

# Set up logging
logger = logging.getLogger(__name__)

# Type variable for function return type
T = TypeVar('T')

# Initialize Redis client if REDIS_URL is set
redis_client = None
if os.getenv("REDIS_URL"):
    try:
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        redis_client.ping()  # Test connection
        logger.info("Redis cache initialized successfully")
    except redis.ConnectionError:
        logger.warning("Failed to connect to Redis. Caching will be disabled.")
        redis_client = None
else:
    logger.info("REDIS_URL not set. Caching will be disabled.")

def redis_cache(
    ttl: int = 3600,  # Default TTL: 1 hour
    prefix: str = "",
    serialize_json: bool = False
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Redis caching decorator for any function.
    
    Args:
        ttl: Time to live in seconds
        prefix: Prefix for the cache key
        serialize_json: Whether to serialize/deserialize as JSON
        
    Returns:
        Decorated function with caching
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            if not redis_client:
                return await func(*args, **kwargs)
                
            # Generate a cache key based on function name, args, and kwargs
            key_parts = [prefix, func.__name__]
            
            # Add args and kwargs to key
            if args:
                for arg in args:
                    if hasattr(arg, '__dict__'):
                        # For objects, use their dict representation
                        key_parts.append(str(arg.__dict__))
                    else:
                        key_parts.append(str(arg))
            
            if kwargs:
                for k, v in sorted(kwargs.items()):
                    if hasattr(v, '__dict__'):
                        key_parts.append(f"{k}:{str(v.__dict__)}")
                    else:
                        key_parts.append(f"{k}:{str(v)}")
            
            # Create a hash of the key parts to keep keys manageable
            key_string = "_".join(key_parts)
            cache_key = f"{prefix}:{hashlib.md5(key_string.encode()).hexdigest()}"
            
            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {func.__name__}")
                if serialize_json:
                    return json.loads(cached)
                else:
                    return pickle.loads(cached)
            
            # Execute function if not in cache
            logger.info(f"Cache miss for {func.__name__}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                if serialize_json:
                    redis_client.setex(cache_key, ttl, json.dumps(result))
                else:
                    redis_client.setex(cache_key, ttl, pickle.dumps(result))
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            if not redis_client:
                return func(*args, **kwargs)
                
            # Generate a cache key based on function name, args, and kwargs
            key_parts = [prefix, func.__name__]
            
            # Add args and kwargs to key
            if args:
                for arg in args:
                    if hasattr(arg, '__dict__'):
                        # For objects, use their dict representation
                        key_parts.append(str(arg.__dict__))
                    else:
                        key_parts.append(str(arg))
            
            if kwargs:
                for k, v in sorted(kwargs.items()):
                    if hasattr(v, '__dict__'):
                        key_parts.append(f"{k}:{str(v.__dict__)}")
                    else:
                        key_parts.append(f"{k}:{str(v)}")
            
            # Create a hash of the key parts to keep keys manageable
            key_string = "_".join(key_parts)
            cache_key = f"{prefix}:{hashlib.md5(key_string.encode()).hexdigest()}"
            
            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {func.__name__}")
                if serialize_json:
                    return json.loads(cached)
                else:
                    return pickle.loads(cached)
            
            # Execute function if not in cache
            logger.info(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                if serialize_json:
                    redis_client.setex(cache_key, ttl, json.dumps(result))
                else:
                    redis_client.setex(cache_key, ttl, pickle.dumps(result))
            
            return result
        
        # Return the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        return cast(Callable[..., T], sync_wrapper)
    
    return decorator

def clear_cache(pattern: str = "*") -> None:
    """Clear cache entries matching the given pattern"""
    if not redis_client:
        logger.warning("Redis not available, cannot clear cache")
        return
    
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)
        logger.info(f"Cleared {len(keys)} cache entries matching pattern: {pattern}")
    else:
        logger.info(f"No cache entries found matching pattern: {pattern}")

def get_cache_stats() -> dict:
    """Get cache statistics"""
    if not redis_client:
        return {"status": "disabled"}
    
    info = redis_client.info()
    return {
        "status": "enabled",
        "used_memory": info.get("used_memory_human", "unknown"),
        "connected_clients": info.get("connected_clients", 0),
        "uptime_in_days": info.get("uptime_in_days", 0),
        "total_keys": len(redis_client.keys("*"))
    }

# Memory-based LRU cache for environments without Redis
from functools import lru_cache as python_lru_cache

def memory_cache(maxsize: int = 128, ttl: Optional[int] = None):
    """
    In-memory LRU cache decorator with optional TTL
    
    Args:
        maxsize: Maximum size of cache
        ttl: Time to live in seconds (None means no expiration)
        
    Returns:
        Decorated function with caching
    """
    if ttl is None:
        # Simple LRU cache without TTL
        return python_lru_cache(maxsize=maxsize)
    
    # For TTL support, we need a custom implementation
    cache = {}
    from time import time
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str((args, frozenset(kwargs.items())))
            
            # Check if in cache and not expired
            if key in cache:
                result, timestamp = cache[key]
                if ttl is None or time() - timestamp < ttl:
                    return result
                # Remove if expired
                del cache[key]
            
            # Call function and cache result
            result = func(*args, **kwargs)
            
            # Manage cache size (simple LRU - remove oldest)
            if len(cache) >= maxsize:
                oldest_key = min(cache.items(), key=lambda x: x[1][1])[0]
                del cache[oldest_key]
                
            cache[key] = (result, time())
            return result
        
        # Add cache_info method similar to lru_cache
        def cache_info():
            return {
                "hits": 0,  # Not tracked in this simple implementation
                "misses": 0,  # Not tracked in this simple implementation
                "maxsize": maxsize,
                "currsize": len(cache),
                "ttl": ttl
            }
        
        wrapper.cache_info = cache_info
        
        # Add cache_clear method
        def cache_clear():
            cache.clear()
        
        wrapper.cache_clear = cache_clear
        
        return wrapper
    
    return decorator 