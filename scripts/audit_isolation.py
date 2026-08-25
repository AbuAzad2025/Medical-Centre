"""Verify tenant isolation + RLS enforcement at DB level."""

import os
import sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
os.environ['APP_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system_test'

from sqlalchemy import text

from app.extensions import db
from app_factory import create_app

app = create_app('testing')

with app.app_context():
    # RLS enabled tables
    rls_count = db.session.execute(
        text("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true")
    ).scalar()
    total_tables = db.session.execute(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
    ).scalar()
    print(f'RLS enabled: {rls_count} / {total_tables} tables')

    # Critical tables: check FORCE ROW LEVEL SECURITY
    print('\nCritical patient data tables:')
    for t in (
        'patients',
        'visits',
        'prescriptions',
        'lab_requests',
        'radiology_requests',
        'payments',
        'invoices',
    ):
        row = db.session.execute(
            text(f"SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = '{t}'")
        ).fetchone()
        if row:
            status = 'RLS+FORCE' if (row[0] and row[1]) else ('RLS only' if row[0] else 'NO RLS')
            print(f'  {t}: {status}')

    # Check policies exist
    pol_count = db.session.execute(
        text("SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public'")
    ).scalar()
    print(f'\nRLS policies: {pol_count}')

    # Test cross-tenant isolation with actual data
    tenants = db.session.execute(
        text('SELECT id, slug FROM tenants ORDER BY id LIMIT 3')
    ).fetchall()
    print(f'\nTenants in DB: {[(t[0], t[1]) for t in tenants]}')

    # Count patients per tenant
    for tid, slug in tenants:
        count = db.session.execute(
            text(f'SELECT COUNT(*) FROM patients WHERE tenant_id = {tid}')
        ).scalar()
        print(f'  Tenant {slug} (id={tid}): {count} patients')

    # Simulate cross-tenant access attempt
    if len(tenants) >= 2:
        t1_id = tenants[0][0]
        t2_id = tenants[1][0]
        # Try to read tenant 2's patients while pretending to be tenant 1
        leaked = db.session.execute(
            text(
                f'SELECT COUNT(*) FROM patients WHERE tenant_id = {t2_id} AND tenant_id != {t1_id}'
            )
        ).scalar()
        print(f'\nCross-tenant leak test: {leaked} rows visible from wrong tenant')

        # Now test with RLS session variable set
        db.session.execute(text(f"SET LOCAL app.tenant_id = '{t1_id}'"))
        leaked_rls = db.session.execute(
            text(f'SELECT COUNT(*) FROM patients WHERE tenant_id = {t2_id}')
        ).scalar()
        print(f'With RLS context (tenant={t1_id}), tenant {t2_id} rows visible: {leaked_rls}')
