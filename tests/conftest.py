"""
pytest configuration and shared fixtures for Medical System tests.
"""

import contextlib
import os
import sys
from pathlib import Path

import pytest
from flask import Flask, g, jsonify
from sqlalchemy import select, text

# Load .env BEFORE any imports that touch config.py (which requires SECRET_KEY)
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# Force testing config
os.environ['APP_ENV'] = 'testing'
os.environ['FLASK_DEBUG'] = 'false'
os.environ['SUPPRESS_LOGGING'] = '1'
os.environ['SKIP_PLATFORM_BOOTSTRAP'] = '1'
os.environ['RLS_BYPASS_ALLOWED'] = '1'

from app.core.tenant.models import Tenant
from app.extensions import db as _db
from app.shared.tenant_filter import TenantIsolationError
from app_factory import create_app
from models.user import User


@pytest.fixture(scope='session')
def app():
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        # Ensure new columns exist on existing tables (adds column if missing)
        try:
            _db.session.execute(text('ALTER TABLE tenants ADD COLUMN IF NOT EXISTS settings JSONB'))
            _db.session.execute(
                text(
                    "ALTER TABLE pharmacy_sales ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) DEFAULT 'cash'"
                )
            )
            _db.session.execute(
                text(
                    'ALTER TABLE pharmacy_sales ADD COLUMN IF NOT EXISTS card_last_digits VARCHAR(4)'
                )
            )
            _db.session.execute(
                text(
                    'ALTER TABLE pharmacy_sales ADD COLUMN IF NOT EXISTS transaction_id VARCHAR(80)'
                )
            )
            _db.session.execute(
                text('ALTER TABLE vital_signs ADD COLUMN IF NOT EXISTS visit_id INTEGER')
            )
            _db.session.execute(
                text(
                    'ALTER TABLE pharmacy_returns ADD COLUMN IF NOT EXISTS disposition VARCHAR(20) DEFAULT \'RESTOCK\' NOT NULL'
                )
            )
            # Insurance Claims - activate dead model with new columns
            _db.session.execute(
                text(
                    'ALTER TABLE insurance_claims ADD COLUMN IF NOT EXISTS claim_date TIMESTAMP'
                )
            )
            _db.session.execute(
                text(
                    'ALTER TABLE insurance_claims ADD COLUMN IF NOT EXISTS patient_share_amount NUMERIC(12, 2) DEFAULT 0'
                )
            )
            _db.session.execute(
                text(
                    'ALTER TABLE insurance_claims ADD COLUMN IF NOT EXISTS insurance_share_amount NUMERIC(12, 2) DEFAULT 0'
                )
            )
            _db.session.execute(
                text(
                    'ALTER TABLE insurance_claims ADD COLUMN IF NOT EXISTS adjudication_notes TEXT'
                )
            )
            # SaaS S0-003: exclusion constraint (not created by db.create_all)
            _db.session.execute(text('CREATE EXTENSION IF NOT EXISTS btree_gist'))
            _db.session.execute(
                text(
                    'ALTER TABLE subscription_lines DROP CONSTRAINT IF EXISTS subscription_lines_no_base_overlap'
                )
            )
            _db.session.execute(
                text(
                    'ALTER TABLE subscription_lines ADD CONSTRAINT subscription_lines_no_base_overlap '
                    'EXCLUDE USING gist ('
                    'tenant_id WITH =, '
                    "tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)') WITH &&"
                    ") WHERE (line_type = 'base' AND status IN ('scheduled', 'active'))"
                )
            )
            # Ghost Mode: permit the 'IMPERSONATE' audit action on existing DBs
            _db.session.execute(
                text('ALTER TABLE audit_trails DROP CONSTRAINT IF EXISTS chk_action')
            )
            _db.session.execute(
                text(
                    'ALTER TABLE audit_trails ADD CONSTRAINT chk_action CHECK '
                    "(action IN ('create', 'update', 'delete', 'view', 'login', 'logout', "
                    "'export', 'import', 'backup', 'restore', 'security', 'login_failed', "
                    "'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access', "
                    "'APPROVE', 'REJECT', 'IMPERSONATE'))"
                )
            )
            _db.session.commit()
        except Exception:
            _db.session.rollback()

        # Register test routes that need to be available before any requests
        from utils.exceptions import IdempotencyError, ModuleNotEnabledError, TenantContextError

        @app.route('/test/module-error')
        def trigger_module_error():
            raise ModuleNotEnabledError('lab', 'Lab module is disabled')

        @app.route('/test/module-error-html')
        def trigger_module_error_html():
            raise ModuleNotEnabledError('radiology')

        @app.route('/test/tenant-iso-error')
        def trigger_tenant_iso_error():
            raise TenantIsolationError('Cross-tenant access blocked')

        @app.route('/test/tenant-ctx-error')
        def trigger_tenant_ctx_error():
            raise TenantContextError('Tenant context required')

        @app.route('/test/perm-error')
        def trigger_perm_error():
            raise PermissionError('Cross-tenant access denied')

        @app.route('/test/idempotency-error')
        def trigger_idem_error():
            raise IdempotencyError('Duplicate request')

        @app.route('/test/idempotency-error-html')
        def trigger_idem_error_html():
            raise IdempotencyError()

        @app.route('/test/g-trace')
        def check_g_trace():
            return jsonify(trace_id=getattr(g, 'trace_id', None))

        @app.route('/test/log-trace')
        def log_something():
            app.logger.info('Test log message with trace')
            return 'ok'

        # Ghost Mode test route - now registered in app_factory.py, not here
        yield app
        _db.session.remove()
        with contextlib.suppress(Exception):
            _db.drop_all()


