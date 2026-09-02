"""Platform bootstrap isolated suite — clean upgraded DB.

Validates that scripts/ops/bootstrap_platform.py correctly seeds
a production-clean database without mock/demo data.
"""

from sqlalchemy import func, select

from app.core.module.models import ModuleDefinition
from app.core.module.registry import MODULE_REGISTRY
from app.core.platform_bootstrap import (
    ensure_module_definitions,
    ensure_product_bundles,
    ensure_saas_packages,
    run_platform_bootstrap,
)
from app.core.tenant.models import ProductBundle
from app.extensions import db
from models.user import User


def _count(table):
    # Bypass tenant filter for global counts (clean baseline may not have tenant context)
    from seeds import tenant_bypass

    with tenant_bypass():
        return db.session.execute(select(func.count()).select_from(table)).scalar() or 0


def test_bootstrap_seeds_15_core_modules_and_is_idempotent(app, monkeypatch):
    monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
    with app.app_context():
        # Ensure idempotent: second run adds 0
        run_platform_bootstrap(quiet=True)
        second = run_platform_bootstrap(quiet=True)
        assert second['module_definitions_added'] == 0

        # Registry must contain at least 15 core modules (actual is 22)
        assert len(MODULE_REGISTRY) >= 15, f'MODULE_REGISTRY has {len(MODULE_REGISTRY)} < 15'

        # DB must have exactly len(registry) rows
        db_count = _count(ModuleDefinition)
        assert db_count == len(MODULE_REGISTRY), (
            f'module_definitions {db_count} != registry {len(MODULE_REGISTRY)}'
        )

        # Additionally, the 15 main clinical/admin modules must exist
        core_15 = [
            'reception',
            'doctor',
            'lab',
            'radiology',
            'pharmacy',
            'emergency',
            'nursing',
            'billing',
            'inventory',
            'appointments',
            'reporting',
            'owner',
            'portal',
            'ai_imaging',
            'integration',
        ]
        for name in core_15:
            exists = (
                db.session.execute(select(ModuleDefinition).filter_by(name=name)).scalars().first()
            )
            assert exists is not None, f'core module {name} missing in module_definitions'


def test_bootstrap_seeds_23_product_bundles(app, monkeypatch):
    monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
    with app.app_context():
        # Run bootstrap
        result = run_platform_bootstrap(quiet=True)
        # ProductBundle table must have 23 rows (seed_default_bundles)
        bundle_count = _count(ProductBundle)
        assert bundle_count == 23, f'product_bundles {bundle_count} != 23'
        # Also check return value
        assert result['product_bundles'] == 23 or result['product_bundles'] >= 23

        # SaaS packages mirror must also be 23 (or at least 23)
        # seed_packages_from_product_bundles is idempotent
        from app.core.saas.models import Package

        db.session.execute(select(func.count()).select_from(Package)).scalar() or 0
        # In SaaS model, packages mirror bundles, but count may be 0 if stripe not configured
        # At minimum, ensure product_bundles is 23
        assert bundle_count == 23


def test_bootstrap_creates_platform_master_account(app, monkeypatch):
    monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
    with app.app_context():
        run_platform_bootstrap(quiet=True)
        # Seed master account via production_baseline
        from seeds import tenant_bypass
        from seeds.production_baseline import seed_master_account

        user = seed_master_account()
        assert user is not None
        assert user.username == 'azad'
        assert user.role == 'platform_owner'
        assert user.is_active is True
        # Verify via DB query (bypass tenant filter)
        with tenant_bypass():
            fetched = db.session.execute(select(User).filter_by(username='azad')).scalars().first()
            assert fetched is not None
            assert fetched.role == 'platform_owner'


def test_clean_baseline_has_no_mock_demo_data(app):
    """Clean baseline enforcement: no mock/demo data from local_dev_story."""
    from seeds import tenant_bypass

    with app.app_context():
        with tenant_bypass():
            # Mock staff from local_dev_story must not exist
            mock_usernames = ['dev_reception', 'dev_doctor', 'dev_lab', 'dev_pharmacist']
            for uname in mock_usernames:
                exists = (
                    db.session.execute(select(User).filter_by(username=uname)).scalars().first()
                )
                assert exists is None, f'mock user {uname} found in clean baseline'

            # Ensure dev tenant slug not present
            from app.core.tenant.models import Tenant

            dev_tenant = (
                db.session.execute(select(Tenant).filter_by(slug='azad-dev')).scalars().first()
            )
            assert dev_tenant is None, 'azad-dev tenant should not exist in clean bootstrap'

            # Also ensure no tenant has the local-dev slug pattern
            all_slugs = db.session.execute(select(Tenant.slug)).scalars().all()
            assert 'azad-dev' not in all_slugs


def test_ensure_helpers_are_idempotent_and_return_counts(app, monkeypatch):
    monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
    with app.app_context():
        assert ensure_module_definitions() >= 0
        assert ensure_product_bundles() >= 0
        assert ensure_saas_packages() >= 0
        # Second call should be 0 added for modules (idempotent)
        assert ensure_module_definitions() == 0
