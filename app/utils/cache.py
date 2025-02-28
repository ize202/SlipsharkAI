import redis
import json
import os
import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast, Dict, get_type_hints
import hashlib
import pickle
from datetime import datetime, timedelta
import asyncio
import time
import threading

# Set up logging with more detail
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled

# Type variable for function return type
T = TypeVar('T')

# Global configuration
GLOBAL_MEMORY_CACHE_MAX_SIZE = 1000  # Maximum number of items across all memory caches
CLEANUP_INTERVAL = 300  # Cleanup every 5 minutes

# Initialize Redis client if REDIS_URL is set
redis_client = None
use_memory_fallback = False  # Flag to indicate if we should use memory cache as fallback

if os.getenv("REDIS_URL"):
    try:
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        redis_client.ping()  # Test connection
        logger.info("Redis cache initialized successfully")
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        logger.warning("Will use in-memory cache as fallback.")
        redis_client = None
        use_memory_fallback = True
else:
    logger.info("REDIS_URL not set. Will use in-memory cache as fallback.")
    use_memory_fallback = True

# Dictionary to store memory cache instances for different TTLs
memory_cache_instances = {}
memory_cache_lock = threading.Lock()
total_memory_cache_size = 0

def cleanup_memory_cache():
    """Periodically clean up expired entries from memory cache"""
    global total_memory_cache_size
    
    while True:
        time.sleep(CLEANUP_INTERVAL)
        current_time = time.time()
        with memory_cache_lock:
            cleaned = 0
            for ttl, cache in memory_cache_instances.items():
                expired_keys = [
                    key for key, (_, timestamp) in cache.items()
                    if current_time - timestamp > ttl
                ]
                for key in expired_keys:
                    del cache[key]
                    total_memory_cache_size -= 1
                    cleaned += 1
            if cleaned > 0:
                logger.info(f"Cleaned {cleaned} expired items from memory cache")

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_memory_cache, daemon=True)
cleanup_thread.start()

def get_or_create_memory_cache(ttl: int, maxsize: int = 128):
    """Get or create a memory cache with the specified TTL"""
    global total_memory_cache_size
    
    with memory_cache_lock:
        if ttl not in memory_cache_instances:
            # Check if we need to clean up old entries
            if total_memory_cache_size >= GLOBAL_MEMORY_CACHE_MAX_SIZE:
                # Remove oldest entries across all caches
                all_entries = []
                for cache_ttl, cache in memory_cache_instances.items():
                    all_entries.extend([(cache_ttl, key, timestamp) 
                                      for key, (_, timestamp) in cache.items()])
                
                all_entries.sort(key=lambda x: x[2])  # Sort by timestamp
                
                # Remove oldest entries until we're under the limit
                entries_to_remove = len(all_entries) - GLOBAL_MEMORY_CACHE_MAX_SIZE + 1
                for cache_ttl, key, _ in all_entries[:entries_to_remove]:
                    del memory_cache_instances[cache_ttl][key]
                    total_memory_cache_size -= 1
                
            memory_cache_instances[ttl] = {}
        return memory_cache_instances[ttl]

