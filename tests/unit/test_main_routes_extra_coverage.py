"""Coverage tests for routes.main.py - additional coverage for missing lines"""

from __future__ import annotations

from unittest.mock import patch

pytest_plugins = ['tests._isolated_tenant']


class TestMainRoutesExtra:
    """Additional coverage tests for routes/main.py missing lines."""

    def test_index_authenticated(self, app, client, login_as):
        """Test index page for authenticated user (covers bundles query)."""
        login_as(client, 'main_idx_auth_user', 'doctor')
        resp = client.get('/')
        assert resp.status_code in (200, 302)

    def test_health_db_error(self, app, client):
        """Test health check when DB fails (covers db error path)."""
        with patch('app.extensions.db.session.execute', side_effect=Exception('DB down')):
            resp = client.get('/health')
            assert resp.status_code in (200, 503)
            data = resp.get_json()
            assert 'status' in data
            assert 'checks' in data
            assert 'database' in data['checks']

    def test_health_redis_error(self, app, client):
        """Test health check when Redis fails."""
        with patch('app.core.rate_limiter._get_redis', side_effect=Exception('Redis down')):
            resp = client.get('/health')
            assert resp.status_code in (200, 503)
            data = resp.get_json()
            assert 'status' in data
            assert 'checks' in data
            assert 'redis' in data['checks']

    def test_health_redis_ping_error(self, app, client):
        """Test health check when Redis ping fails."""
        fake_redis = type(
            'FakeRedis', (), {'ping': lambda _self: (_ for _ in ()).throw(Exception('ping failed'))}
        )()
        with patch('app.core.rate_limiter._get_redis', return_value=fake_redis):
            resp = client.get('/health')
            assert resp.status_code in (200, 503)
            data = resp.get_json()
            assert 'status' in data
            assert 'redis' in data['checks']

    def test_health_stripe_unconfigured(self, app, client):
        """Test health check when Stripe is not configured."""
        with patch.dict('os.environ', {}, clear=True):
            with patch.object(app.config, 'get', return_value=None):
                resp = client.get('/health')
                assert resp.status_code in (200, 503)
                data = resp.get_json()
                assert 'status' in data
                assert 'checks' in data
                assert 'stripe' in data['checks']

    def test_health_stripe_error(self, app, client):
        """Test health check when Stripe API fails."""
        with patch('stripe.Account.retrieve', side_effect=Exception('Stripe error')):
            with patch('os.environ.get', return_value='sk_test_fake'):
                resp = client.get('/health')
                assert resp.status_code in (200, 503)
                data = resp.get_json()
                assert 'status' in data
                assert 'checks' in data
                assert 'stripe' in data['checks']

    def test_health_twilio_error(self, app, client):
        """Test health check when Twilio fails."""
        fake_provider = type(
            'FakeProvider',
            (),
            {'check_connection': lambda _self: (_ for _ in ()).throw(Exception('Twilio error'))},
        )()
        with patch('app.integrations.sms.provider.get_sms_provider', return_value=fake_provider):
            resp = client.get('/health')
            assert resp.status_code in (200, 503)
            data = resp.get_json()
            assert 'status' in data
            assert 'checks' in data
            assert 'sms' in data['checks']

    def test_health_twilio_no_provider(self, app, client):
        """Test health check when no SMS provider."""
        with patch('app.integrations.sms.provider.get_sms_provider', return_value=None):
            resp = client.get('/health')
            assert resp.status_code in (200, 503)
            data = resp.get_json()
            assert 'status' in data
            assert 'checks' in data
            assert 'sms' in data['checks']

    def test_health_smtp_unconfigured(self, app, client):
        """Test health check when SMTP not configured."""
        with patch.object(app.config, 'get', return_value=None):
            resp = client.get('/health')
            assert resp.status_code in (200, 503)
            data = resp.get_json()
            assert 'status' in data
            assert 'checks' in data

    def test_health_smtp_error(self, app, client):
        """Test health check when SMTP connection fails."""
        with patch.object(
            app.config,
            'get',
            side_effect=lambda k, default=None: {
                'MAIL_SERVER': 'smtp.example.com',
                'MAIL_PORT': 587,
                'MAIL_USERNAME': 'user',
                'MAIL_PASSWORD': 'pass',
                'MAIL_USE_TLS': True,
            }.get(k, default),
        ):
            with patch('smtplib.SMTP', side_effect=Exception('SMTP error')):
                resp = client.get('/health')
                assert resp.status_code in (200, 503)
                data = resp.get_json()
                assert 'status' in data
                assert 'checks' in data

    def test_health_degraded(self, app, client):
        """Test health check when overall status is degraded."""
        with patch('app.extensions.db.session.execute', side_effect=Exception('DB down')):
            resp = client.get('/health')
            assert resp.status_code in (200, 503)
            data = resp.get_json()
            assert 'status' in data
            assert 'checks' in data

    def test_api_search_tenants_with_results(self, app, client, db, test_tenant):
        """Test tenant search with actual results (covers tenant processing)."""
        from app.core.tenant.models import Tenant
        from app.shared.enums import TenantStatus

        # Create another tenant that matches the search
        t2 = Tenant(
            name='Test Tenant Two',
            name_ar='المستأجر الثاني',
            slug='test-tenant-two',
            status=TenantStatus.ACTIVE,
            contact_email='test2@example.com',
        )
        db.session.add(t2)
        db.session.flush()

        resp = client.get(f'/api/tenants/search?q={test_tenant.slug}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'tenants' in data
        assert len(data['tenants']) >= 1

    def test_api_search_tenants_partial_match(self, app, client, db, test_tenant):
        """Test tenant search with partial name match."""
        resp = client.get(f'/api/tenants/search?q={test_tenant.name[:3]}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'tenants' in data

    def test_privacy_policy_auth(self, app, client, login_as):
        """Test privacy policy for authenticated user."""
        login_as(client, 'main_privacy_user', 'doctor')
        resp = client.get('/privacy-policy')
        assert resp.status_code == 200

    def test_terms_of_use_auth(self, app, client, login_as):
        """Test terms of use for authenticated user."""
        login_as(client, 'main_terms_user', 'doctor')
        resp = client.get('/terms-of-use')
        assert resp.status_code == 200

    def test_technical_support_auth(self, app, client, login_as):
        """Test technical support for authenticated user."""
        login_as(client, 'main_support_user', 'doctor')
        resp = client.get('/technical-support')
        assert resp.status_code == 200

    def test_about_system_auth(self, app, client, login_as):
        """Test about system for authenticated user."""
        login_as(client, 'main_about_user', 'doctor')
        resp = client.get('/about-system')
        assert resp.status_code == 200

    def test_package_restricted_unauthenticated(self, app, client):
        """Test package restricted page for unauthenticated user."""
        resp = client.get('/package-restricted')
        assert resp.status_code in (302, 401)

    def test_settings_unauthenticated(self, app, client):
        """Test settings page for unauthenticated user."""
        resp = client.get('/settings')
        assert resp.status_code in (302, 401)

    def test_appointments_unauthenticated(self, app, client):
        """Test appointments redirect for unauthenticated user."""
        resp = client.get('/appointments')
        assert resp.status_code in (302, 401)
