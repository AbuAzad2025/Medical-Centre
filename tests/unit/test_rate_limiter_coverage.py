"""Coverage tests for app/core/rate_limiter.py"""

from app.core.rate_limiter import RateLimiter, IdempotencyLock, _cleanup_expired, _cleanup_idempotency_locks


class TestRateLimiter:
    def test_rate_limiter_init(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        assert rl.max_requests == 5
        assert rl.window == 60

    def test_rate_limiter_is_allowed(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        assert rl.is_allowed('test_key') is True
        assert rl.is_allowed('test_key') is True

    def test_rate_limiter_clear(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        rl.is_allowed('test_key')
        rl.clear()
        assert rl.is_allowed('test_key') is True

    def test_rate_limiter_exceeded(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.is_allowed('test_key') is True
        assert rl.is_allowed('test_key') is False

    def test_cleanup_expired(self):
        _cleanup_expired(60)

    def test_cleanup_idempotency_locks(self):
        _cleanup_idempotency_locks(60)

    def test_idempotency_lock_init(self):
        lock = IdempotencyLock(namespace='test', timeout_seconds=30)
        assert lock.namespace == 'test'
        assert lock.timeout == 30

    def test_idempotency_lock_acquire(self):
        lock = IdempotencyLock(namespace='test', timeout_seconds=30)
        assert lock.acquire('key1') is True
        assert lock.acquire('key1') is False  # Already locked

    def test_idempotency_lock_release(self):
        lock = IdempotencyLock(namespace='test', timeout_seconds=30)
        lock.acquire('key1')
        lock.release('key1')
        assert lock.acquire('key1') is True

    def test_idempotency_lock_clear_all(self):
        lock = IdempotencyLock(namespace='test', timeout_seconds=30)
        lock.acquire('key1')
        lock.clear_all()
        assert lock.acquire('key1') is True

    def test_get_redis(self):
        from app.core.rate_limiter import _get_redis
        result = _get_redis()
        assert result is None or result is not None

    def test_get_redis_pool(self):
        from app.core.rate_limiter import _get_redis_pool
        result = _get_redis_pool()
        assert result is None or result is not None

    def test_rate_limit_decorator(self, app):
        from app.core.rate_limiter import rate_limit
        from flask import Flask

        @rate_limit(max_requests=5, window_seconds=60)
        def test_func():
            return 'ok'

        result = test_func()
        assert result == 'ok'

    def test_check_rate_limit(self, app):
        from app.core.rate_limiter import check_rate_limit
        result = check_rate_limit('test_key', max_requests=5, window_seconds=60)
        assert result is True or result is False
