"""
Redis cache wrapper for GitHub API responses.
Caches commit lists to avoid redundant API calls.
"""
import json
import logging
from typing import Any, Dict, List, Optional

import redis

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour
CACHE_TTL_SECONDS = 3600

# Cache key prefix for GitHub commits
CACHE_PREFIX = "github:commits"


class CacheError(Exception):
    """Raised when Redis operations fail."""
    pass


class RedisCache:
    """
    Thread-safe Redis cache for API responses.
    Falls back gracefully if Redis is unavailable.
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False

    @property
    def client(self) -> Optional[redis.Redis]:
        """Lazy-loaded Redis client. Returns None if connection fails."""
        if self._client is None and not self._connected:
            try:
                self._client = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                )
                # Test connection
                self._client.ping()
                self._connected = True
            except redis.ConnectionError as e:
                logger.warning(f"Redis connection failed, caching disabled: {e}")
                self._connected = False
                self._client = None
            except redis.RedisError as e:
                logger.warning(f"Redis error, caching disabled: {e}")
                self._connected = False
                self._client = None
        return self._client

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache.
        Returns None on cache miss or connection failure.
        """
        try:
            if not self.client:
                return None
            data = self.client.get(key)
            if data is None:
                return None
            return json.loads(data)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get failed for key '{key}': {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> bool:
        """
        Store a value in cache with TTL.
        Returns False on failure.
        """
        try:
            if not self.client:
                return False
            serialized = json.dumps(value)
            self.client.setex(key, ttl, serialized)
            return True
        except (redis.RedisError, TypeError) as e:
            logger.warning(f"Cache set failed for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        """Remove a key from cache."""
        try:
            if not self.client:
                return False
            self.client.delete(key)
            return True
        except redis.RedisError as e:
            logger.warning(f"Cache delete failed for key '{key}': {e}")
            return False

    def build_commits_cache_key(self, repo_full_name: str, since_timestamp: Optional[str] = None) -> str:
        """
        Build a consistent cache key for commit lists.

        Args:
            repo_full_name: owner/repo
            since_timestamp: ISO format timestamp or None for full sync

        Returns:
            Cache key string
        """
        ts = since_timestamp or "all"
        return f"{CACHE_PREFIX}:{repo_full_name}:{ts}"


# Singleton instance
cache = RedisCache()
