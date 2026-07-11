"""
Trace ID middleware tests.
Verifies that X-Request-ID header is injected into g.trace_id and returned in response headers.
"""
from __future__ import annotations

import pytest
from flask import g, jsonify
import logging


class TestTraceIdMiddleware:
    """Test trace ID injection and propagation."""

    def test_trace_id_from_header(self, client):
        """Client-provided X-Request-ID is echoed in response."""
        resp = client.get('/', headers={'X-Request-ID': 'abc123def456'})
        assert resp.headers.get('X-Request-ID') == 'abc123def456'

    def test_trace_id_from_x_correlation_id(self, client):
        """X-Correlation-ID header also works as trace ID source."""
        resp = client.get('/', headers={'X-Correlation-ID': 'corr-789'})
        assert resp.headers.get('X-Request-ID') == 'corr-789'

    def test_trace_id_generated_when_missing(self, client):
        """Auto-generated trace ID when no header provided."""
        resp = client.get('/')
        trace_id = resp.headers.get('X-Request-ID')
        assert trace_id is not None
        assert len(trace_id) == 16  # uuid4().hex[:16]
        # Should be hex characters
        assert all(c in '0123456789abcdef' for c in trace_id)

    def test_trace_id_in_g_during_request(self, app, client):
        """g.trace_id is accessible during request processing."""
        resp = client.get('/test/g-trace', headers={'X-Request-ID': 'test-trace-123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['trace_id'] == 'test-trace-123'

    def test_trace_id_in_logs(self, app, client, caplog):
        """Trace ID appears in log records via TraceIdFilter."""
        import logging
        caplog.set_level(logging.INFO)
        
        client.get('/test/log-trace', headers={'X-Request-ID': 'log-trace-456'})
        
        # Check that log records have trace_id
        log_records = [r for r in caplog.records if 'Test log message' in r.message]
        assert len(log_records) > 0
        assert hasattr(log_records[0], 'trace_id')
        assert log_records[0].trace_id == 'log-trace-456'

    def test_trace_id_unique_per_request(self, client):
        """Each request gets a unique trace ID when not provided."""
        resp1 = client.get('/')
        resp2 = client.get('/')
        assert resp1.headers.get('X-Request-ID') != resp2.headers.get('X-Request-ID')