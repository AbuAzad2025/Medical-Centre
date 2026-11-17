#!/usr/bin/env python3
"""Schema parity gate: every model change must have a matching migration.

Builds two throw-away PostgreSQL databases from the same source tree:

* ``alembic`` database: ``flask_migrate.upgrade(revision='head')``
* ``metadata`` database: ``db.create_all()`` from the ORM metadata

Then compares the *table* and *column* sets (name + SQL type + nullability).
Any difference fails the build with a precise diff, so a forgotten migration is
caught in the same CI run that introduced the model change instead of weeks
later in production.

Only structural table/column parity is asserted. Raw-DDL-only objects (RLS
policies, indexes, triggers, functions, enum *values*, partitioned-table
strategy) are intentionally out of scope: they can never be emitted by
``create_all()`` and already have their own CI gates. A short, documented
allowlist covers the handful of objects that legitimately exist on only one
side (see ``ALLOWED_ONLY_IN_ALEMBIC`` / ``ALLOWED_ONLY_IN_METADATA``).

Run from CI (with ``MIGRATE_ADMIN_URL`` pointing at the ``postgres`` database)::

    python scripts/ci/schema_parity.py

Locally::

    DATABASE_URL=postgresql://postgres:testpass@127.0.0.1:5433/postgres \
        python scripts/ci/schema_parity.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MIGRATIONS_DIR = PROJECT_ROOT / 'migrations'

# Prepared-statement / connection URLs ---------------------------------------
ADMIN_URL = (
    os.environ.get('MIGRATE_ADMIN_URL')
    or os.environ.get('DATABASE_URL')
    or 'postgresql://postgres:testpass@127.0.0.1:5433/postgres'
)
DB_ALEMBIC = os.environ.get('SCHEMA_PARITY_ALEMBIC_DB', 'schema_parity_alembic')
DB_METADATA = os.environ.get('SCHEMA_PARITY_METADATA_DB', 'schema_parity_metadata')

# Tables that legitimately exist only on one side. Every entry MUST be
# justified here; an unexplained entry defeats the purpose of the gate.
#
# alembic_version is Alembic's own stamp table (create_all never creates it).
# The rest are tables created exclusively via raw SQL inside migrations: they
# have no ORM model on purpose (lookup/catalog tables, partition defaults and
# supplementary tables added by later migrations). They are *not* missing
# models — a real missing model would surface as a table in the metadata DB
# that has no counterpart here, which is always a hard failure below.
ALLOWED_ONLY_IN_ALEMBIC: frozenset[str] = frozenset(
    {
        'alembic_version',
        # partition default leaves (parents are models, defaults are raw DDL)
        'audit_trails_default',
        'login_attempts_default',
        'phi_audit_logs_default',
        'platform_audit_logs_default',
        'security_events_default',
        'slow_query_reports_default',
        'system_logs_default',
        # raw-DDL catalog / supplementary tables (no declarative model)
        'api_keys',
        'best_practice_advisories',
        'consent_audit_logs',
        'consent_templates',
        'consultations',
        'device_alarms',
        'device_parameters',
        'iot_devices',
        'iot_readings',
        'medical_devices',
        'order_set_items',
        'order_sets',
        'patient_consents',
        'phi_audit_logs',
        'shift_handovers',
        'snomed_concepts',
        'snomed_relationships',
    }
)
# A table in the ORM metadata with no migration is *always* a missing
# migration. No allowlist: that is the primary thing this gate detects.
ALLOWED_ONLY_IN_METADATA: frozenset[str] = frozenset()

# Nullability-only differences on tenant_id are expected: migration s2_001
# applies NOT NULL to every tenant-scoped table, while TenantMixin deliberately
# declares the column nullable in the ORM (auto-assign fills it at runtime).
# This is the single systematic asymmetry in the codebase and is handled by a
# dedicated rule in compare() (column name == 'tenant_id').
#
# Two other nullability-only differences predate this gate and come from the
# production baseline migration declaring NOT NULL where the model is nullable.
ALLOWED_NULLABILITY_DIFFS: frozenset[tuple[str, str]] = frozenset(
    {
        ('emar_administrations', 'medication_id'),
        ('loinc_codes', 'is_active'),
    }
)

# Type differences that are documented and safe. Empty now that the
# whatsapp phone_number VARCHAR(20)->TEXT drift has its own migration.
ALLOWED_TYPE_DIFFS: frozenset[tuple[str, str]] = frozenset()


def _database_url(admin_url: str, db_name: str) -> str:
    """Return ``admin_url`` with its database name replaced by ``db_name``."""
    parsed = urlparse(admin_url)
    path = f'/{db_name}'
    return urlunparse(parsed._replace(path=path))


def _admin_connect(db_name: str = 'postgres'):
    import psycopg2

    return psycopg2.connect(_database_url(ADMIN_URL, db_name))


def recreate_database(db_name: str) -> None:
    """Drop (if present) and create an empty database; caller closes nothing."""
    conn = _admin_connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # Terminate stray connections from an interrupted previous run.
            cur.execute(
                'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()',
                (db_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            cur.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.close()
    print(f'  created fresh database {db_name}')


def drop_database(db_name: str) -> None:
    conn = _admin_connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()',
                (db_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    finally:
        conn.close()


def _mini_app(url: str):
    """A minimal Flask app whose only job is to bind SQLAlchemy + Flask-Migrate."""
    from flask import Flask

    from app_factory import db, migrate

    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='schema-parity-placeholder',
    )
    db.init_app(app)
    migrate.init_app(app, db)
    return app


def build_with_alembic(url: str) -> None:
    """Build the reference schema by applying every migration to an empty DB."""
    os.environ.setdefault('SKIP_PLATFORM_BOOTSTRAP', '1')
    os.environ.setdefault('RLS_BYPASS_ALLOWED', '1')
    os.environ.setdefault('SECRET_KEY', 'schema-parity-placeholder')
    from flask_migrate import upgrade

    app = _mini_app(url)
    with app.app_context():
        upgrade(directory=str(MIGRATIONS_DIR), revision='head')


def build_with_create_all(url: str) -> None:
    """Build the ORM schema from model metadata only (no migrations)."""
    # Import every declarative model module so db.metadata is complete. The
    # legacy models are consolidated in models/__init__.py; the SaaS/platform
    # models live under app/. Missing one here would create a false "missing
    # migration" report, so this list must track new model modules.
    import app.core.module.models  # noqa: F401
    import app.core.saas.models  # noqa: F401
    import app.core.tenant.models  # noqa: F401
    import app.modules.workflows.stock_models  # noqa: F401
    import models  # noqa: F401
    from app_factory import db

    app = _mini_app(url)
    with app.app_context():
        db.create_all()


def introspect(url: str) -> dict[str, dict[str, tuple[str, str, str]]]:
    """Return ``{table: {column: (data_type, udt_name, is_nullable)}}``."""
    import psycopg2

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.relname AS table_name,
                       a.attname AS column_name,
                       pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                       COALESCE(t.typname, '') AS udt_name,
                       a.attnotnull AS not_null
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                LEFT JOIN pg_type t ON t.oid = a.atttypid
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p')
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                ORDER BY c.relname, a.attname
                """
            )
            schema: dict[str, dict[str, tuple[str, str, str]]] = {}
            for table, column, data_type, udt_name, not_null in cur.fetchall():
                # Compare enum udt_name rather than the generic 'USER-DEFINED',
                # so a renamed enum type is still detected.
                effective_type = udt_name if udt_name else data_type
                schema.setdefault(table, {})[column] = (
                    effective_type,
                    data_type,
                    'NO' if not_null else 'YES',
                )
            return schema
    finally:
        conn.close()


