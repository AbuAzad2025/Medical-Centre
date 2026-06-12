"""
Create a default tenant and assign all existing data to it.
Usage: python scripts/create_default_tenant.py <tenant_slug> <tenant_name>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app, db
from app.core.tenant.models import Tenant
from app.core.module.models import TenantModule
from app.core.module.registry import MODULE_REGISTRY
from models.user import User


def create_default_tenant(slug: str, name: str):
    app = create_app()
    with app.app_context():
        # Check if tenant exists
        existing = Tenant.query.filter_by(slug=slug).first()
        if existing:
            print(f"Tenant '{slug}' already exists (id={existing.id}).")
            tenant = existing
        else:
            tenant = Tenant(
                slug=slug,
                name=name,
                name_ar=name,
                contact_email="admin@example.com",
                status="active",
                storage_mode="local",
                subscription_type="perpetual",
            )
            db.session.add(tenant)
            db.session.flush()
            print(f"Created tenant '{slug}' (id={tenant.id}).")

        # Assign all existing users to this tenant
        orphaned = User.query.filter(User.tenant_id.is_(None)).all()
        for u in orphaned:
            u.tenant_id = tenant.id
        if orphaned:
            print(f"Assigned {len(orphaned)} existing users to tenant {tenant.id}.")

        # Activate all modules for the default tenant
        active_names = {m.module_name for m in TenantModule.query.filter_by(tenant_id=tenant.id, is_active=True).all()}
        from datetime import datetime, timezone
        for key in MODULE_REGISTRY:
            if key in active_names:
                continue
            tm = TenantModule(
                tenant_id=tenant.id,
                module_name=key,
                is_active=True,
                activated_at=datetime.now(timezone.utc),
            )
            db.session.add(tm)
            print(f"Activated module '{key}' for tenant {tenant.id}.")

        db.session.commit()
        print("Default tenant setup complete.")


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "default"
    name = sys.argv[2] if len(sys.argv) > 2 else "Default Medical Centre"
    create_default_tenant(slug, name)
