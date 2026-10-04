"""
Global error handler tests for custom exceptions.
Tests that ModuleNotEnabledError, TenantIsolationError, TenantContextError,
PermissionError, and IdempotencyError are properly caught and return correct HTTP responses.
"""

from __future__ import annotations


class TestGlobalErrorHandlers:
    """Test that custom exceptions are handled by global error handlers.

    Every test takes ``rollback_db``. Without it nothing binds a tenant, so
    ``_set_tenant_context`` aborts 403 before the view that raises the exception
    under test is ever called -- and since ``handle_403`` answers API callers with
    JSON, the response looked well formed and carried ``error: forbidden``
    instead. Only the status code and the payload shape were being checked, so
    two of these tests passed while asserting nothing about the handler they name,
    and one failed outright. ``rollback_db`` binds the tenant, which is what lets
    the request reach its view.
    """

    def test_module_not_enabled_error_json(self, app, client, rollback_db):
        """ModuleNotEnabledError on API route returns 403 JSON."""
        resp = client.get('/test/module-error', headers={'Content-Type': 'application/json'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['success'] is False
        assert data['error'] == 'Lab module is disabled'
        assert data['module'] == 'lab'

    def test_module_not_enabled_error_html(self, app, client, rollback_db):
        """ModuleNotEnabledError on HTML route returns 403 with flash."""
        resp = client.get('/test/module-error-html')
        assert resp.status_code == 403

    def test_tenant_isolation_error_json(self, app, client, rollback_db):
        """TenantIsolationError on API route returns 403 JSON."""
        resp = client.get('/test/tenant-iso-error', headers={'Content-Type': 'application/json'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['success'] is False
        assert 'Cross-tenant access blocked' in data['error']

    def test_tenant_context_error_json(self, app, client, rollback_db):
        """TenantContextError on API route returns 403 JSON."""
        resp = client.get('/test/tenant-ctx-error', headers={'Content-Type': 'application/json'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['success'] is False
        assert 'Tenant context required' in data['error']

    def test_permission_error_json(self, app, client, rollback_db):
        """PermissionError on API route returns 403 JSON."""
        resp = client.get('/test/perm-error', headers={'Content-Type': 'application/json'})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['success'] is False
        assert 'Cross-tenant access denied' in data['error']

    def test_idempotency_error_json(self, app, client, rollback_db):
        """IdempotencyError on API route returns 409 JSON."""
        resp = client.get('/test/idempotency-error', headers={'Content-Type': 'application/json'})
        assert resp.status_code == 409
        data = resp.get_json()
        assert data['success'] is False
        assert data['error'] == 'Duplicate request'
        assert data['retry_after'] == 30

    def test_idempotency_error_html(self, app, client, rollback_db):
        """IdempotencyError on HTML route flashes warning and redirects."""
        resp = client.get('/test/idempotency-error-html')
        assert resp.status_code in (302, 409)  # redirect or 409
