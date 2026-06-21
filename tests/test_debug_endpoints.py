"""Tests for P0E-001: debug/performance endpoint containment."""

import pytest


class TestDebugEndpointsDisabled:
    """By default, DISABLE_DEBUG_ENDPOINTS is True in testing config."""

    def test___routes_returns_404_when_disabled(self, app, client):
        resp = client.get("/__routes")
        assert resp.status_code == 404

    def test___perf_finance_returns_404_when_disabled(self, app, client):
        resp = client.get("/__perf/finance")
        assert resp.status_code == 404


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
