"""Doctor clinic with lab, with lab+radiology, and full clinic bundle audit.

Verifies all doctor-with-services bundles include billing and function correctly:
- doctor_clinic_full: reception+doctor+billing+lab+radiology+appointments+pharmacy+reporting
- clinic_with_lab_radiology: reception+doctor+lab+radiology+billing+appointments
- clinic_with_lab and clinic_with_radiology also included
"""

from sqlalchemy import func, select

from app.core.module.validators import can_activate_module
from app.core.tenant.models import ProductBundle, seed_default_bundles
from app.extensions import db


def _seed_bundles_if_empty():
    if db.session.execute(select(func.count()).select_from(ProductBundle)).scalar() == 0:
        seed_default_bundles()


class TestClinicBundleContents:
    def test_doctor_clinic_full(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='doctor_clinic_full'))
                .scalars()
                .first()
            )
            assert bundle is not None
            modules = bundle.get_modules()
            assert 'billing' in modules
            assert 'doctor' in modules
            assert 'reception' in modules
            assert 'lab' in modules
            assert 'radiology' in modules
            assert 'pharmacy' in modules

    def test_clinic_with_lab_radiology(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(
                    select(ProductBundle).filter_by(slug='clinic_with_lab_radiology')
                )
                .scalars()
                .first()
            )
            assert bundle is not None
            modules = bundle.get_modules()
            assert 'billing' in modules
            assert 'doctor' in modules
            assert 'reception' in modules
            assert 'lab' in modules
            assert 'radiology' in modules

    def test_small_clinic(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='small_clinic'))
                .scalars()
                .first()
            )
            assert bundle is not None
            assert 'billing' in bundle.get_modules()

    def test_clinic_with_lab(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='clinic_with_lab'))
                .scalars()
                .first()
            )
            assert bundle is not None
            assert 'billing' in bundle.get_modules()
            assert 'lab' in bundle.get_modules()

    def test_clinic_with_radiology(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='clinic_with_radiology'))
                .scalars()
                .first()
            )
            assert bundle is not None
            assert 'billing' in bundle.get_modules()
            assert 'radiology' in bundle.get_modules()

    def test_all_billing_modules_coexist(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            slugs = [
                'doctor_clinic_full',
                'clinic_with_lab_radiology',
                'small_clinic',
                'clinic_with_lab',
                'clinic_with_radiology',
            ]
            existing = set(db.session.execute(select(ProductBundle.slug)).scalars().all())
            for slug in slugs:
                assert slug in existing, f'{slug} not seeded'
                bundle = (
                    db.session.execute(select(ProductBundle).filter_by(slug=slug)).scalars().first()
                )
                assert 'billing' in bundle.get_modules(), f'{slug} missing billing'


class TestClinicBundleActivation:
    def test_modules_allowed(self, app):
        for slug in ('doctor_clinic_full', 'clinic_with_lab_radiology'):
            t_seed = (
                db.session.execute(select(ProductBundle).filter_by(slug=slug)).scalars().first()
            )
            if not t_seed:
                continue
            from app.core.module.models import TenantModule
            from app.core.tenant.models import Tenant
            from app.shared.enums import TenantStatus

            t = Tenant(
                slug=f'clinic-{slug}',
                name=f'Clinic {slug}',
                contact_email='test@local',
                status=TenantStatus.ACTIVE,
                product_profile_code=slug,
            )
            db.session.add(t)
            db.session.commit()
            for mod in t_seed.get_modules():
                db.session.add(TenantModule(tenant_id=t.id, module_name=mod, is_active=True))
            db.session.commit()
            from tests.tenant_context import tenant_test_context

            with tenant_test_context(app, t):
                for mod in t_seed.get_modules():
                    ok, _ = can_activate_module(t.id, mod)
                    assert ok is True, f'{slug} should allow {mod}'
            db.session.delete(t)
            db.session.commit()
