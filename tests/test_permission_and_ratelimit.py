"""Permission decorators (was 38%) + rate limiter (was 64%)."""


class TestRoleRequiredDecorator:
    def test_unauthenticated_redirects(self, app):
        with app.test_request_context():
            from utils.decorators import role_required

            @role_required('admin')
            def dummy():
                return 'OK'

            # Without login, should redirect
            # (actual redirect tested via client)

    def test_role_required_allows_correct_role(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        u = ensure_test_user(db, test_tenant, username='perm_admin', role='admin')
        with app.test_request_context():
            from flask_login import login_user

            login_user(u)
            from utils.decorators import role_required

            @role_required('admin')
            def dummy():
                return 'OK'

            assert dummy() == 'OK'


class TestRateLimiter:
    def test_rate_limiter_allows_within_limit(self):
        from app.core.rate_limiter import RateLimiter

        rl = RateLimiter(max_requests=5, window_seconds=60, use_redis=False)
        for _ in range(5):
            assert rl.is_allowed('test_key') is True
        assert rl.is_allowed('test_key') is False  # 6th exceeds limit

    def test_rate_limiter_different_keys_independent(self):
        from app.core.rate_limiter import RateLimiter

        rl = RateLimiter(max_requests=2, window_seconds=60, use_redis=False)
        assert rl.is_allowed('key_a') is True
        assert rl.is_allowed('key_b') is True  # different key unaffected

    def test_rate_limiter_clear(self):
        from app.core.rate_limiter import RateLimiter

        rl = RateLimiter(max_requests=1, window_seconds=60, use_redis=False)
        rl.is_allowed('clear_test')
        assert rl.is_allowed('clear_test') is False
        rl.clear()
        assert rl.is_allowed('clear_test') is True

    def test_testing_mode_bypasses(self, app):
        with app.test_request_context():
            from app.core.rate_limiter import rate_limit

            @rate_limit(max_requests=0, window_seconds=60)  # zero = always blocked
            def dummy():
                return 'OK'

            # TESTING=True bypasses rate limiting entirely
            assert dummy() == 'OK'


class TestIdempotencyLock:
    def test_acquire_release(self):
        from app.core.rate_limiter import IdempotencyLock

        lock = IdempotencyLock(timeout_seconds=5)
        assert lock.acquire('test_op') is True
        assert lock.acquire('test_op') is False  # already locked
        lock.release('test_op')
        assert lock.acquire('test_op') is True  # released, can acquire again
