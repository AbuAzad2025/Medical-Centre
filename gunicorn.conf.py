"""
Gunicorn Configuration for Medical System Production Deployment
"""
import os
import multiprocessing

# Server socket
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')
backlog = int(os.environ.get('GUNICORN_BACKLOG', '2048'))

# Worker processes
workers = int(os.environ.get('WEB_CONCURRENCY', os.environ.get('GUNICORN_WORKERS', str(multiprocessing.cpu_count() * 2 + 1))))
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'gthread')
worker_connections = int(os.environ.get('GUNICORN_WORKER_CONNECTIONS', '1000'))
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', '50'))

# Timeouts
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '60'))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', '5'))

# Logging
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '-')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '-')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'medical-system'

# Preload application for better memory usage
preload_app = True

# Security
limit_request_fields = int(os.environ.get('GUNICORN_LIMIT_REQUEST_FIELDS', '100'))
limit_request_field_size = int(os.environ.get('GUNICORN_LIMIT_REQUEST_FIELD_SIZE', '8190'))
limit_request_line = int(os.environ.get('GUNICORN_LIMIT_REQUEST_LINE', '4094'))

# SSL (if terminating at gunicorn)
# keyfile = os.environ.get('GUNICORN_KEYFILE')
# certfile = os.environ.get('GUNICORN_CERTFILE')

# Graceful shutdown
worker_tmp_dir = os.environ.get('GUNICORN_WORKER_TMP_DIR', '/dev/shm')

def when_ready(server):
    server.log.info("Medical System ready to accept connections")

def worker_int(worker):
    worker.log.info("Worker %d interrupted", worker.pid)

def pre_fork(server, worker):
    server.log.info("Spawning worker %d", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker %d spawned", worker.pid)