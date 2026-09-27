#!/usr/bin/env python3
"""
First-run setup script for PRODUCTION.

Creates ONLY:
- Platform catalog (modules, bundles, SaaS packages, developer config)
- Storage directories
- The platform superadmin account

No demo data. No sample tenants. Clean production start.

Usage:
    python -m scripts.first_run.prod_first_run

Password handling:
    The master account is created by the shared bootstrap engine
    (app.core.platform_bootstrap.ensure_platform_admin). It reads
    PLATFORM_ADMIN_PASSWORD if you set it, otherwise it generates a random
    password and logs it exactly once, at creation. An account that already
    exists is never reset.

    An earlier version derived the password from the current date
    (Azad@Medical@<DayName>@<MM>@<DD>) and rewrote it on every run. That made
    the platform owner credential reconstructable by anyone who knew the
    install date, so it was removed rather than kept as an option.
"""

import os
import sys
from datetime import datetime

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Environment ───────────────────────────────────────────────────────────────
os.environ['SECRET_KEY'] = 'dev-secret-key-do-not-use-in-production'
os.environ['APP_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system_test'


def _banner(title: str) -> None:
    sep = '=' * 60
    print(f'\n{sep}\n  {title}\n{sep}')


def main() -> None:
    from sqlalchemy import text

    from app.core.platform_bootstrap import run_platform_bootstrap
    from app.extensions import db
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

        # Delegated to the single bootstrap engine, which generates a random
        # password, logs it once on creation, and never touches an account that
        # already exists. The previous implementation derived the password from
        # today's date and rewrote it on every run, so the platform owner
        # credential could be reconstructed by anyone who knew the install date.
        from app.core.platform_bootstrap import PLATFORM_ADMIN_USERNAME, ensure_platform_admin

        admin_state = ensure_platform_admin()
        if admin_state.get('error'):
            print(f'  ! Admin provisioning failed: {admin_state["error"]}')
        elif admin_state.get('already_present'):
            print(f'  Account {PLATFORM_ADMIN_USERNAME!r} already exists; password unchanged.')
        else:
            print(f'  Created {PLATFORM_ADMIN_USERNAME!r}; its password is in the log above.')

        # ── Final ────────────────────────────────────────────────────────────
        _banner('PRODUCTION SETUP COMPLETE')
        n_users = db.session.execute(text('SELECT COUNT(*) FROM users')).scalar()
        n_tenants = db.session.execute(text('SELECT COUNT(*) FROM tenants')).scalar()
        n_modules = db.session.execute(text('SELECT COUNT(*) FROM module_definitions')).scalar()
        n_bundles = db.session.execute(text('SELECT COUNT(*) FROM product_bundles')).scalar()

        print(f'  Users:          {n_users}')
        print(f'  Tenants:       {n_tenants}')
        print(f'  Modules:       {n_modules}')
        print(f'  Bundles:      {n_bundles}')
        print('\n  Next step: Create your first tenant via the UI or API.')
        print('  Login at: http://127.0.0.1:5001/auth/login')
        print('  Use the owner dashboard to add tenants and bundles.\n')


if __name__ == '__main__':
    main()
