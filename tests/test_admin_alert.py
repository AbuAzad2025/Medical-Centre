"""
Admin Alert Hook tests.
Verifies that critical errors trigger the alert sink with trace_id and tenant_id.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy import select

from app.extensions import db


def _reset_sinks():
    from app_factory import _ALERT_SINKS

    _ALERT_SINKS.clear()


def _get_handler(app: Flask, key):
    """Retrieve a registered error handler callable.

    error_handler_spec[None] is a mapping of bucket -> {exc_class: handler}.
    Class-based handlers live under bucket None; status-code handlers under
    the numeric code bucket.
    """
    spec = app.error_handler_spec.get(None)
    if not spec:
        return None
    if not isinstance(key, int):
        bucket = spec.get(None)
        if isinstance(bucket, dict):
            sub = bucket.get(key)
            if isinstance(sub, dict):
                return next(iter(sub.values()))
    sub = spec.get(key)
    if isinstance(sub, dict):
        return next(iter(sub.values()))
    return sub


class TestAdminAlertHook:
    """Test admin alert hook fires on critical errors."""

    def test_alert_sink_registered(self, app):
        """Alert sink can be registered and called."""
        _reset_sinks()
        from app_factory import _alert_admin, register_alert_sink

        mock_sink = Mock()
        register_alert_sink(mock_sink)

        with app.test_request_context('/test'):
            from flask import g

            g.trace_id = 'alert-test-123'
            from app.core.tenant.models import Tenant
            from app.extensions import db
            from tests.tenant_context import bind_tenant_on_g

            tenant = db.session.execute(select(Tenant)).scalar()
            if tenant:
                bind_tenant_on_g(tenant, db_session=db.session)

            _alert_admin('CRITICAL', 'Test alert', extra='data')

        mock_sink.assert_called_once()
        call_args = mock_sink.call_args
        assert call_args[0][0] == 'CRITICAL'
        ctx = call_args[0][1]
        assert ctx['message'] == 'Test alert'
        assert ctx['extra'] == 'data'
        assert ctx['trace_id'] == 'alert-test-123'

    def test_500_triggers_alert(self, app):
        """500 error handler triggers admin alert."""
        _reset_sinks()
        from app_factory import register_alert_sink

        mock_sink = Mock()
        register_alert_sink(mock_sink)

        handler = _get_handler(app, 500)
        resp = app.make_response(handler(RuntimeError('Simulated 500')))

        assert resp.status_code == 500
        mock_sink.assert_called()
        call_args = mock_sink.call_args
        assert call_args[0][0] == 'CRITICAL'
        assert call_args[0][1]['message'] == 'Internal server error'

    def test_tenant_isolation_error_alerts(self, client):
        """TenantIsolationError handler triggers alert via pre-registered route."""
        _reset_sinks()
        from app_factory import register_alert_sink

        mock_sink = Mock()
        register_alert_sink(mock_sink)

        resp = client.get('/test/tenant-iso-error', headers={'X-Request-ID': 'tenant-iso-1'})

        assert resp.status_code == 403
        mock_sink.assert_called()
        call_args = mock_sink.call_args
        assert call_args[0][0] == 'CRITICAL'

    def test_alert_includes_tenant_id(self, app):
        """Alert context includes tenant_id when available."""
        _reset_sinks()
        from app.core.tenant.models import Tenant
        from app_factory import _alert_admin, register_alert_sink
        from tests.tenant_context import bind_tenant_on_g

        mock_sink = Mock()
        register_alert_sink(mock_sink)

        tenant = db.session.execute(select(Tenant)).scalar()
        if not tenant:
            pytest.skip('no tenant seeded')

        with app.test_request_context('/test', headers={'X-Request-ID': 'ctx-test-456'}):
            bind_tenant_on_g(tenant, db_session=db.session)
            _alert_admin('WARNING', 'Test with tenant')

        mock_sink.assert_called()
        call_args = mock_sink.call_args
        ctx = call_args[0][1]
        assert ctx['tenant_id'] == tenant.id
