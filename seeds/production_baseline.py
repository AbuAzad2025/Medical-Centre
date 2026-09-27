"""Production baseline seeder.

Seeds the canonical module registry into ``module_definitions`` and creates
the master ``platform_owner`` account. Idempotent — safe to run repeatedly.
"""

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

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


def _bind_seed_tenant(tenant) -> None:
    """Bind *tenant* as the active context for the current transaction.

    Seeding runs outside a request, so nothing has set ``g.tenant_id``. The ORM
    tenant filter re-asserts ``app.tenant_id`` before every statement from
    ``g``/``session.info``; with both empty it asserts the empty string, and the
    ``users``/``permissions``/``roles`` RLS policies then reject the very rows
    this seeder is inserting. Binding makes the insert admissible and keeps the
    fail-closed guarantee intact (rows still cannot cross tenants).
    """
    from flask import g

    g.tenant_id = tenant.id
    g.current_tenant = tenant
    g.tenant_slug = tenant.slug
    db.session.info['_tenant_id'] = tenant.id
    db.session.execute(
        text("SELECT set_config('app.tenant_id', :tid, false)"),
        {'tid': str(tenant.id)},
    )


@contextmanager
def platform_tenant_scope():
    """Bind the platform tenant for the duration of a seed operation, then restore.

    Writing a row into an RLS-protected table requires the session GUC to equal
    that row's ``tenant_id``, so seeding must bind a tenant. It must NOT leave
    that binding behind: ``g.tenant_id`` / ``session.info['_tenant_id']`` drive
    the ORM tenant filter for the rest of the process, and a caller that already
    had a tenant bound (a test fixture, a request, a tenant-provisioning flow)
    would silently have it replaced by the platform tenant. That regression
    made every other tenant's rows invisible and broke duplicate-patient
    detection.

    Usage::

        with platform_tenant_scope() as tenant:
            ...  # writes here are attributed to the platform tenant
        # previous tenant context is fully restored here
    """
    from flask import g

    had_g = 'tenant_id' in g
    prev_g_id = g.get('tenant_id')
    prev_current = g.get('current_tenant')
    prev_slug = g.get('tenant_slug')
    prev_info = db.session.info.get('_tenant_id')

    tenant = _resolve_platform_tenant()
    _bind_seed_tenant(tenant)
    try:
        yield tenant
    finally:
        if had_g:
            g.tenant_id = prev_g_id
        else:
            g.pop('tenant_id', None)
        g.current_tenant = prev_current
        g.tenant_slug = prev_slug
        if prev_info is None:
            db.session.info.pop('_tenant_id', None)
        else:
            db.session.info['_tenant_id'] = prev_info
        # Re-assert the restored tenant (or clear it) so the next statement
        # evaluates the policies against the right tenant.
        try:
            if prev_info is None:
                db.session.execute(text('RESET app.tenant_id'))
            else:
                db.session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, false)"),
                    {'tid': str(prev_info)},
                )
        except Exception:
            db.session.rollback()


def _resolve_platform_tenant():
    """Return the tenant that owns the master platform account.

    Prefers the currently-bound tenant context, then the first existing tenant,
    and finally creates a dedicated ``platform`` tenant on a fresh database —
    so the master account always satisfies the NOT NULL ``tenant_id`` contract.
    The resolved tenant is bound into the session (see ``_bind_seed_tenant``).
    """
    from flask import g

    tid = g.get('tenant_id') or db.session.info.get('_tenant_id')
    if tid is not None:
        tenant = db.session.execute(select(Tenant).filter_by(id=tid)).scalars().first()
        if tenant is not None:
            _bind_seed_tenant(tenant)
            return tenant
    tenant = db.session.execute(select(Tenant).order_by(Tenant.id)).scalars().first()
    if tenant is not None:
        _bind_seed_tenant(tenant)
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
    _bind_seed_tenant(tenant)
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
        try:
            session.commit()
        except IntegrityError:
            # ``users`` enforces UNIQUE (tenant_id, username). The pre-check
            # above runs through the tenant-filtered ORM, so it can miss a row
            # that already exists for this tenant when the platform bootstrap
            # and this seeder run in the same process. Re-read and converge
            # instead of aborting the whole first-run.
            session.rollback()
            existing = (
                db.session.execute(select(User).filter_by(username=MASTER_USERNAME))
                .scalars()
                .first()
            )
            if existing is None:
                raise
            return existing
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
