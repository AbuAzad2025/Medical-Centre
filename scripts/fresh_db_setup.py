#!/usr/bin/env python3
"""Clean database setup: drop all -> migrate -> seed."""

import os
import sys

sys.path.insert(0, r'D:\recovers\data\medical')

os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault(
    'TEST_DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test'
)
os.environ.setdefault(
    'DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test'
)

import sqlalchemy as sa
from flask_migrate import upgrade as alembic_upgrade

from app.bootstrap.rbac_seed import seed_rbac_and_catalogs
from app.core.tenant.models import seed_default_bundles
from app.extensions import db
from app_factory import create_app
from seeds.production_baseline import platform_tenant_scope


def main():
    app = create_app('testing')
    with app.app_context():
        # Drop all tables with CASCADE
        insp = sa.inspect(db.engine)
        tables = insp.get_table_names(schema='public')
        if tables:
            for t in tables:
                db.session.execute(sa.text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
            db.session.commit()
        # Drop custom enum types
        enums = db.session.execute(
            sa.text(
                "SELECT typname FROM pg_type WHERE typtype = 'e' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')"
            )
        ).fetchall()
        for (ename,) in enums:
            db.session.execute(sa.text(f'DROP TYPE IF EXISTS "{ename}" CASCADE'))
        db.session.commit()

        # Run Alembic migrations
        alembic_upgrade(directory='migrations')

        # Seed RBAC & catalogs
        with platform_tenant_scope():
            seed_rbac_and_catalogs(db)

        # Seed default bundles
        with platform_tenant_scope():
            seed_default_bundles()

        from app.core.platform_bootstrap import ensure_module_definitions

        ensure_module_definitions()

        from app.core.module.models import TenantModule
        from app.core.tenant.models import ProductBundle

        bundles = db.session.execute(db.select(ProductBundle)).scalars().all()
        mods = db.session.execute(db.select(TenantModule)).scalars().all()
        print(f'Database ready: {len(bundles)} bundles, {len(mods)} tenant modules')


if __name__ == '__main__':
    main()
