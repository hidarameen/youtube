"""
High-performance Redis cache manager for ultra-fast data access
Implements advanced caching strategies with automatic cleanup and optimization
"""

import asyncio
import logging
import json
import time
from typing import Any, Optional, Dict, List, Union
import redis.asyncio as aioredis
from redis.asyncio import Redis

from config.settings import settings
from utils.helpers import serialize_for_cache, deserialize_from_cache

logger = logging.getLogger(__name__)

class CacheManager:
    """Ultra high-performance Redis cache manager"""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.connection_pool = None
        self.is_connected = False
        self.key_prefix = "cache:" # Added key prefix for better organization

        # Cache statistics
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }

        # Performance optimization settings
        self.default_ttl = 3600  # 1 hour
        self.max_connections = 20
        self.retry_attempts = 3
        self.retry_delay = 1

        # Cache eviction policies
        self.max_cache_size = 500 * 1024 * 1024  # 500MB max cache
        self.eviction_policy = 'lru'  # Least Recently Used

        # Cache warming
        self.warm_cache_on_startup = True

    async def initialize(self):
        """Initialize Redis connection with optimization"""
        try:
            logger.info("🔧 Initializing Redis cache manager...")

            # Parse Redis URL
            redis_url = settings.REDIS_URL
            
            # Try to create Redis client directly from URL first
            try:
                self.redis = aioredis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
            except Exception as url_error:
                logger.warning(f"Failed to connect via URL, trying manual configuration: {url_error}")
                
                # Fallback to manual configuration
                # Extract Redis settings from environment or use defaults
                redis_host = getattr(settings, 'REDIS_HOST', 'localhost')
                redis_port = getattr(settings, 'REDIS_PORT', 6379)
                redis_password = getattr(settings, 'REDIS_PASSWORD', None)
                redis_db = getattr(settings, 'REDIS_DB', 0)

                # Configure Redis connection with ultra-fast settings
                self.connection_pool = aioredis.ConnectionPool(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password if redis_password else None,
                    db=redis_db,
                    decode_responses=True,
                    max_connections=20,  # Reasonable pool size
                    retry_on_timeout=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30
                )

            # Create Redis client
                self.redis = aioredis.Redis(
                    connection_pool=self.connection_pool,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )

            # Test connection
            await self._test_connection()

            self.is_connected = True
            logger.info("✅ Redis cache manager initialized successfully")

        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}")
            # Fallback to in-memory cache if Redis is not available
            await self._fallback_to_memory_cache()

    async def _test_connection(self):
        """Test Redis connection"""
        try:
            if self.redis is not None:
                await self.redis.ping()
                logger.info("✅ Redis connection test successful")
            else:
                raise RuntimeError("Redis client not initialized")
        except Exception as e:
            logger.error(f"❌ Redis connection test failed: {e}")
            raise

    async def _fallback_to_memory_cache(self):
        """Fallback to in-memory cache when Redis is unavailable"""
        logger.warning("⚠️ Falling back to in-memory cache")
        self.redis = None
        self.is_connected = False

        # Simple in-memory cache implementation
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._memory_cache_expiry: Dict[str, float] = {}

    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None,
        nx: bool = False
    ) -> bool:
        """
        Set a value in cache with optional expiration

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            expire: Expiration time in seconds (default: 1 hour)
            nx: Only set if key doesn't exist
        """
        try:
            if expire is None:
                expire = self.default_ttl

            # Serialize value for caching
            serialized_value = serialize_for_cache(value)

            if self.redis and self.is_connected:
                # Use Redis
                if nx:
                    result = await self.redis.set(key, serialized_value, ex=expire, nx=True)
                else:
                    result = await self.redis.set(key, serialized_value, ex=expire)
                success = result is not False
            else:
                # Use memory cache
                if nx and key in self._memory_cache:
                    success = False
                else:
                    self._memory_cache[key] = {
                        'value': serialized_value,
                        'created': time.time()
                    }
                    self._memory_cache_expiry[key] = time.time() + expire
                    success = True

            if success:
                self.cache_stats['sets'] += 1
                logger.debug(f"✅ Cached: {key} (TTL: {expire}s)")

            return success

        except Exception as e:
            self.cache_stats['errors'] += 1
            logger.error(f"❌ Cache set failed for {key}: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        try:
            if self.redis and self.is_connected:
                # Use Redis
                value = await self.redis.get(key)
                if value is not None:
                    self.cache_stats['hits'] += 1
                    return deserialize_from_cache(value)
                else:
                    self.cache_stats['misses'] += 1
                    return None
            else:
                # Use memory cache
                current_time = time.time()

                # Check if key exists and not expired
                if key in self._memory_cache:
                    if key in self._memory_cache_expiry:
                        if current_time > self._memory_cache_expiry[key]:
                            # Expired, remove it
                            del self._memory_cache[key]
                            del self._memory_cache_expiry[key]
                            self.cache_stats['misses'] += 1
                            return None

                    # Return cached value
                    cached_data = self._memory_cache[key]
                    self.cache_stats['hits'] += 1
                    return deserialize_from_cache(cached_data['value'])
                else:
                    self.cache_stats['misses'] += 1
                    return None

        except Exception as e:
            self.cache_stats['errors'] += 1
            logger.error(f"❌ Cache get failed for {key}: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        try:
            if self.redis and self.is_connected:
                # Use Redis
                result = await self.redis.delete(key)
                success = result > 0
            else:
                # Use memory cache
                if key in self._memory_cache:
                    del self._memory_cache[key]
                    if key in self._memory_cache_expiry:
                        del self._memory_cache_expiry[key]
                    success = True
                else:
                    success = False

            if success:
                self.cache_stats['deletes'] += 1
                logger.debug(f"🗑️ Deleted cache key: {key}")

            return success

        except Exception as e:
            self.cache_stats['errors'] += 1
            logger.error(f"❌ Cache delete failed for {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        try:
            if self.redis and self.is_connected:
                return await self.redis.exists(key) > 0
            else:
                current_time = time.time()
                if key in self._memory_cache:
                    # Check expiration
                    if key in self._memory_cache_expiry:
                        if current_time > self._memory_cache_expiry[key]:
                            del self._memory_cache[key]
                            del self._memory_cache_expiry[key]
                            return False
                    return True
                return False

        except Exception as e:
            logger.error(f"❌ Cache exists check failed for {key}: {e}")
            return False

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key"""
        try:
            if self.redis and self.is_connected:
                return await self.redis.expire(key, seconds) > 0
            else:
                if key in self._memory_cache:
                    self._memory_cache_expiry[key] = time.time() + seconds
                    return True
                return False

        except Exception as e:
            logger.error(f"❌ Cache expire failed for {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """Get time to live for a key"""
        try:
            if self.redis and self.is_connected:
                return await self.redis.ttl(key)
            else:
                current_time = time.time()
                if key in self._memory_cache_expiry:
                    remaining = self._memory_cache_expiry[key] - current_time
                    return max(0, int(remaining))
                return -1

        except Exception as e:
            logger.error(f"❌ Cache TTL check failed for {key}: {e}")
            return -1

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a numeric value in cache"""
        try:
            if self.redis and self.is_connected:
                return await self.redis.incrby(key, amount)
            else:
                current_value = await self.get(key) or 0
                new_value = int(current_value) + amount
                await self.set(key, new_value)
                return new_value

        except Exception as e:
            logger.error(f"❌ Cache increment failed for {key}: {e}")
            return 0

    async def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement a numeric value in cache"""
        try:
            if self.redis and self.is_connected:
                return await self.redis.decrby(key, amount)
            else:
                current_value = await self.get(key) or 0
                new_value = int(current_value) - amount
                await self.set(key, new_value)
                return new_value

        except Exception as e:
            logger.error(f"❌ Cache decrement failed for {key}: {e}")
            return 0

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        try:
            if self.redis and self.is_connected:
                # Use Redis MGET for better performance
                values = await self.redis.mget(keys)
                result = {}
                for i, key in enumerate(keys):
                    if values[i] is not None:
                        result[key] = deserialize_from_cache(values[i])
                        self.cache_stats['hits'] += 1
                    else:
                        self.cache_stats['misses'] += 1
                return result
            else:
                # Use memory cache
                result = {}
                for key in keys:
                    value = await self.get(key)
                    if value is not None:
                        result[key] = value
                return result

        except Exception as e:
            self.cache_stats['errors'] += 1
            logger.error(f"❌ Cache get_many failed: {e}")
            return {}

    async def set_many(self, mapping: Dict[str, Any], expire: Optional[int] = None) -> bool:
        """Set multiple values in cache"""
        try:
            if expire is None:
                expire = self.default_ttl

            if self.redis and self.is_connected:
                # Use Redis pipeline for better performance
                pipe = self.redis.pipeline()
                for key, value in mapping.items():
                    serialized_value = serialize_for_cache(value)
                    pipe.set(key, serialized_value, ex=expire)

                results = await pipe.execute()
                success_count = sum(1 for result in results if result)
                self.cache_stats['sets'] += success_count

                return success_count == len(mapping)
            else:
                # Use memory cache
                current_time = time.time()
                for key, value in mapping.items():
                    serialized_value = serialize_for_cache(value)
                    self._memory_cache[key] = {
                        'value': serialized_value,
                        'created': current_time
                    }
                    self._memory_cache_expiry[key] = current_time + expire

                self.cache_stats['sets'] += len(mapping)
                return True

        except Exception as e:
            self.cache_stats['errors'] += 1
            logger.error(f"❌ Cache set_many failed: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern"""
        try:
            if self.redis and self.is_connected:
                # Use Redis SCAN for memory-efficient pattern matching
                keys = []
                async for key in self.redis.scan_iter(match=pattern):
                    keys.append(key)

                if keys:
                    deleted = await self.redis.delete(*keys)
                    self.cache_stats['deletes'] += deleted
                    logger.info(f"🗑️ Cleared {deleted} cache keys matching pattern: {pattern}")
                    return deleted
                return 0
            else:
                # Use memory cache
                import fnmatch
                keys_to_delete = []
                for key in self._memory_cache.keys():
                    if fnmatch.fnmatch(key, pattern):
                        keys_to_delete.append(key)

                for key in keys_to_delete:
                    del self._memory_cache[key]
                    if key in self._memory_cache_expiry:
                        del self._memory_cache_expiry[key]

                self.cache_stats['deletes'] += len(keys_to_delete)
                return len(keys_to_delete)

        except Exception as e:
            self.cache_stats['errors'] += 1
            logger.error(f"❌ Cache clear_pattern failed for {pattern}: {e}")
            return 0

    async def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information and statistics"""
        try:
            if self.redis and self.is_connected:
                info = await self.redis.info()
                memory_info = await self.redis.info('memory')

                return {
                    'connected': True,
                    'type': 'redis',
                    'used_memory': memory_info.get('used_memory', 0),
                    'used_memory_human': memory_info.get('used_memory_human', '0B'),
                    'connected_clients': info.get('connected_clients', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0),
                    'cache_stats': self.cache_stats.copy(),
                    'hit_rate': self._calculate_hit_rate()
                }
            else:
                return {
                    'connected': False,
                    'type': 'memory',
                    'cached_keys': len(self._memory_cache),
                    'cache_stats': self.cache_stats.copy(),
                    'hit_rate': self._calculate_hit_rate()
                }

        except Exception as e:
            logger.error(f"❌ Failed to get cache info: {e}")
            return {'connected': False, 'error': str(e)}

    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        if total_requests == 0:
            return 0.0
        return (self.cache_stats['hits'] / total_requests) * 100

    async def cleanup_expired_keys(self):
        """Clean up expired keys in memory cache"""
        if not self.redis:  # Only for memory cache
            current_time = time.time()
            expired_keys = []

            for key, expiry_time in self._memory_cache_expiry.items():
                if current_time > expiry_time:
                    expired_keys.append(key)

            for key in expired_keys:
                if key in self._memory_cache:
                    del self._memory_cache[key]
                if key in self._memory_cache_expiry:
                    del self._memory_cache_expiry[key]

            if expired_keys:
                logger.debug(f"🗑️ Cleaned up {len(expired_keys)} cache keys")

    async def health_check(self) -> Dict[str, Any]:
        """Perform cache health check"""
        try:
            if self.redis and self.is_connected:
                # Test Redis connection
                start_time = time.time()
                await self.redis.ping()
                response_time = (time.time() - start_time) * 1000  # ms

                return {
                    'healthy': True,
                    'type': 'redis',
                    'response_time_ms': round(response_time, 2),
                    'connected': True
                }
            else:
                return {
                    'healthy': True,
                    'type': 'memory',
                    'cached_keys': len(self._memory_cache),
                    'connected': False
                }

        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'connected': False
            }

    async def close(self):
        """Close cache connections"""
        try:
            if self.redis:
                await self.redis.close()

            if self.connection_pool:
                await self.connection_pool.disconnect()

            self.is_connected = False
            logger.info("🔌 Cache manager disconnected")

        except Exception as e:
            logger.error(f"❌ Error closing cache connections: {e}")