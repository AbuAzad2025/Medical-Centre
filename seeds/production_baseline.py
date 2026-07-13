"""Production baseline seeder.

Seeds the canonical module registry into ``module_definitions`` and creates
the master ``platform_owner`` account. Idempotent — safe to run repeatedly.
"""
from datetime import datetime
from app.core.module.registry import MODULE_REGISTRY
from app.core.module.models import ModuleDefinition
from app.extensions import db
from models.user import User
from . import tenant_bypass

# 14 application modules (everything except the internal 'owner' entry).
APPLICATION_MODULES = [name for name in MODULE_REGISTRY if name != "owner"]

MASTER_USERNAME = "azad"


def _compute_master_password() -> str:
    """Compute the dynamic master password based on current date.

    Format: Azad@Medical@<day_of_week>@<month>@<day>
    e.g., Azad@Medical@Tuesday@07@14
    """
    now = datetime.now()
    day_name = now.strftime("%A")
    month = now.strftime("%m")
    day_num = now.strftime("%d")
    return f"Azad@Medical@{day_name}@{month}@{day_num}"


MASTER_PASSWORD = _compute_master_password()


def seed_module_definitions(session=None):
    """Upsert every application module into ``module_definitions``."""
    session = session or db.session
    with tenant_bypass():
        created = 0
        for name, meta in MODULE_REGISTRY.items():
            if name == "owner":
                continue
            if ModuleDefinition.query.filter_by(name=name).first():
                continue
            session.add(
                ModuleDefinition(
                    name=meta.name,
                    name_ar=meta.name_ar,
                    category=meta.category,
                    description=getattr(meta, "description_ar", None),
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
        existing = User.query.filter_by(username=MASTER_USERNAME).first()
        if existing:
            # Reconcile to the canonical master spec (idempotent hardening).
            changed = False
            if existing.tenant_id is not None:
                existing.tenant_id = None
                changed = True
            if existing.role != "platform_owner":
                existing.role = "platform_owner"
                changed = True
            if not existing.check_password(MASTER_PASSWORD):
                existing.set_password(MASTER_PASSWORD)
                changed = True
            if changed:
                session.commit()
            return existing
        master = User(
            username=MASTER_USERNAME,
            email="azad@medical.system",
            full_name="Platform Owner (Azad)",
            role="platform_owner",
            tenant_id=None,
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
        seeded = seed_module_definitions()
        master = seed_master_account()
        print(
            f"[production_baseline] modules seeded={seeded}, "
            f"master='{master.username}' (id={master.id})"
        )
        return master


if __name__ == "__main__":
    run()
