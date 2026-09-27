"""Idempotent platform bootstrap — single entry for production catalog setup.

Runs on every application start from :func:`app_factory.create_app`, so a fresh
deployment needs no manual step. Every step is idempotent: it inspects current
state, applies only the delta, and is safe to run concurrently on every worker
of a multi-process deployment.

Design rules this module follows deliberately:

* **Never invent schema.** Alembic owns the schema. A missing table is reported,
  not silently created, because ``create_all()`` against a partially migrated
  database produces tables that are missing every later ``ALTER TABLE`` and
  diverge permanently. The single exception is a database with no user tables at
  all, which is a genuine fresh install where ``create_all()`` is correct.
* **Never ship a fixed default password.** A hardcoded bootstrap credential is
  an unauthenticated backdoor the moment the port is reachable. A random
  password is generated and logged once, on creation only.
* **Never raise.** A bootstrap problem must degrade the log, not stop the
  server: an already-running instance is better than a crash loop.
* **Log through the app logger**, so bootstrap output is filterable alongside
  the rest of the application rather than going to bare stdout.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.extensions import db
from utils.db_safety import safe_commit
from utils.seed_manifest import (
    PLATFORM_ADMIN_EMAIL,
    PLATFORM_ADMIN_ROLE,
    PLATFORM_ADMIN_USERNAME,
    RUNTIME_DIRECTORIES,
    resolve_admin_password,
)

logger = logging.getLogger(__name__)

#: Directories the app writes to at runtime. All of these are listed in
#: .gitignore, which is exactly why they are absent on a fresh clone and why
#: provisioning them belongs here rather than in the repository.


def _table_count(table: str) -> int:
    from sqlalchemy import inspect, text

    if table not in inspect(db.engine).get_table_names():
        return -1
    return int(db.session.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar() or 0)


def ensure_module_definitions() -> int:
    """Register all MODULE_REGISTRY entries in module_definitions."""
    from app.core.module.models import ModuleDefinition
    from app.core.module.registry import MODULE_REGISTRY

    added = 0
    for name, meta in MODULE_REGISTRY.items():
        if db.session.execute(select(ModuleDefinition).filter_by(name=name)).scalars().first():
            continue
        db.session.add(
            ModuleDefinition(
                name=name,
                name_ar=meta.name_ar,
                category=meta.category,
                description=meta.description_ar,
                is_active=True,
            )
        )
        added += 1
    if added:
        safe_commit(db.session, error_message='database commit failed', reraise=True)
    return added


def ensure_product_bundles() -> int:
    """Seed default ProductBundles when the catalog table is empty."""
    from app.core.tenant.models import seed_default_bundles

    before = _table_count('product_bundles')
    if before == 0:
        seed_default_bundles()
    return _table_count('product_bundles')


def ensure_saas_packages() -> int:
    """Mirror ProductBundle rows into packages / package_versions (idempotent)."""
    from app.core.saas.seed import seed_packages_from_product_bundles

    before = _table_count('packages')
    created = seed_packages_from_product_bundles()
    after = _table_count('packages')
    if created:
        logger.info('SaaS packages created: %s', len(created))
    return max(after - before, 0) if before >= 0 else len(created)


def ensure_developer_config() -> int:
    """Seed developer info into system_configs if absent (idempotent, platform bootstrap)."""
    from models.system_config import SystemConfig

    added = 0
    from utils.seed_manifest import DEVELOPER_CONFIG

    for d in DEVELOPER_CONFIG:
        if (
            not db.session.execute(select(SystemConfig).filter_by(config_key=d['key']))
            .scalars()
            .first()
        ):
            db.session.add(
                SystemConfig(
                    config_key=d['key'],
                    config_value=d['value'],
                    config_type=d['type'],
                    category='general',
                    is_system=True,
                )
            )
            added += 1
    if added:
        safe_commit(db.session, error_message='database commit failed', reraise=True)
    return added


def _log():
    """Return the application logger when available, else the module logger.

    Bootstrap runs inside an app context during ``create_app``, so the app logger
    is normally reachable and gives the deployment one filterable stream.
    """
    try:
        from flask import current_app

        if current_app:
            return current_app.logger
    except Exception:
        pass
    return logger


def ensure_storage_directories() -> list[str]:
    """Create the runtime directories, returning the ones that were created.

    Called on boot so a fresh clone does not 500 on the first upload or report.
    ``exist_ok`` makes this a no-op once the directories exist, so it is safe to
    run on every worker of every start.
    """
    _log().info('Ensuring runtime storage directories')
    created: list[str] = []
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from flask import current_app

        for key in ('UPLOAD_FOLDER', 'REPORT_FOLDER'):
            configured = current_app.config.get(key)
            if configured:
                created.extend(_ensure_one(configured))
    except Exception as exc:  # noqa: BLE001 - never block startup
        _log().warning('Configured storage paths unavailable: %s', exc)
    for rel in RUNTIME_DIRECTORIES:
        created.extend(_ensure_one(os.path.join(root, rel)))
    if created:
        _log().info('Created storage directories: %s', ', '.join(created))
    return created


def _ensure_one(path: str) -> list[str]:
    """Create *path* if absent. Returns [path] when it had to be created."""
    try:
        if Path(path).is_dir():
            return []
        Path(path).mkdir(parents=True, exist_ok=True)
        return [path]
    except OSError as exc:
        # A read-only filesystem is a deployment problem, but it must surface as
        # a log line rather than a crash loop on boot.
        _log().error('Cannot create directory %s: %s', path, exc)
        return []


def check_schema_health() -> dict[str, Any]:
    """Compare the mapped models against the live schema and report drift.

    Read-only by design, with one narrow exception: a database containing no
    user tables at all is a fresh install, and there ``create_all()`` is both
    correct and the only way to get to a working boot. A database that is
    *partially* migrated is reported instead, because creating the missing
    objects would leave them permanently behind the migrations.
    """
    from sqlalchemy import inspect

    result: dict[str, Any] = {
        'ok': True,
        'missing_tables': [],
        'missing_indexes': [],
        'created': False,
    }
    try:
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        mapped = set(db.metadata.tables)
        # Alembic's own bookkeeping table is not a model.
        existing_tables.discard('alembic_version')

        if not existing_tables:
            _log().info('No user tables found: treating as fresh install, creating schema')
            db.create_all()
            result['created'] = True
            return result

        missing = sorted(t for t in mapped if t not in existing_tables)
        result['missing_tables'] = missing

        unindexed = _unindexed_columns(inspector, mapped & existing_tables)
        result['unindexed_columns'] = unindexed

        if missing:
            result['ok'] = False
            _log().error(
                'Schema drift detected: %d missing table(s). '
                'Run "flask db upgrade" — bootstrap will not invent schema. tables=%s',
                len(missing),
                missing[:8],
            )
        if unindexed:
            # Reported, not fatal: the migrations and the ORM do not use the same
            # index names by design, so this is a coverage signal, not proof of
            # a broken database.
            _log().warning(
                '%d column(s) declared with index=True have no index leading on them: %s',
                len(unindexed),
                unindexed[:8],
            )
        if not missing:
            _log().info(
                'Schema health OK: %d tables present, %d column(s) unindexed',
                len(existing_tables),
                len(unindexed),
            )
    except Exception as exc:  # noqa: BLE001 - a failed check must not block boot
        result['ok'] = False
        result['error'] = str(exc)
        _log().exception('Schema health check failed: %s', exc)
    return result


def _unindexed_columns(inspector, tables) -> list[str]:
    """Columns the ORM declares with ``index=True`` that no index leads on.

    Compared by leading column rather than by index name on purpose: the
    migrations and the ORM do not use the same index naming convention (the
    database has ``idx_accounts_code`` where the model declares
    ``ix_accounts_code``, both on ``code``). Matching on names reported 82
    phantom differences on a database that is in fact fully migrated, which is
    worse than no check at all because it cries wolf on every boot.
    """
    out: list[str] = []
    for table in sorted(tables):
        covered: set[str] = set()
        for index in inspector.get_indexes(table):
            cols = index.get('column_names') or []
            if cols:
                covered.add(cols[0])
        for constraint in inspector.get_unique_constraints(table):
            cols = constraint.get('column_names') or []
            if cols:
                covered.add(cols[0])
        for index in db.metadata.tables[table].indexes:
            leading = [c.name for c in index.columns][:1]
            for col in leading:
                if col not in covered:
                    out.append(f'{table}.{col}')
    return sorted(set(out))


def ensure_platform_admin() -> dict[str, Any]:
    """Guarantee a platform superadmin exists, and report its state.

    The password is taken from ``PLATFORM_ADMIN_PASSWORD`` when provided,
    otherwise generated. There is deliberately no hardcoded default: a fixed
    bootstrap credential is an open door on any reachable instance. The
    generated value is logged exactly once, when the account is created.
    """
    state: dict[str, Any] = {'created': False, 'username': PLATFORM_ADMIN_USERNAME}
    try:
        from models.user import User
        from seeds.production_baseline import platform_tenant_scope

        with platform_tenant_scope() as tenant:
            existing = (
                db.session.execute(select(User).filter_by(username=PLATFORM_ADMIN_USERNAME))
                .scalars()
                .first()
            )
            if existing is not None:
                # Idempotent: never touch an account that is already there, and
                # never reset its password on a later boot.
                state['already_present'] = True
                return state

            password = resolve_admin_password()
            admin = User(
                username=PLATFORM_ADMIN_USERNAME,
                email=PLATFORM_ADMIN_EMAIL,
                full_name='Platform Administrator',
                role=PLATFORM_ADMIN_ROLE,
                is_active=True,
                tenant_id=tenant.id if tenant else None,
            )
            admin.set_password(password)
            db.session.add(admin)
            safe_commit(db.session, error_message='admin seed commit failed', reraise=True)
            state['created'] = True
            if not os.environ.get('PLATFORM_ADMIN_PASSWORD'):
                # Printed once, at WARNING, so it is findable in the boot log and
                # cannot be re-derived on a later boot.
                _log().warning(
                    'Generated %s password for %r: %s — store it now, it is not '
                    'shown again. Set PLATFORM_ADMIN_PASSWORD to choose your own.',
                    PLATFORM_ADMIN_ROLE,
                    PLATFORM_ADMIN_USERNAME,
                    password,
                )
    except Exception as exc:  # noqa: BLE001
        _log().exception('Platform admin provisioning failed: %s', exc)
        state['error'] = str(exc)
    return state


def ensure_departments() -> dict[str, Any]:
    """Seed the department catalogue for every existing tenant.

    Departments are tenant-scoped, so this runs per tenant rather than once for
    the platform: a department row carries the tenant's own context, and writing
    it under the platform tenant would hide it from the tenant that needs it.

    Three properties this has to hold, because it runs on every boot of every
    worker:

    * **Idempotent** -- matched on the department name, so a second run adds
      nothing. This is what keeps a multi-worker boot from creating duplicates.
    * **Tenant-correct** -- ``tenant_id`` is always set explicitly. The previous
      implementation in ``pricing_service.seed_departments`` left it unset, which
      an RLS-protected table either rejects or stores as NULL.
    * **Non-fatal** -- a unique violation from two workers racing is caught and
      treated as "already there", not propagated.
    """
    result: dict[str, Any] = {'tenants': 0, 'created': 0}
    try:
        # Remember the caller's binding: this function walks every tenant, and
        # leaving the session bound to the last one it touched would silently
        # replace whatever the caller had. That is the same class of regression
        # platform_tenant_scope() exists to prevent, and it makes the caller's
        # own queries return nothing afterwards.
        from flask import g

        from app.core.tenant.middleware import bind_g_tenant
        from app.core.tenant.models import Tenant
        from models.department import Department
        from utils.seed_manifest import DEFAULT_DEPARTMENTS

        had_binding = 'tenant_id' in g
        previous_g_id = g.get('tenant_id')
        previous_info = db.session.info.get('_tenant_id')
        try:
            tenants = db.session.execute(select(Tenant).order_by(Tenant.id)).scalars().all()
            result['tenants'] = len(tenants)
            for tenant in tenants:
                bind_g_tenant(tenant)
                for name, name_ar in DEFAULT_DEPARTMENTS:
                    existing = (
                        db.session.execute(select(Department).filter_by(name=name))
                        .scalars()
                        .first()
                    )
                    if existing is not None:
                        continue
                    db.session.add(
                        Department(
                            name=name,
                            name_ar=name_ar,
                            is_active=True,
                            tenant_id=tenant.id,
                        )
                    )
                try:
                    # Nested transaction: a losing race rolls back only this row.
                    with db.session.begin_nested():
                        db.session.flush()
                    result['created'] += 1
                except Exception:  # noqa: BLE001
                    db.session.rollback()
            if result['created']:
                safe_commit(db.session, error_message='department seed commit failed', reraise=True)
        finally:
            if had_binding:
                g.tenant_id = previous_g_id
            else:
                g.pop('tenant_id', None)
            if previous_info is None:
                db.session.info.pop('_tenant_id', None)
            else:
                db.session.info['_tenant_id'] = previous_info
        _log().info(
            'Departments: %d created across %d tenant(s)',
            result['created'],
            result['tenants'],
        )
    except Exception as exc:  # noqa: BLE001
        result['error'] = str(exc)
        _log().exception('Department provisioning failed: %s', exc)
    return result


def check_reference_data_readiness() -> dict[str, Any]:
    """Report whether the essential clinical reference data is present.

    A deployment that booted cleanly but has no departments is not ready, and
    nothing would say so. This turns that into an explicit, logged verdict.
    """
    from utils.seed_manifest import DEFAULT_DEPARTMENTS, ESSENTIAL_DEPARTMENTS

    outcome: dict[str, Any] = {'ok': True, 'missing_essential': []}
    try:
        from models.department import Department

        known = {name for (name,) in db.session.execute(select(Department.name)).all() if name}
        expected = {name for name, _ in DEFAULT_DEPARTMENTS}
        missing_essential = sorted(ESSENTIAL_DEPARTMENTS - known)
        outcome['missing_essential'] = missing_essential
        outcome['total_departments'] = len(known)
        outcome['unexpected'] = sorted(known - expected)
        if missing_essential:
            outcome['ok'] = False
            _log().error(
                'Clinical reference data incomplete: missing essential department(s) %s. '
                'The system cannot register visits without them.',
                missing_essential,
            )
        else:
            _log().info('Reference data ready: %d department(s) present', len(known))
    except Exception as exc:  # noqa: BLE001
        outcome['ok'] = False
        outcome['error'] = str(exc)
        _log().exception('Reference data readiness check failed: %s', exc)
    return outcome


def run_platform_bootstrap(*, quiet: bool = False) -> dict[str, Any]:
    """Run full platform bootstrap. Safe to call on every boot.

    Each step is isolated: one failure is logged and the remaining steps still
    run, because a partially seeded platform is recoverable and a server that
    will not start is not.
    """
    if os.environ.get('SKIP_PLATFORM_BOOTSTRAP', '').lower() in ('1', 'true', 'yes'):
        return {'skipped': True}

    log = _log().debug if quiet else _log().info
    summary: dict[str, Any] = {'skipped': False}

    # One loop over the manifest, so adding a dataset is a data change. The
    # three original counters keep their historical summary keys because they
    # are part of this function's published contract.
    from utils.seed_manifest import build_registry

    for dataset in build_registry():
        try:
            summary[dataset.summary_key] = dataset.provider()
        except Exception as exc:  # noqa: BLE001
            summary[f'{dataset.summary_key}_error'] = str(exc)
            _log().exception('Bootstrap step %r failed: %s', dataset.key, exc)

    log('Platform bootstrap: %s', summary)
    return summary