def compare(
    alembic_schema: dict[str, dict[str, tuple[str, str, str]]],
    metadata_schema: dict[str, dict[str, tuple[str, str, str]]],
) -> list[str]:
    """Return a human-readable list of differences (empty means parity)."""
    diffs: list[str] = []

    only_alembic = sorted(set(alembic_schema) - set(metadata_schema) - ALLOWED_ONLY_IN_ALEMBIC)
    only_metadata = sorted(set(metadata_schema) - set(alembic_schema) - ALLOWED_ONLY_IN_METADATA)
    for table in only_alembic:
        diffs.append(f'TABLE only in alembic DB (model missing?): {table}')
    for table in only_metadata:
        diffs.append(f'TABLE only in metadata DB (MIGRATION MISSING!): {table}')

    for table in sorted(set(alembic_schema) & set(metadata_schema)):
        a_cols = alembic_schema[table]
        m_cols = metadata_schema[table]
        # A column present on only one side is always drift. In particular a
        # column only in the metadata DB is a missing migration; no allowlist
        # exists for it by design.
        for column in sorted(set(a_cols) - set(m_cols)):
            diffs.append(f'COLUMN only in alembic DB: {table}.{column}')
        for column in sorted(set(m_cols) - set(a_cols)):
            diffs.append(f'COLUMN only in metadata DB (MIGRATION MISSING!): {table}.{column}')
        for column in sorted(set(a_cols) & set(m_cols)):
            a_type, _, a_null = a_cols[column]
            m_type, _, m_null = m_cols[column]
            if a_type != m_type and (table, column) not in ALLOWED_TYPE_DIFFS:
                diffs.append(f'TYPE mismatch {table}.{column}: alembic={a_type} metadata={m_type}')
            if a_null != m_null:
                tenant_rule = column == 'tenant_id'
                reviewed = (table, column) in ALLOWED_NULLABILITY_DIFFS
                if not tenant_rule and not reviewed:
                    diffs.append(
                        f'NULLABILITY mismatch {table}.{column}: '
                        f'alembic=nullable={a_null} metadata=nullable={m_null}'
                    )
    return diffs


def main() -> int:
    print('Schema parity: alembic upgrade head  vs  db.create_all()')
    print(f'  admin URL: {ADMIN_URL}')
    recreate_database(DB_ALEMBIC)
    recreate_database(DB_METADATA)
    try:
        print('Building reference schema with alembic upgrade head ...')
        build_with_alembic(_database_url(ADMIN_URL, DB_ALEMBIC))
        print('Building ORM schema with db.create_all() ...')
        build_with_create_all(_database_url(ADMIN_URL, DB_METADATA))

        alembic_schema = introspect(_database_url(ADMIN_URL, DB_ALEMBIC))
        metadata_schema = introspect(_database_url(ADMIN_URL, DB_METADATA))
        print(
            f'  alembic DB:  {len(alembic_schema)} tables, '
            f'{sum(len(c) for c in alembic_schema.values())} columns'
        )
        print(
            f'  metadata DB: {len(metadata_schema)} tables, '
            f'{sum(len(c) for c in metadata_schema.values())} columns'
        )

        diffs = compare(alembic_schema, metadata_schema)
        if diffs:
            print(f'\nSCHEMA PARITY FAILED — {len(diffs)} difference(s):')
            for line in diffs:
                print(f'  - {line}')
            return 1
        print('\nSCHEMA PARITY OK — no table/column drift detected.')
        return 0
    finally:
        print('Cleaning up temporary databases ...')
        drop_database(DB_ALEMBIC)
        drop_database(DB_METADATA)


if __name__ == '__main__':
    sys.exit(main())
