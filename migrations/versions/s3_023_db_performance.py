"""Database performance optimization.

Adds missing FK indexes, materialized views for reports, connection-pooling
is configured in config.py, and partitions high-volume audit log tables.

Revision ID: s3_023_db_performance
Revises: s3_022_snomed_ct
Create Date: 2026-10-30
"""

from __future__ import annotations

import os
import sys

import sqlalchemy as sa
from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

revision = "s3_023_db_performance"
down_revision = "s3_022_snomed_ct"
branch_labels = None
depends_on = None

MISSING_FK_INDEXES = [
    ("idx_perf_consultations_created_by_id", "consultations", "created_by_id"),
    ("idx_perf_entitlement_grants_enterprise_contract_entitlement_id", "entitlement_grants", "enterprise_contract_entitlement_id"),
    ("idx_perf_entitlement_grants_subscription_line_id", "entitlement_grants", "subscription_line_id"),
    ("idx_perf_entitlement_grants_tenant_feature_flag_id", "entitlement_grants", "tenant_feature_flag_id"),
    ("idx_perf_entitlement_grants_tenant_override_id", "entitlement_grants", "tenant_override_id"),
    ("idx_perf_gl_journals_posted_by", "gl_journals", "posted_by"),
    ("idx_perf_invoice_services_created_by", "invoice_services", "created_by"),
    ("idx_perf_patient_consents_previous_version_id", "patient_consents", "previous_version_id"),
    ("idx_perf_refund_requests_approved_by", "refund_requests", "approved_by"),
    ("idx_perf_refund_requests_executed_by", "refund_requests", "executed_by"),
    ("idx_perf_refund_requests_requested_by", "refund_requests", "requested_by"),
    ("idx_perf_service_master_approved_by", "service_master", "approved_by"),
    ("idx_perf_service_master_created_by", "service_master", "created_by"),
    ("idx_perf_shift_handovers_closed_by_id", "shift_handovers", "closed_by_id"),
    ("idx_perf_shift_handovers_opened_by_id", "shift_handovers", "opened_by_id"),
    ("idx_perf_shift_handovers_to_user_id", "shift_handovers", "to_user_id"),
    ("idx_perf_tenant_overrides_granted_by", "tenant_overrides", "granted_by"),
]

AUDIT_TABLES = [
    "audit_trails",
    "phi_audit_logs",
    "platform_audit_logs",
    "system_logs",
    "security_events",
    "login_attempts",
    "slow_query_reports",
]


def _table_exists(bind: sa.engine.Connection, table: str) -> bool:
    result = bind.execute(
        sa.text("SELECT to_regclass(:rel) IS NOT NULL"),
        {"rel": f"public.{table}"},
    ).scalar()
    return bool(result)


def _is_partitioned(bind: sa.engine.Connection, table: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT count(*) FROM pg_partitioned_table "
            "WHERE partrelid = CAST(:t AS regclass)"
        ),
        {"t": table},
    ).scalar()
    return bool(result)


def _partition_audit_table(table: str) -> None:
    bind = op.get_bind()
    try:
        bind.execute(sa.text("SELECT set_config('app.bypass_rls', 'on', false)"))
        bind.execute(sa.text("SELECT set_config('app.tenant_id', '', false)"))
    except Exception:
        pass
    if not _table_exists(bind, table):
        return
    if _is_partitioned(bind, table):
        return

    # Collect existing metadata before recreating.
    policies = bind.execute(
        sa.text(
            "SELECT policyname, cmd, roles, qual, with_check, permissive "
            "FROM pg_policies WHERE schemaname = current_schema() AND tablename = :t"
        ),
        {"t": table},
    ).fetchall()

    constraints = bind.execute(
        sa.text(
            "SELECT conname, pg_get_constraintdef(oid) "
            "FROM pg_constraint "
            "WHERE conrelid = CAST(:t AS regclass) AND contype IN ('c', 'f', 'u')"
        ),
        {"t": table},
    ).fetchall()

    not_null_columns = [
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = :t "
                "AND is_nullable = 'NO'"
            ),
            {"t": table},
        ).fetchall()
    ]

    indexes = [
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = current_schema() AND tablename = :t "
                "AND indexname NOT LIKE '%_pkey'"
            ),
            {"t": table},
        ).fetchall()
    ]

    serial_sequence = bind.execute(
        sa.text("SELECT pg_get_serial_sequence(:t, 'id')"),
        {"t": table},
    ).scalar()

    new_table = f"{table}_perf_new"
    default_partition = f"{table}_perf_default"

    op.execute(sa.text(
        f"CREATE TABLE {new_table} "
        f"(LIKE {table} INCLUDING DEFAULTS EXCLUDING INDEXES EXCLUDING CONSTRAINTS) "
        f"PARTITION BY RANGE (created_at)"
    ))
    op.execute(sa.text(
        f"CREATE TABLE {default_partition} PARTITION OF {new_table} DEFAULT"
    ))
    _partition_columns = [r[0] for r in bind.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = :t "
        "ORDER BY ordinal_position"
    ), {"t": table}).fetchall()]
    op.execute(sa.text(
        f"INSERT INTO {new_table} ({', '.join(_partition_columns)}) "
        f"SELECT {', '.join(_partition_columns)} FROM {table}"
    ))

    if serial_sequence:
        op.execute(sa.text(f"ALTER SEQUENCE {serial_sequence} OWNED BY NONE"))

    op.execute(sa.text(f"DROP TABLE {table} CASCADE"))
    op.execute(sa.text(f"ALTER TABLE {new_table} RENAME TO {table}"))
    op.execute(sa.text(f"ALTER TABLE {default_partition} RENAME TO {table}_default"))

    for column in not_null_columns:
        op.execute(sa.text(
            f'ALTER TABLE {table} ALTER COLUMN "{column}" SET NOT NULL'
        ))

    import contextlib

    for con_name, con_def in constraints:
        with contextlib.suppress(Exception):
            op.execute(sa.text(
                f"ALTER TABLE {table} ADD CONSTRAINT {con_name} {con_def}"
            ))

    for index_def in indexes:
        with contextlib.suppress(Exception):
            op.execute(sa.text(index_def))

    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

    for policy in policies:
        policy_name, cmd, roles, qual, with_check, permissive = policy
        as_sql = " AS RESTRICTIVE" if permissive == "RESTRICTIVE" else ""
        to_sql = ""
        if roles and roles != ["public"]:
            to_sql = " TO " + ", ".join(roles)
        using_sql = f" USING ({qual})" if qual is not None else ""
        check_sql = f" WITH CHECK ({with_check})" if with_check is not None else ""
        stmt = (
            f"CREATE POLICY {policy_name} ON {table}{as_sql} "
            f"FOR {cmd}{to_sql}{using_sql}{check_sql}"
        )
        with contextlib.suppress(Exception):
            op.execute(sa.text(stmt))


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Missing FK indexes.
    for idx_name, table, column in MISSING_FK_INDEXES:
        if not _table_exists(bind, table):
            continue
        op.create_index(idx_name, table, [column], if_not_exists=True)

    # 2. Materialized views for reports.
    op.execute(sa.text("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_patient_summary AS
        SELECT
            p.tenant_id,
            p.id AS patient_id,
            COUNT(v.id) AS total_visits,
            MAX(v.visit_date) AS last_visit_date,
            COALESCE(SUM(v.total_amount), 0) AS total_amount,
            COALESCE(SUM(v.paid_amount), 0) AS paid_amount
        FROM patients p
        LEFT JOIN visits v ON v.patient_id = p.id
        GROUP BY p.tenant_id, p.id
        WITH DATA
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_tenant "
        "ON mv_patient_summary (tenant_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_patient "
        "ON mv_patient_summary (patient_id)"
    ))

    op.execute(sa.text("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_department_stats AS
        SELECT
            d.tenant_id,
            d.id AS department_id,
            COUNT(v.id) AS total_visits,
            COUNT(DISTINCT v.patient_id) AS total_patients,
            COUNT(DISTINCT v.doctor_id) AS total_doctors,
            COALESCE(SUM(v.total_amount), 0) AS total_amount
        FROM departments d
        LEFT JOIN visits v ON v.department_id = d.id
        GROUP BY d.tenant_id, d.id
        WITH DATA
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_mv_department_stats_tenant "
        "ON mv_department_stats (tenant_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_mv_department_stats_department "
        "ON mv_department_stats (department_id)"
    ))

    # 3. Partition audit log tables.
    for table in AUDIT_TABLES:
        _partition_audit_table(table)


def downgrade() -> None:
    for _table in AUDIT_TABLES:
        # Best-effort: cannot easily un-partition; leave as-is.
        pass

    op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS mv_department_stats"))
    op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS mv_patient_summary"))

    for idx_name, table, _column in MISSING_FK_INDEXES:
        import contextlib

        with contextlib.suppress(Exception):
            op.drop_index(idx_name, table_name=table, if_exists=True)
