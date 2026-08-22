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
# Match the CI test environment (.github/workflows/ci.yml): tests always run in
# SaaS mode with field encryption disabled, regardless of the local .env, so
# plaintext lookups on EncryptedString columns behave exactly like CI. The
# running application keeps its own .env (single-install + encryption).
os.environ['ENABLE_SAAS_MODE'] = 'true'
os.environ.pop('FIELD_ENCRYPTION_KEY', None)

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
            # P0 file-storage migration backfill (S3/MinIO columns on file_uploads).
            # db.create_all() never alters pre-existing tables; the persistent CI
            # test DB predates these columns, so backfill them like the Phase 3.2
            # audit columns below.
            _db.session.execute(
                text(
                    'ALTER TABLE file_uploads ADD COLUMN IF NOT EXISTS storage_backend '
                    "VARCHAR(20) DEFAULT 'local' NOT NULL"
                )
            )
            _db.session.execute(
                text('ALTER TABLE file_uploads ADD COLUMN IF NOT EXISTS s3_key VARCHAR(500)')
            )
            _db.session.execute(
                text('ALTER TABLE file_uploads ADD COLUMN IF NOT EXISTS s3_bucket VARCHAR(100)')
            )
            _db.session.execute(
                text('ALTER TABLE file_uploads ADD COLUMN IF NOT EXISTS s3_region VARCHAR(50)')
            )
            _db.session.execute(
                text('ALTER TABLE file_uploads ADD COLUMN IF NOT EXISTS s3_etag VARCHAR(64)')
            )
            # Model relaxed file_path to nullable (S3 rows carry the key instead).
            _db.session.execute(
                text('ALTER TABLE file_uploads ALTER COLUMN file_path DROP NOT NULL')
            )
            _db.session.execute(
                text('CREATE INDEX IF NOT EXISTS idx_file_storage ON file_uploads(storage_backend)')
            )
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
                    "ALTER TABLE pharmacy_returns ADD COLUMN IF NOT EXISTS disposition VARCHAR(20) DEFAULT 'RESTOCK' NOT NULL"
                )
            )
            # G-1: controlled-substance columns on the formulary (model change; persistent
            # test DB lags the model, so backfill here like the Phase 3.2 audit columns).
            _db.session.execute(
                text(
                    'ALTER TABLE medications ADD COLUMN IF NOT EXISTS is_controlled BOOLEAN DEFAULT FALSE'
                )
            )
            _db.session.execute(
                text('ALTER TABLE medications ADD COLUMN IF NOT EXISTS schedule VARCHAR(20)')
            )
            # Insurance Claims - activate dead model with new columns
            _db.session.execute(
                text('ALTER TABLE insurance_claims ADD COLUMN IF NOT EXISTS claim_date TIMESTAMP')
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
            # Phase 3.2 - Lab & Radiology audit columns added to models; backfill the
            # persistent test DB so SELECT/INSERT compile against the live table.
            _db.session.execute(
                text('ALTER TABLE lab_requests ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP')
            )
            _db.session.execute(
                text('ALTER TABLE lab_requests ADD COLUMN IF NOT EXISTS cancelled_by INTEGER')
            )
            _db.session.execute(
                text(
                    'ALTER TABLE radiology_requests ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP'
                )
            )
            _db.session.execute(
                text('ALTER TABLE radiology_requests ADD COLUMN IF NOT EXISTS cancelled_by INTEGER')
            )
            _db.session.execute(
                text(
                    'ALTER TABLE lab_results ADD COLUMN IF NOT EXISTS is_critical BOOLEAN DEFAULT FALSE'
                )
            )
            _db.session.execute(
                text('ALTER TABLE lab_results ADD COLUMN IF NOT EXISTS amended_by INTEGER')
            )
            _db.session.execute(
                text('ALTER TABLE lab_results ADD COLUMN IF NOT EXISTS amended_at TIMESTAMP')
            )
            _db.session.execute(
                text(
                    'ALTER TABLE radiology_results ADD COLUMN IF NOT EXISTS is_critical BOOLEAN DEFAULT FALSE'
                )
            )
            _db.session.execute(
                text('ALTER TABLE radiology_results ADD COLUMN IF NOT EXISTS amended_by INTEGER')
            )
            _db.session.execute(
                text('ALTER TABLE radiology_results ADD COLUMN IF NOT EXISTS amended_at TIMESTAMP')
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

        # Phase 3.3 - ADT columns (separate transaction: commit even if the
        # SaaS exclusion-constraint block above rolls back, so the bed/visit/
        # admission tables always expose their audit columns in the test DB).
        try:
            _db.session.execute(
                text(
                    'ALTER TABLE visits ADD COLUMN IF NOT EXISTS is_inpatient BOOLEAN DEFAULT FALSE'
                )
            )
            _db.session.execute(
                text('ALTER TABLE visits ADD COLUMN IF NOT EXISTS admission_date TIMESTAMP')
            )
            _db.session.execute(
                text('ALTER TABLE visits ADD COLUMN IF NOT EXISTS discharge_date TIMESTAMP')
            )
            _db.session.execute(text('ALTER TABLE visits ADD COLUMN IF NOT EXISTS bed_id INTEGER'))
            _db.session.execute(text('ALTER TABLE visits ADD COLUMN IF NOT EXISTS ward_id INTEGER'))
            _db.session.execute(
                text('ALTER TABLE admissions ADD COLUMN IF NOT EXISTS discharge_type VARCHAR(50)')
            )
            _db.session.execute(
                text('ALTER TABLE admissions ADD COLUMN IF NOT EXISTS length_of_stay INTEGER')
            )
            _db.session.execute(
                text('ALTER TABLE admissions ADD COLUMN IF NOT EXISTS discharge_datetime TIMESTAMP')
            )
            _db.session.execute(
                text(
                    "ALTER TABLE beds ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'AVAILABLE'"
                )
            )
            _db.session.execute(
                text('ALTER TABLE beds ADD COLUMN IF NOT EXISTS current_patient_id INTEGER')
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

    ``bind_g_tenant`` also stashes the tenant on ``db.session.info['_tenant_id']``
    (read first by ``tenant_filter._current_tenant_id``). This dict lives on the
    session-scoped session and survives ``rollback_db``'s transaction rollback,
    so a tenant bound in one test would leak into the next. Clear it.
    """
    from flask_sqlalchemy.session import Session as _FSASession

    connection = _db.engine.connect()
    transaction = connection.begin()
    _db.session.remove()

    # FSA's Session.get_bind() resolves the engine per bind-key and ignores any
    # bound connection, so force every bind onto our single connection while the
    # fixture is active. create_savepoint turns the service code's commit() calls
    # into SAVEPOINT releases; rolling back the outer transaction then discards
    # everything, keeping the session-scoped test DB pristine.
    _original_get_bind = _FSASession.get_bind
    _FSASession.get_bind = lambda _self, *_a, **_k: connection
    _db.session.configure(join_transaction_mode='create_savepoint')

    if app.config.get('ENABLE_SAAS_MODE', False):
        from tests.tenant_context import bind_tenant_on_g, ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        bind_tenant_on_g(tenant, db_session=_db.session)
        with contextlib.suppress(Exception):
            _db.session.info['_tenant_id'] = tenant.id

    try:
        yield _db
    finally:
        _FSASession.get_bind = _original_get_bind
        with contextlib.suppress(Exception):
            _db.session.remove()
        try:
            transaction.rollback()
        except Exception:
            pass
        finally:
            connection.close()
            _db.session.configure(join_transaction_mode='conditional_savepoint')


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


@pytest.fixture(scope='function')
def db(app):
    """Shared SQLAlchemy database handle (same scoped session as the app)."""
    return _db


@pytest.fixture(scope='function')
def client(app):
    # NOTE: intentionally NOT a context manager (no ``with app.test_client()``).
    # pytest-flask's ``client`` fixture enters a context manager that pushes an
    # extra app context, which corrupts the request-context stack when combined
    # with the autouse ``_saas_default_tenant_context`` (and tests) that already
    # push ``app.test_request_context()``. Returning the bare client keeps context
    # push/pop balanced. (Matches the pre-094e217 conftest definition.)
    return app.test_client()


@pytest.fixture(scope='function')
def login_as(test_tenant, db):
    """Factory fixture: ``login_as(client, username, role)`` → authenticated client."""
    from tests.tenant_context import ensure_test_user, login_test_client

    def _login(client, username, role, password='test123', **user_extra):
        user = ensure_test_user(
            db, test_tenant, username=username, role=role, password=password, **user_extra
        )
        login_test_client(client, user, test_tenant, password)
        return client

    return _login


@pytest.fixture(scope='function')
def runner(app):
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def test_user(app, test_tenant):
    """Create a pharmacist test user."""
    from flask import g

    prev_bypass = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        u = (
            _db.session.execute(select(User).filter_by(username='pharmacist_test'))
            .scalars()
            .first()
        )
        if not u:
            u = User(
                username='pharmacist_test',
                email='pharmacist@test.local',
                full_name='صيدلي اختبار',
                role='pharmacist',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            _db.session.add(u)
        else:
            u.is_active = True
            u.role = 'pharmacist'
            u.tenant_id = test_tenant.id
        u.set_password('ValidPass123!')
        _db.session.commit()
        return u
    finally:
        if prev_bypass:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)


@pytest.fixture(scope='function')
def test_medications(app, test_tenant):
    """Create sample medications."""
    from models.medication import Medication

    meds_data = [
        {
            'trade_name': 'أموكسيسيلين',
            'scientific_name': 'Amoxicillin',
            'price': 15.50,
            'stock': 100,
            'min_stock': 20,
        },
        {
            'trade_name': 'باراسيتامول',
            'scientific_name': 'Paracetamol',
            'price': 5.00,
            'stock': 200,
            'min_stock': 50,
        },
        {
            'trade_name': 'ايبوبروفين',
            'scientific_name': 'Ibuprofen',
            'price': 8.75,
            'stock': 5,
            'min_stock': 10,
        },
    ]
    meds = []
    for md in meds_data:
        m = Medication(
            tenant_id=test_tenant.id,
            trade_name=md['trade_name'],
            scientific_name=md['scientific_name'],
            dosage_form='tablet',
            strength='500mg',
            price=md['price'],
            stock_quantity=md['stock'],
            minimum_stock=md['min_stock'],
            category='general',
        )
        _db.session.add(m)
        meds.append(m)
    _db.session.commit()
    return meds


@pytest.fixture(scope='function')
def auth_client(app, client, test_user, test_tenant):
    """Return an authenticated test client for pharmacist via login POST."""
    from tests.tenant_context import login_test_client

    login_test_client(client, test_user, test_tenant)
    return client


@pytest.fixture(scope='function')
def manager_user(app, test_tenant):
    """Create a manager test user."""
    from flask import g

    prev_bypass = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        u = _db.session.execute(select(User).filter_by(username='manager_test')).scalars().first()
        if not u:
            u = User(
                username='manager_test',
                email='manager@test.local',
                full_name='مدير اختبار',
                role='manager',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            _db.session.add(u)
        else:
            u.is_active = True
            u.role = 'manager'
            u.tenant_id = test_tenant.id
        u.set_password('ValidPass123!')
        _db.session.commit()
        return u
    finally:
        if prev_bypass:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)


@pytest.fixture(scope='function')
def manager_auth_client(app, client, manager_user, test_tenant):
    """Return an authenticated test client for manager via login POST."""
    from tests.tenant_context import login_test_client

    login_test_client(client, manager_user, test_tenant)
    return client


class FakeSession:
    """In-memory stand-in for db.session — no engine, records side effects."""

    def __init__(self, store=None):
        self.store = dict(store or {})
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    def get(self, model, ident):
        return self.store.get(ident)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def flush(self):
        self.flushes += 1


@pytest.fixture
def patch_db_session(monkeypatch):
    """Patch app.extensions.db.session with a FakeSession and return it."""
    import app.extensions as ext

    def _apply(session=None):
        session = session or FakeSession()
        monkeypatch.setattr(ext.db, 'session', session, raising=False)
        return session

    return _apply


@pytest.fixture(scope='function', autouse=True)
def _clear_rate_limiter(app):
    """Clear rate limiter state before each test to avoid cross-test contamination."""
    from sqlalchemy import delete

    from app.core.rate_limiter import _idempotency_locks, _shared_store
    from models.audit_trail import LoginAttempt
    from services.sms_service import SMSService

    _shared_store.clear()
    _idempotency_locks.clear()
    SMSService.clear_all_otp_state()
    try:
        _db.session.execute(delete(LoginAttempt))
        _db.session.commit()
    except Exception:
        _db.session.rollback()


@pytest.fixture(scope='function', autouse=True)
def _clear_audit_context():
    from app.core.audit.audit_context import set_audit_context

    set_audit_context(actor_id=None, ip_address=None, request_id=None, tenant_id=None)
    yield
    set_audit_context(actor_id=None, ip_address=None, request_id=None, tenant_id=None)


@pytest.fixture(scope='function', autouse=True)
def _clear_flask_login_state():
    """Clear cached Flask auth/tenant/ghost state to prevent cross-test leaks."""
    from flask import g

    _state_keys = (
        '_login_user',
        'current_user',
        'current_tenant',
        'tenant_id',
        'tenant_slug',
        'ghost_mode',
        'ghost_actor_id',
        'enabled_modules',
        'product_profile',
        'feature_flags',
        '_tenant_filter_bypass',
        'original_user',
    )

    def _clear():
        for _k in _state_keys:
            with contextlib.suppress(Exception):
                g.pop(_k, None)
        try:
            _db.session.info.pop('_tenant_id', None)
            _db.session.execute(_db.text('RESET app.tenant_id'))
        except Exception:
            pass

    _clear()
    yield
    _clear()


@pytest.fixture(scope='function', autouse=True)
def _saas_default_tenant_context(app, request, monkeypatch):
    """In SaaS mode, bind the default test tenant to ``g`` for service-layer tests.

    HTTP tests still exercise real middleware; this covers direct ORM/service calls
    outside an active request. Tests that require *no* tenant must opt out via
    ``@pytest.mark.no_tenant_context``.
    """
    clear_tenant_g()
    _db.session.info.pop('_tenant_id', None)
    if not app.config.get('ENABLE_SAAS_MODE', False):
        yield
        clear_tenant_g()
        return
    if request.node.get_closest_marker('no_tenant_context'):
        yield
        clear_tenant_g()
        return

    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_update',
        lambda *_a, **_k: None,
    )

    tenant = ensure_default_test_tenant(app)
    with app.test_request_context():
        from tests.tenant_context import bind_tenant_on_g as _bind_tenant

        _bind_tenant(tenant, db_session=_db.session)
        yield
    clear_tenant_g()


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


def ensure_default_test_tenant(app: 'Flask') -> Tenant:
    """Return (or create) the shared default tenant used by SaaS-mode tests."""
    from tests.tenant_context import ensure_default_test_tenant as _ensure

    return _ensure(app)


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
