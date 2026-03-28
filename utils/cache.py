import redis
import os

_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def get_cached(key: str):
    """Return cached value or None if not found / Redis unavailable."""
    try:
        return get_redis().get(key)
    except Exception:
        return None


def set_cache(key: str, value: str, timeout: int = 300):
    """Store value in Redis with TTL in seconds."""
    try:
        get_redis().setex(key, timeout, value)
    except Exception:
        pass


def delete_cache(key: str):
    """Delete a specific cache key."""
    try:
        get_redis().delete(key)
    except Exception:
        pass


def invalidate_pattern(pattern: str):
    """Delete all keys matching a glob pattern."""
    try:
        r = get_redis()
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass
