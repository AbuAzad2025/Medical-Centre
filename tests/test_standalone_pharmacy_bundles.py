"""Bundle audit: standalone_pharmacy (pharmacy, inventory, billing)."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.module.models import TenantModule
from app.core.module.validators import can_activate_module
from app.core.tenant.models import ProductBundle, Tenant, seed_default_bundles
from app.extensions import db
from app.shared.enums import TenantStatus


def _seed():
    if db.session.execute(select(func.count()).select_from(ProductBundle)).scalar() == 0:
        seed_default_bundles()


def _unique_slug(prefix):
    return f'{prefix}-{int(datetime.now(UTC).timestamp())}'


def test_bundle_exists(app):
    _seed()
    with app.app_context():
        b = (
            db.session.execute(select(ProductBundle).filter_by(slug='standalone_pharmacy'))
            .scalars()
            .first()
        )
        assert b is not None
        assert set(b.get_modules()) == {'pharmacy', 'inventory', 'billing'}


def test_activation(app):
    _seed()
    with app.app_context():
        t = Tenant(
            slug=_unique_slug('st-ph'),
            name='Standalone Pharmacy',
            contact_email='sp@t.local',
            status=TenantStatus.ACTIVE,
            product_profile_code='standalone_pharmacy',
        )
        db.session.add(t)
        db.session.commit()
        for m in ('pharmacy', 'inventory', 'billing'):
            db.session.add(TenantModule(tenant_id=t.id, module_name=m, is_active=True))
        db.session.commit()
        for m in ('pharmacy', 'inventory', 'billing'):
            ok, _ = can_activate_module(t.id, m)
            assert ok is True, f'{m} should be allowed in standalone_pharmacy'


def test_pharmacy_blocked_in_other_bundles(app):
    _seed()
    with app.app_context():
        t = Tenant(
            slug=_unique_slug('lab-x'),
            name='Lab',
            contact_email='l@t.local',
            status=TenantStatus.ACTIVE,
            product_profile_code='standalone_lab',
        )
        db.session.add(t)
        db.session.commit()
        for m in ('lab', 'billing', 'reporting'):
            db.session.add(TenantModule(tenant_id=t.id, module_name=m, is_active=True))
        db.session.commit()
        ok, err = can_activate_module(t.id, 'pharmacy')
        assert ok is False
        assert 'not included' in (err or '').lower()
