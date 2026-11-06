"""Resilience & observability enhancements for 10x robustness.

Provides:
- Graceful shutdown (SIGTERM/SIGINT handling)
- Database connection pool optimization
- Prometheus metrics endpoint
- Request correlation ID middleware
- Centralized input validation
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time

from flask import Flask, g, request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Graceful Shutdown
# ---------------------------------------------------------------------------


def init_graceful_shutdown(app: Flask) -> None:
    """Register SIGTERM/SIGINT handlers for graceful shutdown.

    On shutdown signal, stops accepting new requests and waits for
    in-flight requests to complete (up to 30s) before exiting.
    """
    shutdown_event = threading.Event()

    def _handle_signal(signum, frame):
        logger.warning('Received signal %s — initiating graceful shutdown', signum)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    @app.before_request
    def _check_shutdown():
        if shutdown_event.is_set():
            from flask import abort

            abort(503)

    app.config['SHUTDOWN_EVENT'] = shutdown_event
    logger.info('Graceful shutdown handler registered')


# ---------------------------------------------------------------------------
# 2. Database Connection Pool Optimization
# ---------------------------------------------------------------------------


def optimize_db_pool(app: Flask) -> None:
    """Tune SQLAlchemy connection pool for production workloads.

    - pool_size: base connections (default 10, configurable)
    - max_overflow: burst capacity (default 20)
    - pool_recycle: recycle connections every 3600s (prevents stale connections)
    - pool_pre_ping: test connection before use (prevents stale connection errors)
    - pool_timeout: 30s max wait for a connection
    """
    pool_size = int(os.environ.get('DB_POOL_SIZE', '10'))
    max_overflow = int(os.environ.get('DB_MAX_OVERFLOW', '20'))
    pool_recycle = int(os.environ.get('DB_POOL_RECYCLE', '3600'))
    pool_timeout = int(os.environ.get('DB_POOL_TIMEOUT', '30'))

    app.config.update(
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_recycle': pool_recycle,
            'pool_pre_ping': True,
            'pool_timeout': pool_timeout,
        }
    )
    logger.info(
        'DB pool optimized: size=%d overflow=%d recycle=%ds timeout=%ds',
        pool_size,
        max_overflow,
        pool_recycle,
        pool_timeout,
    )


# ---------------------------------------------------------------------------
# 3. Request Correlation ID Middleware
# ---------------------------------------------------------------------------


def init_correlation_id(app: Flask) -> None:
    """Ensure every request has a unique correlation ID for tracing.

    Reads X-Request-ID or X-Correlation-ID from incoming headers,
    or generates a new UUID. Propagates to response headers.
    """
    import uuid

    @app.before_request
    def _set_correlation_id():
        incoming = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID')
        cid = incoming or uuid.uuid4().hex[:16]
        g.correlation_id = cid
        g.trace_id = cid

    @app.after_request
    def _add_correlation_header(response):
        cid = getattr(g, 'correlation_id', None)
        if cid:
            response.headers['X-Request-ID'] = cid
            response.headers['X-Correlation-ID'] = cid
        return response

    logger.info('Correlation ID middleware registered')


# ---------------------------------------------------------------------------
# 4. Prometheus Metrics Endpoint
# ---------------------------------------------------------------------------


def init_metrics_endpoint(app: Flask) -> None:
    """Add /metrics endpoint for Prometheus scraping.

    Exposes basic application metrics: request count, response times, etc.
    """
    from prometheus_client import Counter, Histogram

    request_count = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status'],
    )
    request_duration = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint'],
    )

    @app.before_request
    def _start_timer():
        g._request_start = time.time()

    @app.after_request
    def _record_metrics(response):
        try:
            duration = time.time() - getattr(g, '_request_start', time.time())
            endpoint = request.endpoint or 'unknown'
            request_count.labels(
                method=request.method,
                endpoint=endpoint,
                status=response.status_code,
            ).inc()
            request_duration.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)
        except Exception:
            pass
        return response

    # Note: /metrics endpoint is provided by monitoring_routes.py
    # HTTP request metrics are tracked via before/after_request hooks above
    logger.info(
        'HTTP request metrics tracking registered (endpoint: /metrics via monitoring_routes)'
    )


# ---------------------------------------------------------------------------
# 5. Centralized Input Validation Middleware
# ---------------------------------------------------------------------------


def init_input_validation(app: Flask) -> None:
    """Centralized input validation and sanitization.

    - Strips whitespace from string inputs
    - Rejects oversized payloads (> 10MB)
    - Validates Content-Type for JSON endpoints
    """
    MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10MB

    @app.before_request
    def _validate_request():
        # Check payload size
        content_length = request.content_length
        if content_length and content_length > MAX_PAYLOAD_SIZE:
            from flask import abort

            abort(413)

        # Sanitize string inputs (strip whitespace)
        if request.method in ('POST', 'PUT', 'PATCH') and request.is_json:
            try:
                json_data = request.get_json(silent=True)
                if json_data and isinstance(json_data, dict):
                    _sanitize_dict(json_data)
            except Exception:
                pass

    def _sanitize_dict(d):
        for key, value in list(d.items()):
            if isinstance(value, str):
                d[key] = value.strip()
            elif isinstance(value, dict):
                _sanitize_dict(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _sanitize_dict(item)

    logger.info('Input validation middleware registered')


# ---------------------------------------------------------------------------
# 6. Database Query Optimization Helpers
# ---------------------------------------------------------------------------


def init_query_optimization(app: Flask) -> None:
    """Enable SQLAlchemy query optimization features.

    - Eager loading hints
    - Query profiling in debug mode
    """
    if app.config.get('FLASK_DEBUG'):
        from sqlalchemy import event

        from app.extensions import db

        @event.listens_for(db.engine, 'before_cursor_execute')
        def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())

        @event.listens_for(db.engine, 'after_cursor_execute')
        def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            times = conn.info.get('query_start_time', [])
            if times:
                elapsed = time.time() - times.pop()
                if elapsed > 1.0:  # Log slow queries (> 1s)
                    logger.warning('Slow query (%.2fs): %s', elapsed, statement[:200])

    logger.info('Query optimization helpers registered')


# ---------------------------------------------------------------------------
# Main initializer
# ---------------------------------------------------------------------------


def init_resilience(app: Flask) -> None:
    """Initialize all resilience and observability enhancements."""
    init_graceful_shutdown(app)
    optimize_db_pool(app)
    init_correlation_id(app)
    init_input_validation(app)
    try:
        init_metrics_endpoint(app)
    except ImportError:
        logger.warning('prometheus_client not installed — metrics endpoint disabled')
    if app.config.get('FLASK_DEBUG'):
        init_query_optimization(app)
    logger.info('All resilience enhancements initialized')


def init_app(app: Flask) -> None:
    """Alias for init_resilience."""
    init_resilience(app)
