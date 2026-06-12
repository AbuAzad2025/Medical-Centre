"""
CLI to create a new tenant with chosen modules and admin user.

Usage:
  python scripts/setup_tenant.py \
    --slug acme-clinic \
    --name "Acme Medical Clinic" \
    --email admin@acme.com \
    --modules reception,doctor,lab,pharmacy \
    --plan perpetual \
    --admin-user admin \
    --admin-pass SecurePass123!
"""
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app, db
from app.core.tenant.models import Tenant
from app.core.module.models import TenantModule
from app.core.module.registry import MODULE_REGISTRY
from app.core.module.validators import validate_reception_required
from models.user import User


def setup_tenant(args):
    app = create_app()
    with app.app_context():
        # Create tenant
        t = Tenant.query.filter_by(slug=args.slug).first()
        if t:
            print(f"Tenant '{args.slug}' already exists (id={t.id}).")
            return

        t = Tenant(
            slug=args.slug,
            name=args.name,
            name_ar=args.name,
            contact_email=args.email,
            domain=args.domain,
            subdomain=args.subdomain,
            status="active",
            storage_mode=args.storage,
            subscription_type=args.plan,
            subscription_start=datetime.now(timezone.utc).date(),
            subscription_end=(datetime.now(timezone.utc) + timedelta(days=365 * 10)).date() if args.plan == "perpetual" else None,
        )
        db.session.add(t)
        db.session.flush()
        print(f"Created tenant '{args.slug}' (id={t.id}).")

        # Validate and activate modules
        modules = [m.strip() for m in args.modules.split(",")]
        try:
            validate_reception_required(t.id, modules)
        except Exception as e:
            print(f"Validation error: {e}")
            db.session.rollback()
            sys.exit(1)

        for mod in modules:
            if mod not in MODULE_REGISTRY:
                print(f"Warning: unknown module '{mod}', skipping.")
                continue
            tm = TenantModule(
                tenant_id=t.id,
                module_name=mod,
                is_active=True,
                activated_at=datetime.now(timezone.utc),
            )
            db.session.add(tm)
            print(f"  Activated module: {mod}")

        # Create admin user
        if args.admin_user and args.admin_pass:
            if User.query.filter_by(username=args.admin_user, tenant_id=t.id).first():
                print(f"Admin user '{args.admin_user}' already exists.")
            else:
                admin = User(
                    tenant_id=t.id,
                    username=args.admin_user,
                    email=args.email,
                    full_name="Admin",
                    role="admin",
                    is_active=True,
                )
                admin.set_password(args.admin_pass)
                db.session.add(admin)
                print(f"  Created admin user: {args.admin_user}")

        db.session.commit()
        print(f"\nTenant '{args.slug}' is ready!")
        print(f"  Access URL:")
        if t.subdomain:
            print(f"    https://{t.subdomain}.azad.com")
        if t.domain:
            print(f"    https://{t.domain}")
        print(f"    https://yourdomain.com/t/{t.slug}/")


def main():
    parser = argparse.ArgumentParser(description="Create a new tenant")
    parser.add_argument("--slug", required=True, help="Tenant slug (unique identifier)")
    parser.add_argument("--name", required=True, help="Tenant display name")
    parser.add_argument("--email", required=True, help="Contact email")
    parser.add_argument("--modules", required=True, help="Comma-separated module names")
    parser.add_argument("--plan", default="monthly", choices=["perpetual", "monthly", "yearly"])
    parser.add_argument("--storage", default="local", choices=["cloud", "local", "hybrid"])
    parser.add_argument("--domain", default=None, help="Dedicated domain")
    parser.add_argument("--subdomain", default=None, help="Subdomain (e.g. acme)")
    parser.add_argument("--admin-user", default=None, help="Admin username")
    parser.add_argument("--admin-pass", default=None, help="Admin password")
    args = parser.parse_args()
    setup_tenant(args)


if __name__ == "__main__":
    main()
