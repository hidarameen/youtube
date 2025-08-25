
"""
Cache helpers for faster bot operations
"""
import time
from typing import Any, Optional, Callable
from functools import wraps

def cache_result(cache_manager, key: str, ttl: int = 300):
    """Decorator to cache function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to get from cache first
            cached_result = await cache_manager.get(key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(key, result, expire=ttl)
            return result
        return wrapper
    return decorator

async def quick_user_check(cache_manager, user_id: int) -> Optional[bool]:
    """Quick user authorization check from cache"""
    cache_key = f"quick_auth:{user_id}"
    return await cache_manager.get(cache_key)

async def set_quick_user_check(cache_manager, user_id: int, allowed: bool):
    """Set quick user authorization in cache"""
    cache_key = f"quick_auth:{user_id}"
    await cache_manager.set(cache_key, allowed, expire=300)  # 5 minutes

async def is_rate_limited(cache_manager, user_id: int) -> bool:
    """Quick rate limit check"""
    rate_key = f"rate_quick:{user_id}"
    last_request = await cache_manager.get(rate_key)
    
    if last_request:
        time_diff = time.time() - float(last_request)
        return time_diff < 0.5  # 500ms minimum between requests
    
    # Update last request time
    await cache_manager.set(rate_key, str(time.time()), expire=60)
    return False
