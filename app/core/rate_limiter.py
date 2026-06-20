"""
Rate limiter with Redis backend for production, in-memory fallback for development.
"""
import time
import logging
import os
from functools import wraps
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)

# In-memory fallback store
_shared_store = {}
_last_cleanup = time.time()

# Redis client (lazy init)
_redis_client = None


def _get_redis():
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    
    redis_url = os.getenv('REDIS_URL') or current_app.config.get('REDIS_URL') if current_app else None
    if not redis_url:
        return None
    
    try:
        import redis
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Rate limiter: Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"Rate limiter: Redis unavailable, using in-memory fallback: {e}")
        return None


def _cleanup_expired(window_seconds: int = 60):
    """Periodically purge expired entries from in-memory store."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < 60:
        return
    _last_cleanup = now
    cutoff = now - window_seconds
    expired = [k for k, v in _shared_store.items() if v and v[-1] < cutoff]
    for k in expired:
        del _shared_store[k]


class RateLimiter:
    """Sliding-window rate limiter with Redis backend, in-memory fallback."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60, namespace: str = "rl"):
        self.max_requests = max_requests
        self.window = window_seconds
        self.namespace = namespace
        self._redis = _get_redis()

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window
        full_key = f"{self.namespace}:{key}"

        if self._redis:
            try:
                # Use Redis sorted set for sliding window
                pipe = self._redis.pipeline()
                pipe.zremrangebyscore(full_key, 0, window_start)
                pipe.zcard(full_key)
                pipe.zadd(full_key, {str(now): now})
                pipe.expire(full_key, self.window + 1)
                results = pipe.execute()
                current_count = results[1]
                return current_count < self.max_requests
            except Exception as e:
                logger.warning(f"Rate limiter Redis error, falling back: {e}")
                self._redis = None  # Force fallback on next call

        # In-memory fallback
        _cleanup_expired(self.window)
        timestamps = _shared_store.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= self.max_requests:
            _shared_store[key] = timestamps
            return False
        timestamps.append(now)
        _shared_store[key] = timestamps
        return True

    def clear(self):
        if self._redis:
            try:
                pattern = f"{self.namespace}:*"
                for key in self._redis.scan_iter(match=pattern):
                    self._redis.delete(key)
            except Exception:
                pass
        _shared_store.clear()


def rate_limit(max_requests: int = 60, window_seconds: int = 60, namespace: str = "rl"):
    """Decorator to rate-limit a route by IP + endpoint."""
    limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds, namespace=namespace)
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = f"{request.remote_addr}:{request.endpoint}"
            if not limiter.is_allowed(key):
                return jsonify({'success': False, 'message': 'Too many requests'}), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator