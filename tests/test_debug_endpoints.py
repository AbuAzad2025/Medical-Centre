"""Tests for P4-005: retired debug endpoints; operational health probe retained."""

import pytest


class TestRetiredDebugEndpoints:
    """Development-only routes removed from production surface."""

    @pytest.mark.parametrize("path", ["/__ping", "/__routes", "/__perf/finance", "/auth/__ping"])
    def test_retired_endpoints_return_404(self, app, client, path):
        resp = client.get(path)
        assert resp.status_code == 404


class TestHealthEndpoint:
    """/__health is an operational probe and is always available."""

    def test___health_returns_200(self, app, client):
        resp = client.get("/__health")
        assert resp.status_code == 200
