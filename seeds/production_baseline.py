"""Production baseline seeder.

Seeds the canonical module registry into ``module_definitions`` and creates
the master ``platform_owner`` account. Idempotent — safe to run repeatedly.
"""

from datetime import datetime

from sqlalchemy import select

from app.core.module.models import ModuleDefinition
from app.core.module.registry import MODULE_REGISTRY
from app.core.tenant.models import Tenant
from app.extensions import db
from models.user import User

from . import tenant_bypass

# 14 application modules (everything except the internal 'owner' entry).
APPLICATION_MODULES = [name for name in MODULE_REGISTRY if name != 'owner']

MASTER_USERNAME = 'azad'

PLATFORM_TENANT_SLUG = 'platform'
PLATFORM_TENANT_NAME = 'Platform'


def _resolve_platform_tenant():
    """Return the tenant that owns the master platform account.

    Prefers the currently-bound tenant context, then the first existing tenant,
    and finally creates a dedicated ``platform`` tenant on a fresh database —
    so the master account always satisfies the NOT NULL ``tenant_id`` contract.
    """
    from flask import g

    tid = g.get('tenant_id') or db.session.info.get('_tenant_id')
    if tid is not None:
        tenant = (
            db.session.execute(select(Tenant).filter_by(id=tid)).scalars().first()
        )
        if tenant is not None:
            return tenant
    tenant = (
        db.session.execute(select(Tenant).order_by(Tenant.id)).scalars().first()
    )
    if tenant is not None:
        return tenant
    tenant = Tenant(
        slug=PLATFORM_TENANT_SLUG,
        name=PLATFORM_TENANT_NAME,
        contact_email='platform@medical.system',
        status='active',
        product_profile_code='multi_department_center',
    )
    db.session.add(tenant)
    db.session.flush()
    return tenant


def _compute_master_password() -> str:
    """Compute the dynamic master password based on current date.

    Format: Azad@Medical@<day_of_week>@<month>@<day>
    e.g., Azad@Medical@Tuesday@07@14
    """
    now = datetime.now()
    day_name = now.strftime('%A')
    month = now.strftime('%m')
    day_num = now.strftime('%d')
    return f'Azad@Medical@{day_name}@{month}@{day_num}'


MASTER_PASSWORD = _compute_master_password()


def seed_module_definitions(session=None):
    """Upsert every application module into ``module_definitions``."""
    session = session or db.session
    with tenant_bypass():
        created = 0
        for name, meta in MODULE_REGISTRY.items():
            if name == 'owner':
                continue
            if db.session.execute(select(ModuleDefinition).filter_by(name=name)).scalars().first():
                continue
            session.add(
                ModuleDefinition(
                    name=meta.name,
                    name_ar=meta.name_ar,
                    category=meta.category,
                    description=getattr(meta, 'description_ar', None),
                    is_active=True,
                )
            )
            created += 1
        session.commit()
    return created


def seed_master_account(session=None):
    """Create the platform-owner master account (idempotent)."""
    session = session or db.session
    with tenant_bypass():
        existing = (
            db.session.execute(select(User).filter_by(username=MASTER_USERNAME)).scalars().first()
        )
        if existing:
            changed = False
            if existing.role != 'platform_owner':
                existing.role = 'platform_owner'
                changed = True
            if not existing.check_password(MASTER_PASSWORD):
                existing.set_password(MASTER_PASSWORD)
                changed = True
            if changed:
                session.commit()
            return existing
        master = User(
            username=MASTER_USERNAME,
            email='azad@medical.system',
            full_name='Platform Owner (Azad)',
            role='platform_owner',
            tenant_id=_resolve_platform_tenant().id,
            is_active=True,
        )
        master.set_password(MASTER_PASSWORD)
        session.add(master)
        session.commit()
        return master


def run(app=None):
    """Standalone entry point: ``python -m seeds.production_baseline``."""
    if app is None:
        from app_factory import create_app

        app = create_app()
    with app.app_context():
        seed_module_definitions()
        return seed_master_account()


if __name__ == '__main__':
    run()
