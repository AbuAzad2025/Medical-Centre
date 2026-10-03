"""
Trace ID middleware tests.
Verifies that X-Request-ID header is injected into g.trace_id and returned in response headers.
"""

from __future__ import annotations

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
        from config import TraceIdFilter

        caplog.set_level(logging.INFO)

        # create_app() silences logging for the testing config -- both the global
        # switch and the application logger -- and pytest's logging plugin takes
        # over the root handlers, so the filter that get_logging_config() installs
        # never runs and no record is ever stamped. The test could therefore only
        # pass by accident, if an earlier test happened to switch logging back on.
        # Re-enable it and put the filter on the logger, where it runs ahead of
        # every handler, then put everything back.
        app_logger = app.logger
        trace_filter = TraceIdFilter()
        previous_manager_disable = logging.root.manager.disable
        previous_logger_disabled = app_logger.disabled
        logging.disable(logging.NOTSET)
        app_logger.disabled = False
        app_logger.addFilter(trace_filter)
        try:
            client.get('/test/log-trace', headers={'X-Request-ID': 'log-trace-456'})

            # Check that log records have trace_id
            log_records = [r for r in caplog.records if 'Test log message' in r.message]
        finally:
            app_logger.removeFilter(trace_filter)
            logging.disable(previous_manager_disable)
            app_logger.disabled = previous_logger_disabled
        assert len(log_records) > 0
        assert hasattr(log_records[0], 'trace_id'), (
            f'record carries no trace_id: {log_records[0].__dict__}'
        )
        assert log_records[0].trace_id == 'log-trace-456', f'trace_id={log_records[0].trace_id!r}'

    def test_trace_id_unique_per_request(self, client):
        """Each request gets a unique trace ID when not provided."""
        resp1 = client.get('/')
        resp2 = client.get('/')
        assert resp1.headers.get('X-Request-ID') != resp2.headers.get('X-Request-ID')
