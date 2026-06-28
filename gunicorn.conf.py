"""Gunicorn production configuration for high-concurrency SaaS deployment."""
from __future__ import annotations

import multiprocessing
import os

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8080')
workers = int(os.environ.get('WEB_CONCURRENCY', (2 * multiprocessing.cpu_count()) + 1))
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'gthread')
threads = int(os.environ.get('GUNICORN_THREADS', '4'))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', '5'))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', '30'))
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', '50'))
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '-')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '-')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
preload_app = os.environ.get('GUNICORN_PRELOAD', 'false').lower() in ('true', '1', 'on')


def on_starting(server):
    server.log.info(
        'Gunicorn boot workers=%s class=%s threads=%s bind=%s',
        workers,
        worker_class,
        threads,
        bind,
    )
