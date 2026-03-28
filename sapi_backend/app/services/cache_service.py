import json
import logging
from typing import Any, Optional

import redis

from app.core.config import settings


logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    """Returns a shared Redis client; returns None if Redis is unavailable."""
    global _redis_client
    if _redis_client is None:
        try:
            client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            client.ping()
            _redis_client = client
        except Exception as exc:
            logger.warning(f"Redis unavailable, cache disabled: {exc}")
            return None
    return _redis_client


class CacheService:
    """Simple Redis-backed cache with JSON serialization.

    All operations degrade gracefully when Redis is unavailable so the
    application keeps working without cache (cache-aside pattern).
    """

    DEFAULT_TTL = 300  # 5 minutes

    def get(self, key: str) -> Optional[Any]:
        client = _get_redis()
        if not client:
            return None
        try:
            value = client.get(key)
            return json.loads(value) if value is not None else None
        except Exception as exc:
            logger.warning(f"Cache GET error for '{key}': {exc}")
            return None

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
        client = _get_redis()
        if not client:
            return
        try:
            client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning(f"Cache SET error for '{key}': {exc}")

    def delete(self, key: str) -> None:
        client = _get_redis()
        if not client:
            return
        try:
            client.delete(key)
        except Exception as exc:
            logger.warning(f"Cache DELETE error for '{key}': {exc}")

    def delete_pattern(self, pattern: str) -> None:
        """Deletes all keys matching a glob pattern (e.g. 'document_types:*')."""
        client = _get_redis()
        if not client:
            return
        try:
            keys = client.keys(pattern)
            if keys:
                client.delete(*keys)
        except Exception as exc:
            logger.warning(f"Cache DELETE PATTERN error for '{pattern}': {exc}")


cache_service = CacheService()
