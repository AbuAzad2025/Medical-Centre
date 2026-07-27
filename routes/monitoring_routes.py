"""Prometheus metrics endpoint for production monitoring.

Exposes application-level metrics in Prometheus text format for scraping
by Prometheus, Grafana, or any compatible monitoring stack.

Key metrics:
  - medical_orphaned_tenant_rows{table="..."} — number of rows with tenant_id=0
  - medical_db_up — 1 if DB is reachable, 0 otherwise

Add this blueprint to the app in app_factory.py via:
    from routes.monitoring_routes import monitoring_bp
    app.register_blueprint(monitoring_bp)
"""
from flask import Blueprint, Response, current_app, g
from sqlalchemy import text as sa_text

monitoring_bp = Blueprint('monitoring', __name__)

# Must match app/shared/tenant_filter.py → _GLOBAL_TENANT_TABLES
_GLOBAL_TENANT_TABLES = frozenset({
    'tenants', 'roles', 'permissions', 'role_permissions', 'user_permissions',
    'module_permissions', 'department_permissions',
    'system_configs', 'branding_settings', 'platform_audit_logs',
})


def _discover_tenant_tables() -> list[str]:
    """Return list of tenant-scoped table names."""
    from app.extensions import db
    rows = db.session.execute(sa_text("""
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
    return [r[0] for r in rows if r[0] not in _GLOBAL_TENANT_TABLES]


def _collect_metrics() -> str:
    """Collect all metrics and return Prometheus text format string."""
    from app.extensions import db
    from datetime import datetime, timezone

    lines: list[str] = []
    now = datetime.now(timezone.utc).timestamp()

    # Header
    lines.append("# HELP medical_orphaned_tenant_rows Rows with orphaned tenant_id=0")
    lines.append("# TYPE medical_orphaned_tenant_rows gauge")
    lines.append("# HELP medical_db_up Whether the database is reachable")
    lines.append("# TYPE medical_db_up gauge")
    lines.append("# HELP medical_scrape_duration_seconds Time taken to collect metrics")
    lines.append("# TYPE medical_scrape_duration_seconds gauge")

    # DB health check
    try:
        db.session.execute(sa_text("SELECT 1"))
        lines.append(f"medical_db_up 1 {int(now)}000")
    except Exception as e:
        lines.append(f"medical_db_up 0 {int(now)}000")
        lines.append(f"medical_scrape_duration_seconds 0 {int(now)}000")
        return '\n'.join(lines) + '\n'

    import time
    t0 = time.monotonic()

    total_orphans = 0
    orphan_tables = 0

    try:
        tables = _discover_tenant_tables()
        for table in tables:
            count = db.session.execute(
                sa_text(f"SELECT count(*) FROM {table} WHERE tenant_id = 0")
            ).scalar() or 0
            if count:
                total_orphans += count
                orphan_tables += 1
                # Escaped table name label
                label = table.replace('\\', '\\\\').replace('"', '\\"')
                lines.append(
                    f'medical_orphaned_tenant_rows{{table="{label}"}} {count} {int(now)}000'
                )

        # Aggregate total
        lines.append(
            f'medical_orphaned_tenant_rows{{table="__total__"}} {total_orphans} {int(now)}000'
        )

        if orphan_tables:
            lines.append(
                '# NOTE: tenant_id=0 rows indicate orphaned data from S2-001 backfill.'
            )
    except Exception as exc:
        lines.append(f'# ERROR collecting orphan metrics: {exc}')

    duration = time.monotonic() - t0
    lines.append(f"medical_scrape_duration_seconds {duration:.4f} {int(now)}000")

    return '\n'.join(lines) + '\n'


@monitoring_bp.route('/metrics')
def metrics():
    """Prometheus metrics endpoint — unauthenticated, read-only."""
    current_app.logger.debug("Prometheus /metrics scrape")
    return Response(_collect_metrics(), mimetype='text/plain; version=0.0.4')
