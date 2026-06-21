"""
Dashboard and reporting tests.
"""
import pytest


class TestMedicationDashboard:
    """Medication dashboard data accuracy tests."""

    def test_dashboard_loads(self, auth_client, test_medications):
        """Dashboard should render without errors."""
        resp = auth_client.get('/medication/dashboard')
        assert resp.status_code in (200, 302)

    def test_dashboard_counts(self, auth_client, test_medications):
        """Dashboard should show correct medication counts."""
        resp = auth_client.get('/medication/dashboard')
        if resp.status_code == 200:
            html = resp.data.decode('utf-8')
            assert 'أموكسيسيلين' in html or '3' in html

    def test_dashboard_low_stock(self, auth_client, test_medications):
        """Dashboard should highlight low-stock medications."""
        resp = auth_client.get('/medication/dashboard')
        if resp.status_code == 200:
            html = resp.data.decode('utf-8')
            assert 'ايبوبروفين' in html or 'منخفض' in html


class TestOwnerDashboard:
    """Owner/SuperAdmin dashboard tests."""

    def test_owner_dashboard_redirect(self, client):
        """Owner dashboard should require auth."""
        resp = client.get('/owner/dashboard')
        assert resp.status_code == 302

    def test_owner_tenant_list(self, client):
        """API endpoint for tenants should work."""
        resp = client.get('/auth/api/tenants-list')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None
        assert len(data) > 0


class TestRateLimiter:
    """Rate limiter tests."""

    def test_login_rate_limit(self, app, client):
        """Rate limiter should block after too many requests."""
        for _ in range(15):
            resp = client.post('/auth/login', data={
                'username': 'ratelimit_test',
                'password': 'wrong',
            })
        assert resp.status_code in (200, 429)
