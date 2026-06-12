"""
One-command platform setup:
  1. Run DB migrations
  2. Seed module definitions
  3. Create default tenant
  4. Seed permissions and roles
  5. Create admin user (from env)

Usage: python scripts/setup_platform.py
Required env: SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup():
    from app_factory import create_app, db
    from flask_migrate import upgrade

    app = create_app()
    with app.app_context():
        print("[1/5] Running migrations...")
        upgrade()
        print("Migrations applied.")

        print("[2/5] Seeding module definitions...")
        from scripts.seed_modules import seed as seed_mods
        seed_mods()

        print("[3/5] Creating default tenant...")
        from scripts.create_default_tenant import create_default_tenant
        create_default_tenant("default", "Default Medical Centre")

        print("[4/5] Seeding permissions and roles...")
        try:
            from models.permissions import create_default_permissions, create_default_roles, assign_super_admin_permissions
            create_default_permissions()
            create_default_roles()
            assign_super_admin_permissions()
            print("Permissions and roles seeded.")
        except Exception as e:
            print(f"Permission seed warning: {e}")

        print("[5/5] Creating admin user...")
        from seeds.create_users import create_users
        cnt = create_users([])
        print(f"Admin user creation result: {cnt}")

        print("\nPlatform setup complete!")


if __name__ == "__main__":
    setup()
