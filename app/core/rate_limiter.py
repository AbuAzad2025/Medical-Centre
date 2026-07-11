"""
Rate limiter with Redis backend for production, in-memory fallback for development.
Supports sliding window algorithm with Redis sorted sets.
"""
import time
import logging
import os
import threading
from functools import wraps
from typing import Optional
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)

# In-memory fallback store (thread-safe)
_shared_store: dict = {}
_store_lock = threading.RLock()
_last_cleanup = time.time()

# Redis client with connection pool
_redis_pool = None
_pool_lock = threading.Lock()


def _get_redis_pool() -> Optional[object]:
    """Get or create Redis connection pool."""
    global _redis_pool
    
    if _redis_pool is not None:
        return _redis_pool
    
    with _pool_lock:
        if _redis_pool is not None:
            return _redis_pool
        
        redis_url = os.getenv('REDIS_URL') or current_app.config.get('REDIS_URL') if current_app else None
        if not redis_url:
            return None
        
        try:
            import redis
            _redis_pool = redis.ConnectionPool.from_url(
                redis_url,
                decode_responses=True,
                max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', '20')),
                socket_timeout=float(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
                socket_connect_timeout=float(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5')),
                retry_on_timeout=True,
                health_check_interval=30,
            )
            # Test connection
            test_client = redis.Redis(connection_pool=_redis_pool)
            test_client.ping()
            logger.info("Rate limiter: Redis connection pool created")
            return _redis_pool
        except Exception as e:
            logger.warning(f"Rate limiter: Redis pool creation failed, using in-memory fallback: {e}")
            return None


def _get_redis() -> Optional[object]:
    """Get Redis client from pool."""
    pool = _get_redis_pool()
    if pool is None:
        return None
    try:
        import redis
        return redis.Redis(connection_pool=pool)
    except Exception:
        return None


def _cleanup_expired(window_seconds: int = 60):
    """Periodically purge expired entries from in-memory store."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < 60:
        return
    _last_cleanup = now
    cutoff = now - window_seconds
    with _store_lock:
        expired = [k for k, v in _shared_store.items() if v and v[-1] < cutoff]
        for k in expired:
            del _shared_store[k]


class RateLimiter:
    """Sliding-window rate limiter with Redis backend, in-memory fallback."""
    
    def __init__(
        self, 
        max_requests: int = 100, 
        window_seconds: int = 60, 
        namespace: str = "rl",
        use_redis: bool = True
    ):
        self.max_requests = max_requests
        self.window = window_seconds
        self.namespace = namespace
        self.use_redis = use_redis
        self._redis = _get_redis() if use_redis else None
        self._fallback_count = 0

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()
        window_start = now - self.window
        full_key = f"{self.namespace}:{key}"

        # Try Redis first
        if self.use_redis and self._redis:
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
                logger.warning(f"Rate limiter Redis error, falling back to memory: {e}")
                self._redis = None
                self._fallback_count += 1
                if self._fallback_count > 5:
                    logger.error("Rate limiter: Too many Redis failures, disabling Redis")
                    self.use_redis = False

        # In-memory fallback (thread-safe)
        with _store_lock:
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
        """Clear all rate limit data for this namespace."""
        if self.use_redis and self._redis:
            try:
                pattern = f"{self.namespace}:*"
                for key in self._redis.scan_iter(match=pattern):
                    self._redis.delete(key)
            except Exception:
                pass
        with _store_lock:
            keys_to_delete = [k for k in _shared_store if k.startswith(self.namespace)]
            for k in keys_to_delete:
                del _shared_store[k]


def rate_limit(max_requests: int = 60, window_seconds: int = 60, namespace: str = "rl", use_redis: bool = True):
    """Decorator to rate-limit a route by IP + endpoint."""
    limiter = RateLimiter(
        max_requests=max_requests, 
        window_seconds=window_seconds, 
        namespace=namespace,
        use_redis=use_redis
    )
    
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = f"{request.remote_addr}:{request.endpoint}"
            if not limiter.is_allowed(key):
                return jsonify({
                    'success': False, 
                    'message': 'Too many requests. Please try again later.',
                    'retry_after': window_seconds
                }), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator


# Convenience function for programmatic rate limiting
def check_rate_limit(key: str, max_requests: int = 100, window_seconds: int = 60, namespace: str = "rl") -> bool:
    """Check rate limit programmatically without decorator."""
    limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds, namespace=namespace)
    return limiter.is_allowed(key)