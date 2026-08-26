"""
Rate limiter with Redis backend for production, in-memory fallback for development.
Supports sliding window algorithm with Redis sorted sets.
"""

import logging
import os
import threading
import time
from functools import wraps

from flask import current_app, jsonify, request

logger = logging.getLogger(__name__)

# In-memory fallback store (thread-safe)
_shared_store: dict = {}
_store_lock = threading.RLock()
_last_cleanup = time.time()

# Redis client with connection pool
_redis_pool = None
_pool_lock = threading.Lock()


def _get_redis_pool() -> object | None:
    """Get or create Redis connection pool."""
    global _redis_pool

    if _redis_pool is not None:
        return _redis_pool

    with _pool_lock:
        if _redis_pool is not None:
            return _redis_pool

        redis_url = (
            os.getenv('REDIS_URL') or current_app.config.get('REDIS_URL') if current_app else None
        )
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
            logger.info('Rate limiter: Redis connection pool created')
            return _redis_pool
        except Exception as e:
            logger.warning(
                f'Rate limiter: Redis pool creation failed, using in-memory fallback: {e}'
            )
            return None


def _get_redis() -> object | None:
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
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < 60:
        return
    _last_cleanup = now
    cutoff = now - window_seconds
    with _store_lock:
        expired = []
        for k, v in list(_shared_store.items()):
            if not v:
                expired.append(k)
                continue
            filtered = [t for t in v if t > cutoff]
            if not filtered:
                expired.append(k)
            elif len(filtered) != len(v):
                _shared_store[k] = filtered
        for k in expired:
            _shared_store.pop(k, None)


class RateLimiter:
    """Sliding-window rate limiter with Redis backend, in-memory fallback."""

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        namespace: str = 'rl',
        use_redis: bool = True,
    ):
        self.max_requests = max_requests
        self.window = window_seconds
        self.namespace = namespace
        self.use_redis = use_redis
        self._redis = _get_redis() if use_redis else None
        self._fallback_count = 0

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window
        full_key = f'{self.namespace}:{key}'
        if self.use_redis and self._redis:
            try:
                import uuid

                pipe = self._redis.pipeline()
                pipe.zremrangebyscore(full_key, 0, window_start)
                pipe.zcard(full_key)
                results = pipe.execute()
                current_count = results[1]
                if current_count >= self.max_requests:
                    return False
                member = f'{now}:{uuid.uuid4().hex}'
                pipe2 = self._redis.pipeline()
                pipe2.zadd(full_key, {member: now})
                pipe2.expire(full_key, self.window + 1)
                pipe2.execute()
                return True
            except Exception as e:
                logger.warning(f'Rate limiter Redis error, falling back to memory: {e}')
                self._redis = None
                self._fallback_count += 1
                if self._fallback_count > 5:
                    logger.exception('Rate limiter: Too many Redis failures, disabling Redis')
                    self.use_redis = False

        # In-memory fallback (thread-safe)
        with _store_lock:
            _cleanup_expired(self.window)
            timestamps = _shared_store.get(full_key, [])
            timestamps = [t for t in timestamps if t > window_start]
            if len(timestamps) >= self.max_requests:
                _shared_store[full_key] = timestamps
                return False
            timestamps.append(now)
            _shared_store[full_key] = timestamps
            return True

    def clear(self):
        """Clear all rate limit data for this namespace."""
        if self.use_redis and self._redis:
            try:
                pattern = f'{self.namespace}:*'
                for key in self._redis.scan_iter(match=pattern):
                    self._redis.delete(key)
            except Exception:
                pass
        with _store_lock:
            keys_to_delete = [k for k in _shared_store if k.startswith(f'{self.namespace}:')]
            for k in keys_to_delete:
                del _shared_store[k]


def rate_limit(
    max_requests: int = 60,
    window_seconds: int = 60,
    namespace: str = 'rl',
    use_redis: bool = True,
    methods: tuple = ('POST',),
):
    """Decorator to rate-limit a route by IP + endpoint.

    Only requests whose method is in ``methods`` are counted. By default
    only POST is limited — fetching forms via GET must stay unrestricted
    so legitimate users behind shared IPs (clinic NAT) can load pages,
    while brute-force attempts (which are always POSTs) remain throttled.
    """

    limiter = RateLimiter(
        max_requests=max_requests,
        window_seconds=window_seconds,
        namespace=namespace,
        use_redis=use_redis,
    )

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Skip rate limiting in testing mode — sequential tests exceed
            # auth rate limits causing false failures.  Production unaffected.
            if current_app.config.get('TESTING', False):
                return f(*args, **kwargs)
            if request.method not in methods:
                return f(*args, **kwargs)
            key = f'{request.remote_addr}:{request.endpoint}'
            if not limiter.is_allowed(key):
                return jsonify(
                    {
                        'success': False,
                        'message': 'Too many requests. Please try again later.',
                        'retry_after': window_seconds,
                    }
                ), 429
            return f(*args, **kwargs)

        return wrapper

    return decorator


# Convenience function for programmatic rate limiting
def check_rate_limit(
    key: str, max_requests: int = 100, window_seconds: int = 60, namespace: str = 'rl'
) -> bool:
    """Check rate limit programmatically without decorator."""
    limiter = RateLimiter(
        max_requests=max_requests, window_seconds=window_seconds, namespace=namespace
    )
    return limiter.is_allowed(key)


# ═══════════════════════════════════════════════════════════════
# IdempotencyLock – distributed lock for payment/webhook races
# ═══════════════════════════════════════════════════════════════
_idempotency_locks: dict = {}
_idempotency_lock_lock = threading.RLock()


def _cleanup_idempotency_locks(timeout_seconds: int = 60):
    now = time.time()
    expired = [k for k, v in _idempotency_locks.items() if now - v > timeout_seconds]
    for k in expired:
        del _idempotency_locks[k]


class IdempotencyLock:
    """Distributed idempotency lock using Redis SET NX or in-memory fallback.

    Ensures only one concurrent request can process a given idempotency key
    at a time, preventing phantom-insert races.
    """

    def __init__(self, namespace: str = 'idemp', timeout_seconds: int = 30):
        self.namespace = namespace
        self.timeout = timeout_seconds
        self._redis = _get_redis()

    def acquire(self, key: str) -> bool:
        full_key = f'{self.namespace}:{key}'
        now = time.time()

        if self._redis:
            try:
                acquired = self._redis.set(full_key, str(now), nx=True, ex=self.timeout)
                return bool(acquired)
            except Exception as e:
                logger.warning(f'Idempotency lock Redis error, falling back to memory: {e}')
                self._redis = None

        with _idempotency_lock_lock:
            _cleanup_idempotency_locks(self.timeout)
            if full_key in _idempotency_locks:
                lock_time = _idempotency_locks[full_key]
                if now - lock_time < self.timeout:
                    return False
            _idempotency_locks[full_key] = now
            return True

    def release(self, key: str) -> None:
        full_key = f'{self.namespace}:{key}'
        if self._redis:
            try:
                self._redis.delete(full_key)
                return
            except Exception:
                pass
        with _idempotency_lock_lock:
            _idempotency_locks.pop(full_key, None)

    def clear_all(self) -> None:
        """Clear every in-memory lock for this namespace (test helper)."""
        prefix = f'{self.namespace}:'
        with _idempotency_lock_lock:
            for k in list(_idempotency_locks.keys()):
                if k.startswith(prefix):
                    del _idempotency_locks[k]
        if self._redis:
            try:
                for k in self._redis.scan_iter(match=f'{prefix}*'):
                    self._redis.delete(k)
            except Exception:
                pass
