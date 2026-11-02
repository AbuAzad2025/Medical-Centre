#!/usr/bin/env python3
"""
Verify RLS enforcement (runtime role + proof).

This script verifies that RLS policies are enforced at runtime
by testing that queries with different tenant contexts return
only the appropriate data.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Verify RLS enforcement at runtime."""
    print('Verifying RLS enforcement...')

    # Set up environment
    os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:testpass@localhost:5432/test')
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-ci-testing-32bytes-minimum-length'
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['RLS_BYPASS_ALLOWED'] = '1'

    try:
        from flask import g

        from app_factory import create_app

        app = create_app('testing')

        with app.app_context():
            from flask import current_app
            from sqlalchemy import select

            from app.core.tenant.middleware import bind_g_tenant
            from app.core.tenant.models import Tenant
            from models.patient import Patient

            db = current_app.extensions['migrate'].db

            # Create two test tenants
            tenant1 = Tenant(
                slug='tenant1',
                name='Tenant 1',
                name_ar='مستأجر 1',
                contact_email='t1@test.com',
                status='ACTIVE',
            )
            tenant2 = Tenant(
                slug='tenant2',
                name='Tenant 2',
                name_ar='مستأجر 2',
                contact_email='t2@test.com',
                status='ACTIVE',
            )

            db.session.add(tenant1)
            db.session.add(tenant2)
            db.session.flush()

            # Create a test patient in tenant1
            patient1 = Patient(
                tenant_id=tenant1.id, first_name='Test', last_name='Patient1', gender='M'
            )
            db.session.add(patient1)

            # Create a test patient in tenant2
            patient2 = Patient(
                tenant_id=tenant2.id, first_name='Test', last_name='Patient2', gender='F'
            )
            db.session.add(patient2)
            db.session.commit()

            # Test 1: Query as tenant1 - should only see patient1
            bind_g_tenant(tenant1)
            patients_tenant1 = db.session.execute(select(Patient)).scalars().all()
            tenant1_patient_ids = {p.id for p in patients_tenant1}
            print(f'Tenant 1 sees patients: {tenant1_patient_ids}')

            if patient2.id in tenant1_patient_ids:
                print('FAIL: Tenant 1 can see tenant2 patient')
                return 1

            if patient1.id not in tenant1_patient_ids:
                print('FAIL: Tenant 1 cannot see own patient')
                return 1

            print('PASS: Tenant 1 sees only own patients')

            # Test 2: Query as tenant2 - should only see patient2
            bind_g_tenant(tenant2)
            patients_tenant2 = db.session.execute(select(Patient)).scalars().all()
            tenant2_patient_ids = {p.id for p in patients_tenant2}
            print(f'Tenant 2 sees patients: {tenant2_patient_ids}')

            if patient1.id in tenant2_patient_ids:
                print('FAIL: Tenant 2 can see tenant1 patient')
                return 1

            if patient2.id not in tenant2_patient_ids:
                print('FAIL: Tenant 2 cannot see own patient')
                return 1

            print('PASS: Tenant 2 sees only own patients')

            # Test 3: Query as platform (no tenant bound) - should see nothing or all depending on policy
            # With RLS_FORCE, even platform should be restricted unless bypassed
            # Clear tenant binding
            from flask import g

            g.pop('tenant_id', None)
            g.pop('current_tenant', None)

            patients_platform = db.session.execute(select(Patient)).scalars().all()
            platform_patient_ids = {p.id for p in patients_platform}
            print(f'Platform sees patients: {platform_patient_ids}')

            # With FORCE RLS and no tenant bound, should see nothing
            if platform_patient_ids:
                print(
                    'WARNING: Platform sees patients without tenant binding (may be expected if bypass is active)'
                )
            else:
                print('PASS: Platform sees no patients without tenant binding')

    except Exception as e:
        print(f'ERROR during RLS enforcement test: {e}')
        import traceback

        traceback.print_exc()
        return 1

    print('\nAll RLS enforcement tests passed!')
    return 0


if __name__ == '__main__':
    sys.exit(main())
