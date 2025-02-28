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
use_memory_fallback = False  # Flag to indicate if we should use memory cache as fallback

if os.getenv("REDIS_URL"):
    try:
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        redis_client.ping()  # Test connection
        logger.info("Redis cache initialized successfully")
    except redis.ConnectionError:
        logger.warning("Failed to connect to Redis. Will use in-memory cache as fallback.")
        redis_client = None
        use_memory_fallback = True
else:
    logger.info("REDIS_URL not set. Will use in-memory cache as fallback.")
    use_memory_fallback = True

# Dictionary to store memory cache instances for different TTLs
memory_cache_instances = {}

def get_or_create_memory_cache(ttl: int, maxsize: int = 128):
    """Get or create a memory cache with the specified TTL"""
    if ttl not in memory_cache_instances:
        memory_cache_instances[ttl] = {}
    return memory_cache_instances[ttl]

def redis_cache(
    ttl: int = 3600,  # Default TTL: 1 hour
    prefix: str = "",
    serialize_json: bool = False,
    memory_fallback: bool = True,  # Whether to use memory cache as fallback
    memory_maxsize: int = 128  # Max size for memory cache
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Redis caching decorator for any function.
    
    Args:
        ttl: Time to live in seconds
        prefix: Prefix for the cache key
        serialize_json: Whether to serialize/deserialize as JSON
        memory_fallback: Whether to use memory cache as fallback when Redis is unavailable
        memory_maxsize: Maximum size for memory cache
        
    Returns:
        Decorated function with caching
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Create a memory cache for this function if fallback is enabled
        memory_cache = None
        if (use_memory_fallback or not redis_client) and memory_fallback:
            memory_cache = get_or_create_memory_cache(ttl, memory_maxsize)
            logger.debug(f"Created memory cache fallback for {func.__name__} with TTL {ttl}s")
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
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
            
            # Try Redis cache first if available
            if redis_client:
                try:
                    cached = redis_client.get(cache_key)
                    if cached:
                        logger.info(f"Redis cache hit for {func.__name__}")
                        if serialize_json:
                            return json.loads(cached)
                        else:
                            return pickle.loads(cached)
                except Exception as e:
                    logger.warning(f"Redis error in {func.__name__}: {str(e)}. Will try memory cache if available.")
                    # Fall through to memory cache or function execution
            
            # Try memory cache if Redis failed or is unavailable
            if memory_cache is not None:
                current_time = asyncio.get_event_loop().time()
                if cache_key in memory_cache:
                    result, timestamp = memory_cache[cache_key]
                    if current_time - timestamp < ttl:
                        logger.info(f"Memory cache hit for {func.__name__}")
                        return result
                    else:
                        # Remove expired entry
                        del memory_cache[cache_key]
            
            # Execute function if not in any cache
            logger.info(f"Cache miss for {func.__name__}")
            result = await func(*args, **kwargs)
            
            # Store in Redis cache if available
            if redis_client and result is not None:
                try:
                    if serialize_json:
                        # Check if result is a Pydantic model with model_dump method
                        if hasattr(result, 'model_dump') and callable(getattr(result, 'model_dump')):
                            redis_client.setex(cache_key, ttl, json.dumps(result.model_dump()))
                        else:
                            redis_client.setex(cache_key, ttl, json.dumps(result))
                    else:
                        redis_client.setex(cache_key, ttl, pickle.dumps(result))
                except Exception as e:
                    logger.warning(f"Failed to store in Redis cache: {str(e)}")
            
            # Store in memory cache if Redis failed or is unavailable
            if memory_cache is not None and result is not None:
                # Manage cache size (simple LRU - remove oldest)
                if len(memory_cache) >= memory_maxsize:
                    oldest_key = min(memory_cache.items(), key=lambda x: x[1][1])[0]
                    del memory_cache[oldest_key]
                
                current_time = asyncio.get_event_loop().time()
                memory_cache[cache_key] = (result, current_time)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
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
            
            # Try Redis cache first if available
            if redis_client:
                try:
                    cached = redis_client.get(cache_key)
                    if cached:
                        logger.info(f"Redis cache hit for {func.__name__}")
                        if serialize_json:
                            return json.loads(cached)
                        else:
                            return pickle.loads(cached)
                except Exception as e:
                    logger.warning(f"Redis error in {func.__name__}: {str(e)}. Will try memory cache if available.")
                    # Fall through to memory cache or function execution
            
            # Try memory cache if Redis failed or is unavailable
            if memory_cache is not None:
                import time
                current_time = time.time()
                if cache_key in memory_cache:
                    result, timestamp = memory_cache[cache_key]
                    if current_time - timestamp < ttl:
                        logger.info(f"Memory cache hit for {func.__name__}")
                        return result
                    else:
                        # Remove expired entry
                        del memory_cache[cache_key]
            
            # Execute function if not in any cache
            logger.info(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store in Redis cache if available
            if redis_client and result is not None:
                try:
                    if serialize_json:
                        # Check if result is a Pydantic model with model_dump method
                        if hasattr(result, 'model_dump') and callable(getattr(result, 'model_dump')):
                            redis_client.setex(cache_key, ttl, json.dumps(result.model_dump()))
                        else:
                            redis_client.setex(cache_key, ttl, json.dumps(result))
                    else:
                        redis_client.setex(cache_key, ttl, pickle.dumps(result))
                except Exception as e:
                    logger.warning(f"Failed to store in Redis cache: {str(e)}")
            
            # Store in memory cache if Redis failed or is unavailable
            if memory_cache is not None and result is not None:
                # Manage cache size (simple LRU - remove oldest)
                if len(memory_cache) >= memory_maxsize:
                    oldest_key = min(memory_cache.items(), key=lambda x: x[1][1])[0]
                    del memory_cache[oldest_key]
                
                import time
                current_time = time.time()
                memory_cache[cache_key] = (result, current_time)
            
            return result
        
        # Return the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        return cast(Callable[..., T], sync_wrapper)
    
    return decorator

def clear_cache(pattern: str = "*") -> None:
    """Clear cache entries matching the given pattern"""
    # Clear Redis cache if available
    if redis_client:
        try:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} Redis cache entries matching pattern: {pattern}")
        except Exception as e:
            logger.warning(f"Failed to clear Redis cache: {str(e)}")
    
    # Clear memory cache
    cleared_count = 0
    for ttl, cache in memory_cache_instances.items():
        # Simple pattern matching for memory cache
        keys_to_delete = []
        for key in cache.keys():
            if pattern == "*" or pattern in key:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del cache[key]
            cleared_count += 1
    
    if cleared_count > 0:
        logger.info(f"Cleared {cleared_count} memory cache entries matching pattern: {pattern}")

async def get_cache_stats() -> dict:
    """Get cache statistics"""
    stats = {
        "hits": 0,
        "misses": 0,
        "size": 0,
        "memory_usage": "0 MB"
    }
    
    # Get Redis stats if available
    if redis_client:
        try:
            info = redis_client.info()
            stats["hits"] = info.get("keyspace_hits", 0)
            stats["misses"] = info.get("keyspace_misses", 0)
            stats["size"] = redis_client.dbsize()
            stats["memory_usage"] = f"{info.get('used_memory_human', '0B')}"
        except Exception as e:
            logger.error(f"Error getting Redis stats: {str(e)}")
            
    # Add memory cache stats
    for cache in memory_cache_instances.values():
        stats["size"] += len(cache)
        
    return stats

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