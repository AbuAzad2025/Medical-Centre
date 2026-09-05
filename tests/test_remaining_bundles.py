"""Bundle audit: remaining 13 bundles content + activation + coexistence."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.core.module.models import TenantModule
from app.core.module.validators import can_activate_module
from app.core.tenant.models import ProductBundle, Tenant, seed_default_bundles
from app.extensions import db
from app.shared.enums import TenantStatus

EXPECTED = {
    'small_clinic': ['reception', 'doctor', 'billing', 'appointments'],
    'clinic_with_lab': ['reception', 'doctor', 'lab', 'billing', 'appointments'],
    'clinic_with_radiology': ['reception', 'doctor', 'radiology', 'billing', 'appointments'],
    'standalone_emergency': ['reception', 'emergency', 'doctor', 'nursing', 'billing'],
    'urgent_care': [
        'reception',
        'doctor',
        'emergency',
        'nursing',
        'billing',
        'lab',
        'radiology',
        'pharmacy',
    ],
    'diagnostic_center': ['reception', 'lab', 'radiology', 'billing', 'reporting'],
    'community_clinic': [
        'reception',
        'doctor',
        'nursing',
        'billing',
        'appointments',
        'lab',
        'pharmacy',
        'reporting',
    ],
    'nursing_home': ['reception', 'nursing', 'doctor', 'appointments', 'pharmacy', 'inventory'],
    'multi_department_center': [
        'reception',
        'doctor',
        'nursing',
        'billing',
        'appointments',
        'lab',
        'radiology',
        'pharmacy',
        'emergency',
        'reporting',
        'inventory',
    ],
    'polyclinic': [
        'reception',
        'doctor',
        'nursing',
        'billing',
        'appointments',
        'lab',
        'radiology',
        'pharmacy',
        'emergency',
        'reporting',
        'inventory',
        'portal',
    ],
    'hospital': [
        'reception',
        'doctor',
        'nursing',
        'billing',
        'appointments',
        'lab',
        'radiology',
        'pharmacy',
        'emergency',
        'reporting',
        'inventory',
        'portal',
        'ai_imaging',
        'integration',
    ],
    'billing_only': ['billing', 'appointments'],
    # Embedded Core Layer auto-provisioned (see _PRODUCT_PROFILE_SEED).
    'custom': ['billing', 'reporting'],
}


def _seed():
    if db.session.execute(select(func.count()).select_from(ProductBundle)).scalar() == 0:
        seed_default_bundles()


@pytest.mark.parametrize('slug,modules', list(EXPECTED.items()))
def test_bundle_modules(app, slug, modules):
    _seed()
    with app.app_context():
        b = db.session.execute(select(ProductBundle).filter_by(slug=slug)).scalars().first()
        assert b is not None, f'bundle {slug} missing'
        assert b.get_modules() == modules, f'{slug} modules mismatch'


def test_all_remaining_coexist(app):
    _seed()
    with app.app_context():
        slugs = set(db.session.execute(select(ProductBundle.slug)).scalars().all())
        for slug in EXPECTED:
            assert slug in slugs, f'{slug} not seeded'


@pytest.mark.parametrize('slug', ['small_clinic', 'urgent_care', 'hospital', 'billing_only'])
def test_bundle_activation_sample(app, slug):
    _seed()
    with app.app_context():
        mods = EXPECTED[slug]
        t = Tenant(
            slug=f'audit-{slug}-{int(datetime.now(UTC).timestamp())}',
            name=f'Audit {slug}',
            contact_email='a@t.local',
            status=TenantStatus.ACTIVE,
            product_profile_code=slug,
        )
        db.session.add(t)
        db.session.commit()
        for m in mods:
            db.session.add(TenantModule(tenant_id=t.id, module_name=m, is_active=True))
        db.session.commit()
        for m in mods:
            ok, _ = can_activate_module(t.id, m)
            assert ok is True, f'{m} should be allowed in {slug}'
