#!/usr/bin/env python3
"""
First-run setup script for LOCAL DEVELOPMENT.

Creates:
- Platform catalog (modules, bundles, SaaS packages)
- Master account azad (platform_owner)
- Demo tenant "medical-center" with full staff and seed data

Usage:
    python -m scripts.first_run.dev_first_run

Passwords are FIXED for convenience in dev only:
    azad:        DevAzad123!
    All staff:   DevPass123!
"""

import os
import sys

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Environment ───────────────────────────────────────────────────────────────
os.environ['SECRET_KEY'] = 'dev-secret-key-do-not-use-in-production'
os.environ['APP_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system_test'

FIXED_MASTER_PASSWORD = 'DevAzad123!'
FIXED_STAFF_PASSWORD = 'DevPass123!'


def _banner(title: str) -> None:
    sep = '=' * 60
    print(f'\n{sep}\n  {title}\n{sep}')


def main() -> None:
    from sqlalchemy import text

    from app.core.platform_bootstrap import run_platform_bootstrap
    from app.core.tenant.models import Tenant
    from app.extensions import db
    from app.shared.enums import TenantStatus
    from app_factory import create_app
    from models.user import User

    app = create_app('testing')

    with app.app_context():
        # ── 1. Platform Bootstrap ────────────────────────────────────────────
        _banner('1. Platform Bootstrap')
        result = run_platform_bootstrap(quiet=False)
        print(f'  Modules added:     {result["module_definitions_added"]}')
        print(f'  Product bundles:    {result["product_bundles"]}')
        print(f'  SaaS packages:      {result["saas_packages_added"]}')

        # ── 2. Master Account ──────────────────────────────────────────────────
        _banner('2. Master Account (platform_owner)')
        from seeds.production_baseline import _resolve_platform_tenant

        master_tenant = _resolve_platform_tenant()
        print(f'  Tenant: {master_tenant.slug} (id={master_tenant.id})')

        existing = db.session.execute(
            text("SELECT id FROM users WHERE username = 'azad'")
        ).fetchone()

        if existing:
            master = db.session.get(User, existing[0])
            master.set_password(FIXED_MASTER_PASSWORD)
            master.role = 'platform_owner'
            master.is_active = True
            print('  Updated existing azad account')
        else:
            master = User(
                username='azad',
                email='azad@medical.system',
                full_name='Platform Owner (Azad Dev)',
                role='platform_owner',
                tenant_id=master_tenant.id,
                is_active=True,
            )
            master.set_password(FIXED_MASTER_PASSWORD)
            db.session.add(master)
            print('  Created azad account')
        db.session.commit()
        print('  Username: azad')
        print(f'  Password: {FIXED_MASTER_PASSWORD}')
        print('  Role:     platform_owner')

        # ── 3. Demo Tenant ────────────────────────────────────────────────────
        _banner('3. Demo Tenant: medical-center')
        existing_tenant = db.session.execute(
            text("SELECT id FROM tenants WHERE slug = 'medical-center'")
        ).fetchone()

        if existing_tenant:
            tenant = db.session.get(Tenant, existing_tenant[0])
            print(f'  Tenant already exists (id={tenant.id}) — skipping creation')
        else:
            tenant = Tenant(
                slug='medical-center',
                name='medical-center',
                name_ar='المركز الطبي المتخصص',
                contact_email='admin@medical-center.local',
                product_profile_code='multi_department_center',
                status=TenantStatus.ACTIVE,
            )
            db.session.add(tenant)
            db.session.flush()

            settings = tenant.settings or {}
            settings['modules'] = dict.fromkeys(
                [
                    'reception',
                    'doctor',
                    'lab',
                    'radiology',
                    'pharmacy',
                    'emergency',
                    'nursing',
                    'billing',
                    'inventory',
                    'reporting',
                    'appointments',
                    'portal',
                    'inpatient',
                ],
                True,
            )
            tenant.settings = settings
            db.session.commit()
            print(f'  Created tenant: medical-center (id={tenant.id})')
        tid = tenant.id

        # ── 4. Staff Accounts ─────────────────────────────────────────────────
        _banner('4. Staff Accounts')
        staff = [
            ('admin', 'super_admin', 'مدير النظام'),
            ('reception', 'reception', 'موظف الاستقبال'),
            ('dr_ahmad', 'doctor', 'د. أحمد محمد'),
            ('dr_sara', 'doctor', 'د. سارة أحمد'),
            ('nurse_fatima', 'nurse', 'الممرضة فاطمة'),
            ('lab_tech', 'lab', 'فني المختبر'),
            ('rad_tech', 'radiology', 'فني الأشعة'),
            ('pharmacist', 'pharmacy', 'الصيدلي'),
            ('accountant', 'accountant', 'المحاسب'),
            ('manager', 'manager', 'مدير المركز'),
        ]

        user_ids = {}
        for username, role, full_name in staff:
            existing = db.session.execute(
                text(f"SELECT id FROM users WHERE username = '{username}'")
            ).fetchone()
            if existing:
                u = db.session.get(User, existing[0])
                u.set_password(FIXED_STAFF_PASSWORD)
                u.role = role
                u.is_active = True
                user_ids[username] = u.id
                print(f'  Updated {username}/{role}')
            else:
                u = User(
                    tenant_id=tid,
                    username=username,
                    email=f'{username}@medical-center.local',
                    full_name=full_name,
                    role=role,
                    is_active=True,
                )
                u.set_password(FIXED_STAFF_PASSWORD)
                db.session.add(u)
                db.session.flush()
                user_ids[username] = u.id
                print(f'  Created {username}/{role}')
        db.session.commit()

        # ── 5. Departments ────────────────────────────────────────────────────
        _banner('5. Departments')
        depts_data = [
            ('Emergency', 'الطوارئ', user_ids.get('dr_ahmad')),
            ('Internal Med', 'الباطنية', user_ids.get('dr_sara')),
            ('Pediatrics', 'الأطفال', None),
            ('Laboratory', 'المختبر', user_ids.get('lab_tech')),
            ('Radiology', 'الأشعة', user_ids.get('rad_tech')),
            ('Pharmacy', 'الصيدلية', user_ids.get('pharmacist')),
            ('Surgery', 'الجراحة', None),
            ('Cardiology', 'قلب', None),
            ('Orthopedics', 'عظام', None),
            ('Dermatology', 'جلدية', None),
        ]
        dept_map = {}
        for name, name_ar, head_id in depts_data:
            existing = db.session.execute(
                text(f"SELECT id FROM departments WHERE tenant_id = {tid} AND name = '{name}'")
            ).fetchone()
            if existing:
                dept_map[name] = existing[0]
                print(f'  Exists: {name}')
            else:
                from models.department import Department

                d = Department(
                    tenant_id=tid,
                    name=name,
                    name_ar=name_ar,
                    head_doctor_id=head_id,
                    is_active=True,
                )
                db.session.add(d)
                db.session.flush()
                dept_map[name] = d.id
                print(f'  Created: {name}')
        db.session.commit()

        # ── 6. Sample Patients ─────────────────────────────────────────────────
        _banner('6. Sample Patients')
        patients_data = [
            ('أحمد', 'محمد علي', 'M', '0501110001', '1990-03-15'),
            ('فاطمة', 'عبدالله', 'F', '0501110002', '1985-07-22'),
            ('محمد', 'أحمد', 'M', '0501110003', '1978-11-30'),
            ('عائشة', 'محمود', 'F', '0501110004', '1995-04-10'),
            ('عمر', 'خالد', 'M', '0501110005', '2000-09-05'),
            ('مريم', 'حسن', 'F', '0501110006', '1988-12-18'),
            ('يوسف', 'إبراهيم', 'M', '0501110007', '1975-06-25'),
            ('نور', 'سعيد', 'F', '0501110008', '2010-02-14'),
            ('خالد', 'سالم', 'M', '0501110009', '1992-01-20'),
            ('سلمى', 'عمر', 'F', '0501110010', '1988-08-11'),
        ]
        for fn_ar, ln_ar, g, ph, bd in patients_data:
            existing = db.session.execute(
                text(f"SELECT id FROM patients WHERE tenant_id = {tid} AND phone = '{ph}'")
            ).fetchone()
            if existing:
                print(f'  Exists: {fn_ar} {ln_ar}')
                continue
            import datetime

            from models.patient import Patient

            p = Patient(
                tenant_id=tid,
                first_name_ar=fn_ar,
                last_name_ar=ln_ar,
                gender=g,
                phone=ph,
                birth_date=datetime.datetime.strptime(bd, '%Y-%m-%d').date(),
                first_name=fn_ar,
                last_name=ln_ar,
            )
            db.session.add(p)
            print(f'  Created: {fn_ar} {ln_ar}')
        db.session.commit()

        # ── 7. Medications ────────────────────────────────────────────────────
        _banner('7. Medications')
        meds_data = [
            ('Paracetamol 500mg', 'Acetaminophen', 15.50, 500),
            ('Amoxicillin 500mg', 'Amoxicillin', 25.00, 200),
            ('Ibuprofen 400mg', 'Ibuprofen', 8.75, 300),
            ('Azithromycin 250mg', 'Azithromycin', 45.00, 80),
            ('Omeprazole 20mg', 'Omeprazole', 18.00, 150),
            ('Metformin 850mg', 'Metformin', 6.00, 250),
            ('Amlodipine 5mg', 'Amlodipine', 20.00, 180),
            ('Atorvastatin 20mg', 'Atorvastatin', 35.00, 120),
            ('Ciprofloxacin 500mg', 'Ciprofloxacin', 22.00, 160),
            ('Omeprazole 40mg', 'Omeprazole', 25.00, 100),
        ]
        for tn, sn, price, stock in meds_data:
            existing = db.session.execute(
                text(f"SELECT id FROM medications WHERE tenant_id = {tid} AND trade_name = '{tn}'")
            ).fetchone()
            if existing:
                print(f'  Exists: {tn}')
                continue
            from models.medication import Medication

            db.session.add(
                Medication(
                    tenant_id=tid,
                    trade_name=tn,
                    scientific_name=sn,
                    dosage_form='tablet',
                    strength=tn.split()[-1],
                    price=price,
                    stock_quantity=stock,
                    minimum_stock=30,
                    category='general',
                    is_active=True,
                )
            )
            print(f'  Created: {tn}')
        db.session.commit()

        # ── 8. Supplier ────────────────────────────────────────────────────────
        _banner('8. Suppliers')
        suppliers = [
            ('شركة الأدوية المتحدة', 'أبو خالد', '0481234567', 'supplier@united-pharma.local'),
            ('شركة الخليج للأدوية', 'أبو أحمد', '0487654321', 'info@gulf-pharma.local'),
        ]
        for name, contact, phone, email in suppliers:
            existing = db.session.execute(
                text(f"SELECT id FROM suppliers WHERE tenant_id = {tid} AND name = '{name}'")
            ).fetchone()
            if existing:
                print(f'  Exists: {name}')
                continue
            from models.medication import Supplier

            db.session.add(
                Supplier(
                    tenant_id=tid,
                    name=name,
                    contact_person=contact,
                    phone=phone,
                    email=email,
                    is_active=True,
                )
            )
            print(f'  Created: {name}')
        db.session.commit()

        # ── 9. Permissions ────────────────────────────────────────────────────
        _banner('9. Permissions & Roles')
        from models.permissions import (
            assign_super_admin_permissions,
            create_default_permissions,
            create_default_roles,
        )

        create_default_permissions()
        create_default_roles()
        assign_super_admin_permissions()
        print('  Default permissions and roles seeded')

        from models.permissions import RolePermission as RPModel

        role_perm_map = {
            'admin': ['admin.access', 'user_read', 'system_settings'],
            'reception': [
                'patient_create',
                'patient_read',
                'patient_update',
                'reception.manage',
                'medical_records_read',
                'queue_settings_manage',
            ],
            'doctor': [
                'medical_records_create',
                'medical_records_read',
                'medical_records_update',
                'patient_read',
                'doctor.access',
                'finance.view',
            ],
            'nurse': ['patient_read', 'medical_records_read', 'medical_records_update'],
            'lab': ['reports_view', 'medical_records_read'],
            'radiology': ['reports_view', 'medical_records_read'],
            'pharmacy': ['medical_records_read', 'reports_view', 'pharmacy.manage'],
            'accountant': [
                'financial_view',
                'financial_manage',
                'financial_reports',
                'financial_export',
                'pricing_manage',
            ],
            'manager': [
                'reports_view',
                'reports_create',
                'financial_reports',
                'financial_view',
                'pricing_manage',
                'patient_read',
                'patient_update',
                'queue_settings_manage',
                'finance.view',
            ],
        }

        for role_name, perm_names in role_perm_map.items():
            r = (
                db.session.execute(text(f"SELECT id FROM roles WHERE name = '{role_name}'"))
                .scalars()
                .first()
            )
            if not r:
                continue
            for pname in perm_names:
                pm = (
                    db.session.execute(text(f"SELECT id FROM permissions WHERE name = '{pname}'"))
                    .scalars()
                    .first()
                )
                if not pm:
                    continue
                exists = db.session.execute(
                    text(
                        f'SELECT 1 FROM role_permissions WHERE role_id = {r} AND permission_id = {pm}'
                    )
                ).fetchone()
                if not exists:
                    db.session.add(RPModel(role_id=r, permission_id=pm))
        db.session.commit()
        print('  Role permissions assigned')

        # ── Final Counts ───────────────────────────────────────────────────────
        _banner('DONE — Summary')
        counts = {}
        n = db.session.execute(text('SELECT COUNT(*) FROM tenants')).scalar()
        counts['tenants'] = n
        for table in ('users', 'departments', 'patients', 'medications', 'suppliers'):
            n = db.session.execute(
                text(f'SELECT COUNT(*) FROM {table} WHERE tenant_id = {tid}')
            ).scalar()
            counts[table] = n

        print(f'  Tenants:     {counts["tenants"]}')
        print(f'  Users:       {counts["users"]}')
        print(f'  Departments: {counts["departments"]}')
        print(f'  Patients:    {counts["patients"]}')
        print(f'  Medications: {counts["medications"]}')
        print(f'  Suppliers:   {counts["suppliers"]}')
        print(f'\n  Master login:  azad / {FIXED_MASTER_PASSWORD}')
        print(f'  Staff login:  reception / {FIXED_STAFF_PASSWORD}  (or any staff account)')
        print('\n  App URL: http://127.0.0.1:5001/auth/login')
        print('  DB: medical_system_test\n')


if __name__ == '__main__':
    main()
