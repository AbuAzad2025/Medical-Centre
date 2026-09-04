"""Bundle audit: walkin_clinic (reception, doctor, billing, pharmacy)."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.module.models import TenantModule
from app.core.module.validators import can_activate_module
from app.core.tenant.models import ProductBundle, Tenant, seed_default_bundles
from app.extensions import db
from app.shared.enums import TenantStatus


def _seed_bundles_if_empty():
    if db.session.execute(select(func.count()).select_from(ProductBundle)).scalar() == 0:
        seed_default_bundles()


def test_standalone_clinic_bundle_exists(app):
    _seed_bundles_if_empty()
    with app.app_context():
        bundle = (
            db.session.execute(select(ProductBundle).filter_by(slug='walkin_clinic'))
            .scalars()
            .first()
        )
        assert bundle is not None
        assert set(bundle.get_modules()) == {'reception', 'doctor', 'billing', 'pharmacy'}


def test_standalone_clinic_activation(app):
    _seed_bundles_if_empty()
    with app.app_context():
        t = Tenant(
            slug=f'walkin-iso-{int(datetime.now(UTC).timestamp())}',
            name='Walk-in',
            contact_email='w@test.local',
            status=TenantStatus.ACTIVE,
            product_profile_code='walkin_clinic',
        )
        db.session.add(t)
        db.session.commit()
        for mod in ('reception', 'doctor', 'billing', 'pharmacy'):
            db.session.add(TenantModule(tenant_id=t.id, module_name=mod, is_active=True))
        db.session.commit()
        ok, msg = can_activate_module(t.id, 'reception')
        assert ok is True, f'reception should be allowed in walkin_clinic: {msg}'
        ok, msg = can_activate_module(t.id, 'doctor')
        assert ok is True, f'doctor should be allowed: {msg}'
