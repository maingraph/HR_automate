"""Redis cache client and decorators for performance optimization."""
from __future__ import annotations

import json
import hashlib
from functools import wraps
from typing import Optional, Callable, Any, TypeVar
from redis import Redis

from .config import settings
from .logging import get_logger

log = get_logger(__name__)

# Initialize Redis client
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

T = TypeVar('T')


def cache_result(ttl: int = 300, key_prefix: str = ""):
    """
    Cache function result in Redis with TTL.
    
    Args:
        ttl: Time to live in seconds (default 5 minutes)
        key_prefix: Prefix for cache key
    
    Usage:
        @cache_result(ttl=300, key_prefix="campaign")
        async def get_campaign(campaign_id: str):
            return await fetch_campaign(campaign_id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Generate cache key from function name + args
            key_data = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try cache first
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    log.debug(f"Cache HIT: {func.__name__} (key: {cache_key[:8]}...)")
                    return json.loads(cached)
            except Exception as e:
                log.warning(f"Cache read error: {e}")
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            try:
                redis_client.setex(cache_key, ttl, json.dumps(result))
                log.debug(f"Cache SET: {func.__name__} (TTL: {ttl}s)")
            except Exception as e:
                log.warning(f"Cache write error: {e}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # Generate cache key from function name + args
            key_data = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try cache first
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    log.debug(f"Cache HIT: {func.__name__} (key: {cache_key[:8]}...)")
                    return json.loads(cached)
            except Exception as e:
                log.warning(f"Cache read error: {e}")
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            try:
                redis_client.setex(cache_key, ttl, json.dumps(result))
                log.debug(f"Cache SET: {func.__name__} (TTL: {ttl}s)")
            except Exception as e:
                log.warning(f"Cache write error: {e}")
            
            return result
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def invalidate_cache(key_prefix: str, *args, **kwargs):
    """
    Invalidate cache entries matching the prefix and args.
    
    Args:
        key_prefix: Prefix used in cache_result decorator
        *args, **kwargs: Arguments used in the cached function
    
    Usage:
        invalidate_cache("campaign", campaign_id="123")
    """
    key_data = f"{key_prefix}:*:{args}:{kwargs}"
    cache_key = hashlib.md5(key_data.encode()).hexdigest()
    
    try:
        # Delete the specific key
        redis_client.delete(cache_key)
        log.debug(f"Cache INVALIDATE: {key_prefix} (key: {cache_key[:8]}...)")
    except Exception as e:
        log.warning(f"Cache invalidation error: {e}")


def clear_cache_pattern(pattern: str):
    """
    Clear all cache keys matching a pattern.
    
    Args:
        pattern: Redis key pattern (e.g., "campaign:*")
    
    Usage:
        clear_cache_pattern("campaign:*")
    """
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
            log.info(f"Cache CLEAR: {len(keys)} keys matching '{pattern}'")
    except Exception as e:
        log.warning(f"Cache clear error: {e}")


def get_cache_stats() -> dict:
    """Get Redis cache statistics."""
    try:
        info = redis_client.info("stats")
        return {
            "total_connections": info.get("total_connections_received", 0),
            "total_commands": info.get("total_commands_processed", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "hit_rate": (
                info.get("keyspace_hits", 0) / 
                (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
            ) * 100,
        }
    except Exception as e:
        log.error(f"Failed to get cache stats: {e}")
        return {}
