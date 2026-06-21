"""Tests for P0E-001: debug/performance endpoint containment."""

# Blueprint monkey-patch: Flask 3.1+ does not accept the codebase-wide
# `guard_module` kwarg. Strip it before any route imports trigger it.
import flask as _flask
_orig_bp = _flask.Blueprint
class _PatchedBP(_orig_bp):
    def __init__(self, name, import_name, **kwargs):
        kwargs.pop('guard_module', None)
        super().__init__(name, import_name, **kwargs)
_flask.Blueprint = _PatchedBP

import pytest


class TestProductionLock:
    """ProductionConfig must ignore environment overrides."""

    def test_production_config_locked(self):
        from config import ProductionConfig
        assert ProductionConfig.DISABLE_DEBUG_ENDPOINTS is True

    def test_env_var_cannot_enable_in_production(self, monkeypatch):
        monkeypatch.setenv('DISABLE_DEBUG_ENDPOINTS', 'false')
        import importlib
        import config
        cfg = importlib.reload(config)
        assert cfg.ProductionConfig.DISABLE_DEBUG_ENDPOINTS is True


class TestDebugEndpointsDisabled:
    """By default, DISABLE_DEBUG_ENDPOINTS is True in testing config."""

    def test___routes_anonymous_returns_404_when_disabled(self, app, client):
        resp = client.get("/__routes")
        assert resp.status_code == 404

    def test___routes_authenticated_returns_404_when_disabled(self, app, auth_client):
        resp = auth_client.get("/__routes")
        assert resp.status_code == 404

    def test___perf_finance_anonymous_returns_404_when_disabled(self, app, client):
        resp = client.get("/__perf/finance")
        assert resp.status_code == 404

    def test___perf_finance_authenticated_returns_404_when_disabled(self, app, auth_client):
        resp = auth_client.get("/__perf/finance")
        assert resp.status_code == 404

    def test___health_returns_200(self, app, client):
        resp = client.get("/__health")
        assert resp.status_code == 200


class TestDebugEndpointsEnabled:
    """When explicitly enabled, endpoints should work."""

    def test___routes_returns_200_when_enabled(self, app, client):
        app.config["DISABLE_DEBUG_ENDPOINTS"] = False
        resp = client.get("/__routes")
        assert resp.status_code == 200
        assert b"__routes" in resp.data

    def test___perf_finance_returns_200_when_enabled(self, app, client):
        app.config["DISABLE_DEBUG_ENDPOINTS"] = False
        resp = client.get("/__perf/finance?format=json")
        assert resp.status_code == 200
        assert b"overall" in resp.data
