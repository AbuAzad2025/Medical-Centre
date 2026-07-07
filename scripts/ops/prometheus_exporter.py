#!/usr/bin/env python3
"""Standalone Prometheus exporter for medical-system tenant isolation metrics.

Runs an HTTP server on port 9180 (configurable via PORT env var) and exposes
a /metrics endpoint in Prometheus text format.  This is useful when:
  - The Flask app's built-in /metrics endpoint is disabled behind auth
  - You want to run the exporter in a sidecar container
  - You need minimal dependency overhead (no Flask app bootstrap required)

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/db python prometheus_exporter.py

Scrapes the database every 60 seconds (configurable via SCRAPE_INTERVAL).
Metrics are cached between scrapes.
"""
from __future__ import annotations

import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import sqlalchemy as sa

PORT = int(os.environ.get('PORT', '9180'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', '60'))
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('MIGRATE_DATABASE_URL')

# Must match app/shared/tenant_filter.py → _GLOBAL_TENANT_TABLES
GLOBAL_TENANT_TABLES = frozenset({
    'tenants', 'roles', 'permissions', 'role_permissions', 'user_permissions',
    'module_permissions', 'department_permissions',
    'system_configs', 'branding_settings', 'platform_audit_logs',
})

if not DATABASE_URL:
    print('FATAL: set DATABASE_URL environment variable', file=sys.stderr)
    sys.exit(1)

engine = sa.create_engine(DATABASE_URL, pool_pre_ping=True)
cached_metrics: str = ''
last_scrape: float = 0
scrape_lock = __import__('threading').Lock()


def discover_tenant_tables(conn) -> list[str]:
    """Return all public tables with a tenant_id column, excluding global."""
    rows = conn.execute(sa.text("""
        SELECT c.relname
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN information_schema.columns col
          ON col.table_name = c.relname
         AND col.table_schema = 'public'
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND col.column_name = 'tenant_id'
        ORDER BY c.relname
    """)).fetchall()
    return [row[0] for row in rows if row[0] not in GLOBAL_TENANT_TABLES]


def scrape() -> str:
    """Collect metrics and return Prometheus text format payload."""
    lines: list[str] = []
    now_ts = int(time.time())

    lines.append("# HELP medical_orphaned_tenant_rows Rows with orphaned tenant_id=0")
    lines.append("# TYPE medical_orphaned_tenant_rows gauge")
    lines.append("# HELP medical_db_up Whether the database is reachable")
    lines.append("# TYPE medical_db_up gauge")

    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
            lines.append(f"medical_db_up 1 {now_ts}000")

            t0 = time.monotonic()
            tables = discover_tenant_tables(conn)
            total = 0
            for table in tables:
                count = conn.execute(
                    sa.text(f"SELECT count(*) FROM {table} WHERE tenant_id = 0")
                ).scalar() or 0
                if count:
                    total += count
                    label = table.replace('\\', '\\\\').replace('"', '\\"')
                    lines.append(
                        f'medical_orphaned_tenant_rows{{table="{label}"}} {count} {now_ts}000'
                    )

            lines.append(
                f'medical_orphaned_tenant_rows{{table="__total__"}} {total} {now_ts}000'
            )
            duration = time.monotonic() - t0
            lines.append(f"# scrape_duration_seconds {duration:.4f}")

    except Exception as exc:
        lines.append(f"medical_db_up 0 {now_ts}000")
        lines.append(f"# ERROR: {exc}")

    return '\n'.join(lines) + '\n'


def background_scrape():
    """Periodically refresh the cached metrics."""
    global cached_metrics, last_scrape
    while True:
        try:
            metrics = scrape()
            with scrape_lock:
                cached_metrics = metrics
                last_scrape = time.time()
        except Exception as exc:
            print(f"Scrape error: {exc}", file=sys.stderr)
        time.sleep(SCRAPE_INTERVAL)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/metrics':
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4')
        self.send_header('Cache-Control', f'max-age={SCRAPE_INTERVAL}')
        self.end_headers()

        with scrape_lock:
            payload = cached_metrics
        self.wfile.write(payload.encode())

    def log_message(self, fmt, *args):
        """Silence default HTTP server logging; use print for scrape errors only."""
        pass


def main():
    if not DATABASE_URL:
        print('FATAL: set DATABASE_URL', file=sys.stderr)
        return 1

    # Verify DB connectivity at startup
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
            tables_count = len(discover_tenant_tables(conn))
        print(f"Connected to database. Monitoring {tables_count} tenant-scoped tables.")
    except Exception as exc:
        print(f"FATAL: Cannot connect to database: {exc}", file=sys.stderr)
        return 1

    # Start background scraper
    import threading
    scraper = threading.Thread(target=background_scrape, daemon=True)
    scraper.start()

    # Start HTTP server
    server = HTTPServer(('0.0.0.0', PORT), MetricsHandler)
    print(f"Prometheus exporter listening on :{PORT}/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
