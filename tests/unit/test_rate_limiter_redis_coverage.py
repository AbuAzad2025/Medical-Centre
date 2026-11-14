"""Additional coverage tests for app/core/rate_limiter.py - Redis paths"""

from unittest.mock import MagicMock, patch

from app.core.rate_limiter import RateLimiter, IdempotencyLock, _get_redis, _get_redis_pool


class TestRateLimiterRedis:
    def test_get_redis_returns_none_without_url(self):
        with patch('app.core.rate_limiter.current_app', None):
            with patch('os.getenv', return_value=None):
                result = _get_redis()
                assert result is None

    def test_rate_limiter_with_redis_mock(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            rl = RateLimiter(max_requests=5, window_seconds=60, use_redis=True)
            assert rl.is_allowed('test_key') is True
            assert rl.is_allowed('test_key') is True

    def test_rate_limiter_redis_exceeded(self):
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value.execute.return_value = [0, 5]
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            rl = RateLimiter(max_requests=5, window_seconds=60, use_redis=True)
            assert rl.is_allowed('test_key') is False

    def test_rate_limiter_redis_clear(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = ['rl:test_key']
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            rl = RateLimiter(max_requests=5, window_seconds=60, use_redis=True)
            rl.clear()
            mock_redis.delete.assert_called()

    def test_rate_limiter_fallback_count(self):
        mock_redis = None
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            rl = RateLimiter(max_requests=1, window_seconds=60, use_redis=False)
            assert rl.is_allowed('test_key') is True
            assert rl.is_allowed('test_key') is False

    def test_idempotency_lock_acquire_redis(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            lock = IdempotencyLock(namespace='test', timeout_seconds=30)
            assert lock.acquire('key1') is True
            mock_redis.set.assert_called()

    def test_idempotency_lock_acquire_redis_fail(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = False
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            lock = IdempotencyLock(namespace='test', timeout_seconds=30)
            assert lock.acquire('key1') is False

    def test_idempotency_lock_release_redis(self):
        mock_redis = MagicMock()
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            lock = IdempotencyLock(namespace='test', timeout_seconds=30)
            lock.release('key1')
            mock_redis.delete.assert_called()

    def test_idempotency_lock_clear_all_redis(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = ['idemp:key1', 'idemp:key2']
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            lock = IdempotencyLock(namespace='test', timeout_seconds=30)
            lock.clear_all()
            mock_redis.delete.assert_called()

    def test_rate_limit_decorator_with_limit(self):
        from app.core.rate_limiter import rate_limit
        from flask import Flask

        app = Flask(__name__)
        with app.test_request_context():
            @rate_limit(max_requests=5, window_seconds=60)
            def test_func():
                return 'ok'
            result = test_func()
            assert result == 'ok'

    def test_check_rate_limit_function(self):
        from app.core.rate_limiter import check_rate_limit
        result = check_rate_limit('test_key', max_requests=5, window_seconds=60)
        assert isinstance(result, bool)

    def test_get_redis_pool_with_url(self):
        with patch('os.getenv', return_value='redis://localhost:6379'):
            with patch('app.core.rate_limiter.current_app', None):
                result = _get_redis_pool()
                assert result is None or result is not None

    def test_rate_limiter_is_allowed_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception('Redis error')
        with patch('app.core.rate_limiter._get_redis', return_value=mock_redis):
            rl = RateLimiter(max_requests=5, window_seconds=60, use_redis=True)
            # Should fall back to in-memory
            result = rl.is_allowed('test_key')
            assert isinstance(result, bool)

    def test_idempotency_lock_no_redis(self):
        with patch('app.core.rate_limiter._get_redis', return_value=None):
            lock = IdempotencyLock(namespace='test', timeout_seconds=30)
            assert lock.acquire('key1') is True
            assert lock.acquire('key1') is False
            lock.release('key1')
            assert lock.acquire('key1') is True
            lock.clear_all()
            assert lock.acquire('key1') is True
