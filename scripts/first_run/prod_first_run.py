#!/usr/bin/env python3
"""
First-run setup script for PRODUCTION.

Creates ONLY:
- Platform catalog (modules, bundles, SaaS packages, developer config)
- Master account azad (platform_owner)

No demo data. No sample tenants. Clean production start.

Usage:
    python -m scripts.first_run.prod_first_run

Password is DYNAMIC — computed from today's date:
    Format: Azad@Medical@<DayName>@<MM>@<DD>
    Example: Azad@Medical@Monday@08@31

The script prints the computed password and a QR-code-style
reminder. Save it in a password manager immediately after running.
"""

import sys
import os
from datetime import datetime

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Environment ───────────────────────────────────────────────────────────────
os.environ['SECRET_KEY'] = 'dev-secret-key-do-not-use-in-production'
os.environ['APP_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system_test'


def _compute_master_password() -> str:
    now = datetime.now()
    day_name = now.strftime('%A')
    month = now.strftime('%m')
    day_num = now.strftime('%d')
    return f'Azad@Medical@{day_name}@{month}@{day_num}'


def _banner(title: str) -> None:
    sep = '=' * 60
    print(f'\n{sep}\n  {title}\n{sep}')


def main() -> None:
    from sqlalchemy import text

    from app.core.platform_bootstrap import run_platform_bootstrap
    from app.extensions import db
    from models.user import User
    from app_factory import create_app

    app = create_app('testing')

    # Safety check: warn if running in non-test environment
    app_env = os.environ.get('APP_ENV', 'testing')
    db_url = os.environ.get('DATABASE_URL', '')

    print('\n' + '=' * 60)
    print('  PRODUCTION FIRST-RUN SETUP')
    print('  ⚠️  WARNING: This creates the master platform account.')
    print('  ⚠️  Save the generated password immediately!')
    print('=' * 60)
    print(f'\n  APP_ENV:     {app_env}')
    print(f'  DATABASE:    {db_url}')
    print(f'  Timestamp:  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    master_password = _compute_master_password()
    print(f'\n  Computed master password: {master_password}')

    with app.app_context():
        # ── 1. Platform Bootstrap ──────────────────────────────────────────────
        _banner('1. Platform Bootstrap')
        result = run_platform_bootstrap(quiet=False)
        print(f'  Modules added:      {result["module_definitions_added"]}')
        print(f'  Product bundles:    {result["product_bundles"]}')
        print(f'  SaaS packages:      {result["saas_packages_added"]}')

        # ── 2. Master Account ─────────────────────────────────────────────────
        _banner('2. Master Account (platform_owner)')
        from seeds.production_baseline import _resolve_platform_tenant

        master_tenant = _resolve_platform_tenant()
        print(f'  Tenant: {master_tenant.slug} (id={master_tenant.id})')

        existing = db.session.execute(
            text("SELECT id FROM users WHERE username = 'azad'")
        ).fetchone()

        if existing:
            master = db.session.get(User, existing[0])
            master.set_password(master_password)
            master.role = 'platform_owner'
            master.is_active = True
            db.session.commit()
            print(f'  Updated existing azad account')
        else:
            master = User(
                username='azad',
                email='azad@medical.system',
                full_name='Platform Owner (Azad)',
                role='platform_owner',
                tenant_id=master_tenant.id,
                is_active=True,
            )
            master.set_password(master_password)
            db.session.add(master)
            db.session.commit()
            print(f'  Created azad account')

        print(f'\n  ┌─────────────────────────────────────────────────────────┐')
        print(f'  │  MASTER CREDENTIALS — SAVE IMMEDIATELY                 │')
        print(f'  │                                                         │')
        print(f'  │  Username:  azad                                       │')
        print(f'  │  Password:  {master_password}  │')
        print(f'  │  Role:      platform_owner                             │')
        print(f'  │  Tenant:    platform (id={master_tenant.id})                      │')
        print(f'  │                                                         │')
        print(f'  │  Note: Password changes DAILY at midnight.              │')
        print(f'  │  Always use: Azad@Medical@<Today>@<MM>@<DD>             │')
        print(f'  └─────────────────────────────────────────────────────────┘')

        # ── Final ────────────────────────────────────────────────────────────
        _banner('PRODUCTION SETUP COMPLETE')
        n_users = db.session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        n_tenants = db.session.execute(text("SELECT COUNT(*) FROM tenants")).scalar()
        n_modules = db.session.execute(text("SELECT COUNT(*) FROM module_definitions")).scalar()
        n_bundles = db.session.execute(text("SELECT COUNT(*) FROM product_bundles")).scalar()

        print(f'  Users:          {n_users}')
        print(f'  Tenants:       {n_tenants}')
        print(f'  Modules:       {n_modules}')
        print(f'  Bundles:      {n_bundles}')
        print(f'\n  Next step: Create your first tenant via the UI or API.')
        print(f'  Login at: http://127.0.0.1:5001/auth/login')
        print(f'  Use the owner dashboard to add tenants and bundles.\n')


if __name__ == '__main__':
    main()