def _generate_cache_key(prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a consistent cache key based on function arguments"""
    key_parts = [prefix, func_name]
    
    # Handle special cases for research queries
    if func_name in ['quick_research', 'process_request']:
        # Extract query from args or kwargs
        query = None
        context = None
        has_context = False
        
        logger.debug(f"Generating cache key for {func_name} with args: {args} and kwargs: {kwargs}")
        
        if args and isinstance(args[0], str):
            query = args[0]
            logger.debug(f"Extracted query from args[0] as string: {query}")
        elif 'query' in kwargs:
            query = kwargs['query']
            logger.debug(f"Extracted query from kwargs: {query}")
        elif args and len(args) > 1 and hasattr(args[1], 'query'):
            # Handle case where first arg is self (ResearchChain)
            query = args[1].query
            logger.debug(f"Extracted query from args[1].query: {query}")
            # Also extract context if available
            if hasattr(args[1], 'context') and args[1].context:
                context = args[1].context
                has_context = True
                logger.debug(f"Extracted context from args[1].context: {context}")
            else:
                logger.debug("No context found in args[1].context")
        elif args and hasattr(args[0], 'query'):
            query = args[0].query
            logger.debug(f"Extracted query from args[0].query: {query}")
            # Also extract context if available
            if hasattr(args[0], 'context') and args[0].context:
                context = args[0].context
                has_context = True
                logger.debug(f"Extracted context from args[0].context: {context}")
            else:
                logger.debug("No context found in args[0].context")
            
        if query:
            # Normalize query by removing extra whitespace and converting to lowercase
            normalized_query = ' '.join(query.lower().split())
            key_parts.append(f"query:{normalized_query}")
            logger.debug(f"Added normalized query to key parts: {normalized_query}")
            
        # Add context if present
        if context:
            # Convert context to a stable string representation
            if hasattr(context, 'model_dump'):
                context_dict = context.model_dump()
            else:
                context_dict = context
                
            # Only include relevant context fields
            relevant_context = {
                'teams': context_dict.get('teams', []),
                'players': context_dict.get('players', []),
                'sport': str(context_dict.get('sport', '')),
                'game_date': str(context_dict.get('game_date', '')),
                'bet_type': str(context_dict.get('bet_type', ''))
            }
            key_parts.append(f"context:{json.dumps(relevant_context, sort_keys=True)}")
            logger.debug(f"Added context to key parts: {relevant_context}")
        elif 'context' in kwargs and kwargs['context']:
            context_dict = kwargs['context'].model_dump() if hasattr(kwargs['context'], 'model_dump') else kwargs['context']
            # Only include relevant context fields
            relevant_context = {
                'teams': context_dict.get('teams', []),
                'players': context_dict.get('players', []),
                'sport': str(context_dict.get('sport', '')),
                'game_date': str(context_dict.get('game_date', '')),
                'bet_type': str(context_dict.get('bet_type', ''))
            }
            key_parts.append(f"context:{json.dumps(relevant_context, sort_keys=True)}")
            logger.debug(f"Added context from kwargs to key parts: {relevant_context}")
        else:
            # Explicitly mark that there is no context
            key_parts.append("context:none")
            logger.debug("Added 'context:none' to key parts")
    else:
        # For other functions, use standard key generation
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
    
    # Create a hash of the key parts
    key_string = "_".join(key_parts)
    hashed_key = f"{prefix}:{hashlib.md5(key_string.encode()).hexdigest()}"
    logger.debug(f"Generated cache key: {hashed_key} from key string: {key_string}")
    return hashed_key

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
            cache_key = _generate_cache_key(prefix, func.__name__, args, kwargs)
            
            logger.debug(f"Cache key for {func.__name__}: {cache_key}")
            
            # Try Redis cache first if available
            if redis_client:
                try:
                    logger.debug(f"Attempting to get from Redis cache: {cache_key}")
                    cached = redis_client.get(cache_key)
                    if cached:
                        logger.info(f"Redis cache hit for {func.__name__} with key {cache_key}")
                        try:
                            if serialize_json:
                                result = json.loads(cached)
                                # Check if the original function returns a Pydantic model
                                return_type_hints = getattr(func, "__annotations__", {}).get("return")
                                if return_type_hints and hasattr(return_type_hints, "__origin__") and return_type_hints.__origin__ is Callable:
                                    # For async functions, the return type is wrapped in Coroutine
                                    return_type_hints = return_type_hints.__args__[-1]
                                
                                # If we know the return type and it's a Pydantic model, reconstruct it
                                if return_type_hints and hasattr(return_type_hints, "model_validate"):
                                    result = return_type_hints.model_validate(result)
                                # Special case for ResearchResponse
                                elif func.__name__ == "process_request" and isinstance(result, dict) and "response" in result:
                                    # Import here to avoid circular imports
                                    from app.models.research_models import ResearchResponse
                                    result = ResearchResponse.model_validate(result)
                            else:
                                result = pickle.loads(cached)
                            logger.debug(f"Successfully deserialized cached value for {cache_key}")
                            increment_cache_stats(hit=True, endpoint=func.__name__)
                            return result
                        except Exception as e:
                            logger.error(f"Failed to deserialize cached value for {cache_key}: {str(e)}")
                            # Continue to function execution
                    else:
                        logger.debug(f"Redis cache miss for {cache_key}")
                        increment_cache_stats(hit=False, endpoint=func.__name__)
                except Exception as e:
                    logger.error(f"Redis error in {func.__name__}: {str(e)}. Will try memory cache if available.")
                    # Fall through to memory cache or function execution
            
            # Try memory cache if Redis failed or is unavailable
            if memory_cache is not None:
                current_time = asyncio.get_event_loop().time()
                if cache_key in memory_cache:
                    result, timestamp = memory_cache[cache_key]
                    if current_time - timestamp < ttl:
                        logger.info(f"Memory cache hit for {func.__name__}")
                        increment_cache_stats(hit=True, endpoint=f"memory_{func.__name__}")
                        return result
                    else:
                        # Remove expired entry
                        logger.debug(f"Removing expired memory cache entry for {cache_key}")
                        del memory_cache[cache_key]
                        increment_cache_stats(hit=False, endpoint=f"memory_{func.__name__}")
            
            # Execute function if not in any cache
            logger.info(f"Cache miss for {func.__name__}, executing function")
            result = await func(*args, **kwargs)
            
            # Store in Redis cache if available
            if redis_client and result is not None:
                try:
                    logger.debug(f"Attempting to store in Redis cache: {cache_key}")
                    if serialize_json:
                        # Check if result is a Pydantic model with model_dump method
                        if hasattr(result, 'model_dump') and callable(getattr(result, 'model_dump')):
                            value = json.dumps(result.model_dump(mode='json'))
                        else:
                            # Custom JSON serialization for objects with datetime fields
                            try:
                                value = json.dumps(result)
                            except TypeError as e:
                                if "datetime" in str(e):
                                    # Use a custom JSON encoder for datetime objects
                                    class DateTimeEncoder(json.JSONEncoder):
                                        def default(self, obj):
                                            if isinstance(obj, datetime):
                                                return obj.isoformat()
                                            return super().default(obj)
                                    
                                    value = json.dumps(result, cls=DateTimeEncoder)
                                else:
                                    raise
                    else:
                        value = pickle.dumps(result)
                    
                    redis_client.setex(cache_key, ttl, value)
                    logger.debug(f"Successfully stored in Redis cache: {cache_key}")
                except Exception as e:
                    logger.error(f"Failed to store in Redis cache: {str(e)}")
            
            # Store in memory cache if Redis failed or is unavailable
            if memory_cache is not None and result is not None:
                # Manage cache size (simple LRU - remove oldest)
                if len(memory_cache) >= memory_maxsize:
                    oldest_key = min(memory_cache.items(), key=lambda x: x[1][1])[0]
                    logger.debug(f"Memory cache full, removing oldest entry: {oldest_key}")
                    del memory_cache[oldest_key]
                
                current_time = asyncio.get_event_loop().time()
                memory_cache[cache_key] = (result, current_time)
                logger.debug(f"Stored in memory cache: {cache_key}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            cache_key = _generate_cache_key(prefix, func.__name__, args, kwargs)
            
            # Try Redis cache first if available
            if redis_client:
                try:
                    cached = redis_client.get(cache_key)
                    if cached:
                        logger.info(f"Redis cache hit for {func.__name__}")
                        if serialize_json:
                            result = json.loads(cached)
                            # Check if the original function returns a Pydantic model
                            return_type_hints = getattr(func, "__annotations__", {}).get("return")
                            # If we know the return type and it's a Pydantic model, reconstruct it
                            if return_type_hints and hasattr(return_type_hints, "model_validate"):
                                result = return_type_hints.model_validate(result)
                            # Special case for ResearchResponse
                            elif func.__name__ == "process_request" and isinstance(result, dict) and "response" in result:
                                # Import here to avoid circular imports
                                from app.models.research_models import ResearchResponse
                                result = ResearchResponse.model_validate(result)
                            return result
                        else:
                            return pickle.loads(cached)
                except Exception as e:
                    logger.warning(f"Redis error in {func.__name__}: {str(e)}. Will try memory cache if available.")
            
            # Try memory cache if Redis failed or is unavailable
            if memory_cache is not None:
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
                            redis_client.setex(cache_key, ttl, json.dumps(result.model_dump(mode='json')))
                        else:
                            # Custom JSON serialization for objects with datetime fields
                            try:
                                redis_client.setex(cache_key, ttl, json.dumps(result))
                            except TypeError as e:
                                if "datetime" in str(e):
                                    # Use a custom JSON encoder for datetime objects
                                    class DateTimeEncoder(json.JSONEncoder):
                                        def default(self, obj):
                                            if isinstance(obj, datetime):
                                                return obj.isoformat()
                                            return super().default(obj)
                                    
                                    redis_client.setex(cache_key, ttl, json.dumps(result, cls=DateTimeEncoder))
                                else:
                                    raise
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
                
                current_time = time.time()
                memory_cache[cache_key] = (result, current_time)
            
            return result
        
        # Return the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        return cast(Callable[..., T], sync_wrapper)
    
    return decorator

async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    stats = {
        "hits": 0,
        "misses": 0,
        "keys": 0,
        "memory_usage": "0",
        "hit_rate": "0%",
        "endpoints": {}
    }
    
    if redis_client:
        try:
            # Get cache hits and misses
            hits = int(redis_client.get("cache:hits") or 0)
            misses = int(redis_client.get("cache:misses") or 0)
            stats["hits"] = hits
            stats["misses"] = misses
            
            # Calculate hit rate
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            stats["hit_rate"] = f"{hit_rate:.1f}%"
            
            # Get number of cache keys
            keys = len(redis_client.keys("*"))
            stats["keys"] = keys
            
            # Get memory usage
            info = redis_client.info(section="memory")
            stats["memory_usage"] = f"{info['used_memory_human']}"
            
            # Get endpoint-specific stats
            for key in redis_client.scan_iter("cache:endpoints:*"):
                endpoint = key.decode('utf-8').split(':')[-1]
                hits = int(redis_client.get(f"cache:endpoints:{endpoint}:hits") or 0)
                misses = int(redis_client.get(f"cache:endpoints:{endpoint}:misses") or 0)
                total = hits + misses
                hit_rate = (hits / total * 100) if total > 0 else 0
                
                stats["endpoints"][endpoint] = {
                    "hits": hits,
                    "misses": misses,
                    "hit_rate": f"{hit_rate:.1f}%"
                }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            stats["error"] = str(e)
    else:
        stats["status"] = "Redis not available"
        
        # Get memory cache stats
        memory_hits = sum(1 for cache in memory_cache_instances.values() 
                         for key, (_, timestamp) in cache.items()
                         if time.time() - timestamp < cache.get("ttl", 3600))
        memory_total = sum(len(cache) for cache in memory_cache_instances.values())
        stats["memory_cache"] = {
            "hits": memory_hits,
            "total_keys": memory_total
        }
    
    return stats

def increment_cache_stats(hit: bool, endpoint: str = "unknown"):
    """Increment cache hit/miss counters"""
    if redis_client:
        try:
            # Increment global counters
            if hit:
                redis_client.incr("cache:hits")
            else:
                redis_client.incr("cache:misses")
            
            # Increment endpoint-specific counters
            if hit:
                redis_client.incr(f"cache:endpoints:{endpoint}:hits")
            else:
                redis_client.incr(f"cache:endpoints:{endpoint}:misses")
        except Exception as e:
            logger.error(f"Error incrementing cache stats: {str(e)}")

async def clear_cache(pattern: str = "*") -> None:
    """Clear cache entries matching the given pattern"""
    # Clear Redis cache if available
    if redis_client:
        try:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} Redis cache entries matching pattern: {pattern}")
                
            # Reset cache statistics
            stat_keys = redis_client.keys("cache:*")
            if stat_keys:
                redis_client.delete(*stat_keys)
                logger.info("Reset cache statistics")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
    
    # Clear memory cache
    if pattern == "*":
        memory_cache_instances.clear()
        logger.info("Cleared memory cache")

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