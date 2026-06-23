"""
pytest configuration and shared fixtures for Medical System tests.
"""
import os, sys, pytest

# Load .env BEFORE any imports that touch config.py (which requires SECRET_KEY)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Force testing config
os.environ['APP_ENV'] = 'testing'
os.environ['FLASK_DEBUG'] = 'false'
os.environ['SUPPRESS_LOGGING'] = '1'

# Use PostgreSQL test database if available, fallback SQLite
_test_db_url = os.environ.get('TEST_DATABASE_URL') or \
    os.environ.get('DATABASE_URL')

if not _test_db_url:
    _test_db_url = 'sqlite:///:memory:'
    # SQLite needs different engine options
else:
    os.environ['SQLALCHEMY_DATABASE_URI'] = _test_db_url

from app_factory import create_app, db as _db
from models.user import User
from models.medication import Medication, PharmacySale, PharmacySaleItem, Supplier, MedicationPurchase
from app.core.tenant.models import Tenant


@pytest.fixture(scope='session')
def app():
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        # Ensure new columns exist on existing tables (adds column if missing)
        try:
            from sqlalchemy import text
            _db.session.execute(text('ALTER TABLE tenants ADD COLUMN IF NOT EXISTS settings JSONB'))
            _db.session.execute(text(
                "ALTER TABLE pharmacy_sales ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) DEFAULT 'cash'"
            ))
            _db.session.execute(text(
                'ALTER TABLE pharmacy_sales ADD COLUMN IF NOT EXISTS card_last_digits VARCHAR(4)'
            ))
            _db.session.execute(text(
                'ALTER TABLE pharmacy_sales ADD COLUMN IF NOT EXISTS transaction_id VARCHAR(80)'
            ))
            # SaaS S0-003: exclusion constraint (not created by db.create_all)
            _db.session.execute(text('CREATE EXTENSION IF NOT EXISTS btree_gist'))
            _db.session.execute(text(
                'ALTER TABLE subscription_lines DROP CONSTRAINT IF EXISTS subscription_lines_no_base_overlap'
            ))
            _db.session.execute(text(
                "ALTER TABLE subscription_lines ADD CONSTRAINT subscription_lines_no_base_overlap "
                "EXCLUDE USING gist ("
                "tenant_id WITH =, "
                "tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)') WITH &&"
                ") WHERE (line_type = 'base' AND status IN ('scheduled', 'active'))"
            ))
            _db.session.commit()
        except Exception:
            _db.session.rollback()
        yield app
        _db.session.remove()
        try:
            _db.drop_all()
        except Exception:
            pass  # Ignore teardown errors (e.g. unnamed FK constraints on departments)


@pytest.fixture(scope='function')
def db(app):
    yield _db


@pytest.fixture(scope='function', autouse=True)
def _clear_rate_limiter(app):
    """Clear rate limiter state before each test to avoid cross-test contamination."""
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    from app.extensions import db
    try:
        from models.audit_trail import LoginAttempt
        db.session.query(LoginAttempt).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()


@pytest.fixture(scope='function', autouse=True)
def _clear_flask_login_state():
    """Clear cached Flask-Login user to prevent cross-test auth leaks.

    The session-scoped app context in the ``app`` fixture means ``g`` is
    shared across tests. Flask-Login stores the loaded user in ``g``; if a
    previous test logged in, the next test may see that user unless we clear it.
    """
    from flask import g
    try:
        g.pop('_login_user', None)
    except Exception:
        pass
    yield
    try:
        g.pop('_login_user', None)
    except Exception:
        pass


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    return app.test_cli_runner()


# ── Test data fixtures ──────────────────────────────────────────────

@pytest.fixture(scope='function')
def test_tenant(app):
    """Create a test tenant for pharmacy-shifa."""
    from app.core.tenant.models import Tenant
    t = Tenant.query.filter_by(slug='pharmacy-shifa').first()
    if not t:
        t = Tenant(
            slug='pharmacy-shifa',
            name='صيدلية الشفاء',
            contact_email='pharmacy@test.local',
            status='active',
            product_profile_code='standalone_pharmacy',
        )
        _db.session.add(t)
        _db.session.commit()
    # Reset settings to avoid cross-test contamination
    t.settings = None
    _db.session.commit()
    return t


@pytest.fixture(scope='function')
def test_user(app, test_tenant):
    """Create a pharmacist test user."""
    u = User.query.filter_by(username='pharmacist_test').first()
    if not u:
        u = User(
            username='pharmacist_test',
            email='pharmacist@test.local',
            full_name='صيدلي اختبار',
            role='pharmacist',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def test_medications(app, test_tenant):
    """Create sample medications."""
    meds_data = [
        {'trade_name': 'أموكسيسيلين', 'scientific_name': 'Amoxicillin', 'price': 15.50, 'stock': 100, 'min_stock': 20},
        {'trade_name': 'باراسيتامول', 'scientific_name': 'Paracetamol', 'price': 5.00, 'stock': 200, 'min_stock': 50},
        {'trade_name': 'ايبوبروفين', 'scientific_name': 'Ibuprofen', 'price': 8.75, 'stock': 5, 'min_stock': 10},
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
    # Clear rate limiter state before login
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'pharmacist_test',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    })
    return client


@pytest.fixture(scope='function')
def manager_user(app, test_tenant):
    """Create a manager test user."""
    u = User.query.filter_by(username='manager_test').first()
    if not u:
        u = User(
            username='manager_test',
            email='manager@test.local',
            full_name='مدير اختبار',
            role='manager',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def manager_auth_client(app, client, manager_user, test_tenant):
    """Return an authenticated test client for manager via login POST."""
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'manager_test',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    })
    return client


# ── Centralized lightweight mocks for pure-logic / workflow tests ───
class FakeSession:
    """In-memory stand-in for db.session — no engine, records side effects.

    Seed ``store`` with {id: obj} so ``get(Model, id)`` resolves; ``add`` /
    ``commit`` / ``rollback`` / ``flush`` are recorded for transactional asserts.
    """

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
def fake_session():
    """A fresh FakeSession; tests seed `.store` as needed."""
    return FakeSession()


@pytest.fixture
def patch_db_session(monkeypatch):
    """Patch app.extensions.db.session with a FakeSession and return it."""
    import app.extensions as ext

    def _apply(session=None):
        session = session or FakeSession()
        monkeypatch.setattr(ext.db, 'session', session, raising=False)
        return session

    return _apply