@pytest.fixture(scope='function')
def rollback_db(app):
    """Transactional isolation: every write is rolled back after the test.

    Binds the shared scoped ``db.session`` to a single connection whose outer
    transaction we roll back on teardown. ``join_transaction_mode='create_savepoint'``
    (SQLAlchemy 2.0) turns the service code's ``commit()`` calls into SAVEPOINT
    releases instead of real commits, so destructive ``seed_*``/``cleanup_*``/
    ``purge_*`` service methods can be exercised without polluting the
    session-scoped test database. ``Model.query`` follows because it resolves
    through the same scoped session we reconfigure here.
    """
    conn = _db.engine.connect()
    txn = conn.begin()
    conn.begin_nested()

    @contextlib.contextmanager
    def _force_rollback():
        try:
            yield
        finally:
            _db.session.rollback()

    _db.session = _db.session_maker(bind=conn)
    _db.session.begin_nested()

    @contextlib.contextmanager
    def _nested_savepoint():
        sp = conn.begin_nested()
        try:
            yield
        except Exception:
            sp.rollback()
            raise
        else:
            sp.commit()

    _db.session.begin_nested = _nested_savepoint

    try:
        yield _db
    finally:
        txn.rollback()
        conn.close()


# Test data fixtures


@pytest.fixture(scope='function')
def test_tenant(app):
    """Create a test tenant for pharmacy-shifa with all modules active (SaaS CI)."""
    from tests.tenant_context import DEFAULT_TEST_TENANT_SLUG, ensure_default_test_tenant

    ensure_default_test_tenant(app)
    t = (
        _db.session.execute(select(Tenant).filter_by(slug=DEFAULT_TEST_TENANT_SLUG))
        .scalars()
        .first()
    )
    if t.settings is None:
        t.settings = {}
    if 'modules' not in t.settings:
        t.settings['modules'] = {}
    for module_name in [
        'reception',
        'doctor',
        'lab',
        'radiology',
        'pharmacy',
        'emergency',
        'nursing',
        'billing',
        'inventory',
        'reporting',
        'appointments',
        'owner',
        'portal',
        'ai_imaging',
        'accounting',
        'admin',
        'manager',
        'dicom',
    ]:
        t.settings['modules'][module_name] = True
    _db.session.commit()
    return t


# ──────────────────────────────────────────────────────────────────────────────
# Ghost mode helpers (moved from inline definition in test_ghost_mode.py)
# ──────────────────────────────────────────────────────────────────────────────

_TENANT_GHOST_KEYS = (
    '_login_user',
    'current_user',
    'current_tenant',
    'ghost_mode',
    'original_user',
)


def clear_tenant_g() -> None:
    """Remove tenant-related keys from Flask ``g`` (shared session app context in tests)."""
    for key in _TENANT_GHOST_KEYS:
        g.pop(key, None)


def ensure_default_test_tenant(app: 'Flask') -> None:
    """Return (or create) the shared default tenant used by SaaS-mode tests."""
    from tests.tenant_context import ensure_default_test_tenant as _ensure

    _ensure(app)


def bind_tenant_on_g(tenant, *, db_session=None) -> None:
    """Set Flask ``g`` tenant fields and optional PostgreSQL RLS session var."""
    g.current_tenant = tenant
    g.tenant_id = tenant.id
    g.tenant_slug = tenant.slug
    if db_session:
        db_session.execute(text(f"SET LOCAL app.current_tenant = '{tenant.id}'"))


def login_test_client(client, user, tenant, password: str = 'ValidPass123!') -> None:
    """POST /auth/login and ensure SaaS session carries tenant context."""
    resp = client.post(
        '/auth/login',
        data={'username': user.username, 'password': password},
        follow_redirects=True,
    )
    assert resp.status_code == 200, f'Login failed: {resp.status_code}'
    with client.session_transaction() as sess:
        sess['tenant_id'] = tenant.id


def ensure_test_user(
    db, tenant, *, username: str, role: str, password: str = 'ValidPass123!', **extra
):
    """Create a user if it doesn't exist, or return existing one."""

    u = db.session.execute(select(User).filter_by(username=username)).scalars().first()
    if not u:
        u = User(
            username=username,
            email=f'{username}@example.com',
            full_name=username,
            role=role,
            is_active=True,
            tenant_id=tenant.id,
            **extra,
        )
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
    return u


@contextlib.contextmanager
def tenant_test_context(app: 'Flask', tenant=None, *, bypass: bool = False):
    """Establish tenant context for DB operations in SaaS mode tests."""
    if bypass:
        yield
        return
    if tenant is None:
        from tests.tenant_context import DEFAULT_TEST_TENANT_SLUG, ensure_default_test_tenant

        ensure_default_test_tenant(app)
        tenant = (
            _db.session.execute(select(Tenant).filter_by(slug=DEFAULT_TEST_TENANT_SLUG))
            .scalars()
            .first()
        )
    with app.app_context():
        bind_tenant_on_g(tenant, db_session=_db.session)
        try:
            yield
        finally:
            clear_tenant_g()


# Make fixtures available
pytest.fixture(scope='function')
def test_db(app):
    """Legacy alias for rollback_db."""
    return rollback_db(app)
