"""Fresh setup — proper multi-department medical center tenant."""

import os
import sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
os.environ['APP_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system_test'

from sqlalchemy import select, text

from app.extensions import db
from app_factory import create_app

app = create_app('testing')

with app.app_context():
    # ── Database is freshly migrated — no old data to truncate ──

    # ── 2. Create proper medical center tenant ──
    from app.core.tenant.models import Tenant

    tenant = Tenant(
        slug='medical-center',
        name='medical-center',
        name_ar='المركز الطبي المتخصص',
        contact_email='admin@medical-center.local',
        product_profile_code='multi_department_center',
    )
    db.session.add(tenant)
    db.session.flush()
    tid = tenant.id
    print(f'Tenant created: {tenant.slug} (id={tid})')

    # Enable ALL modules for this tenant
    from app.shared.enums import TenantStatus

    tenant.status = TenantStatus.ACTIVE
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
            'accounting',
            'manager',
            'admin',
            'dicom',
        ],
        True,
    )
    tenant.settings = settings
    db.session.commit()

    # ── 3. Create staff accounts ──
    from models.user import User

    staff = [
        ('admin', 'super_admin', 'Admin123!', 'مدير النظام'),
        ('reception', 'reception', 'ValidPass123!', 'موظف الاستقبال'),
        ('dr_ahmad', 'doctor', 'ValidPass123!', 'د. أحمد محمد'),
        ('dr_sara', 'doctor', 'ValidPass123!', 'د. سارة أحمد'),
        ('nurse_fatima', 'nurse', 'ValidPass123!', 'الممرضة فاطمة'),
        ('lab_tech', 'lab', 'ValidPass123!', 'فني المختبر'),
        ('rad_tech', 'radiology', 'ValidPass123!', 'فني الأشعة'),
        ('pharmacist', 'pharmacist', 'ValidPass123!', 'الصيدلي'),
        ('accountant', 'accountant', 'ValidPass123!', 'المحاسب'),
        ('manager', 'manager', 'ValidPass123!', 'مدير المركز'),
    ]
    user_ids = {}
    for username, role, password, full_name in staff:
        u = User(
            tenant_id=tid,
            username=username,
            email=f'{username}@medical-center.local',
            full_name=full_name,
            role=role,
            is_active=True,
        )
        u.set_password(password)
        db.session.add(u)
        db.session.flush()
        user_ids[username] = u.id
    db.session.commit()

    # ── 4. Create departments with head doctors ──
    from models.department import Department

    depts_data = [
        ('Emergency', 'الطوارئ', user_ids.get('dr_ahmad')),
        ('Internal Medicine', 'الباطنية', user_ids.get('dr_sara')),
        ('Pediatrics', 'الأطفال', None),
        ('Laboratory', 'المختبر', user_ids.get('lab_tech')),
        ('Radiology', 'الأشعة', user_ids.get('rad_tech')),
        ('Pharmacy', 'الصيدلية', user_ids.get('pharmacist')),
    ]
    dept_map = {}
    for name, name_ar, head_id in depts_data:
        d = Department(tenant_id=tid, name=name, name_ar=name_ar, is_active=True)
        if head_id:
            d.head_doctor_id = head_id
        db.session.add(d)
        db.session.flush()
        dept_map[name] = d.id
    db.session.commit()

    # ── 5. Create patients with realistic Arabic names ──
    from models.patient import Patient

    patients_data = [
        ('أحمد', 'محمد علي', 'M', '0501110001', '1990-03-15'),
        ('فاطمة', 'عبدالله', 'F', '0501110002', '1985-07-22'),
        ('محمد', 'أحمد', 'M', '0501110003', '1978-11-30'),
        ('عائشة', 'محمود', 'F', '0501110004', '1995-04-10'),
        ('عمر', 'خالد', 'M', '0501110005', '2000-09-05'),
        ('مريم', 'حسن', 'F', '0501110006', '1988-12-18'),
        ('يوسف', 'إبراهيم', 'M', '0501110007', '1975-06-25'),
        ('نور', 'سعيد', 'F', '0501110008', '2010-02-14'),
    ]
    patient_ids = []
    for fn_ar, ln_ar, g, ph, bd in patients_data:
        p = Patient(
            tenant_id=tid,
            first_name_ar=fn_ar,
            last_name_ar=ln_ar,
            gender=g,
            phone=ph,
            birth_date=__import__('datetime').datetime.strptime(bd, '%Y-%m-%d').date(),
            first_name=fn_ar,
            last_name=ln_ar,
        )
        db.session.add(p)
        db.session.flush()
        patient_ids.append(p.id)
    db.session.commit()

    # ── 6. Create medications for pharmacy ──
    from models.medication import Medication

    meds_data = [
        ('Paracetamol 500mg', 'Acetaminophen', 15.50, 500),
        ('Amoxicillin 500mg', 'Amoxicillin', 25.00, 200),
        ('Ibuprofen 400mg', 'Ibuprofen', 8.75, 300),
        ('Azithromycin 250mg', 'Azithromycin', 45.00, 80),
        ('Omeprazole 20mg', 'Omeprazole', 18.00, 150),
        ('Metformin 850mg', 'Metformin', 12.00, 250),
        ('Amlodipine 5mg', 'Amlodipine', 20.00, 180),
        ('Atorvastatin 20mg', 'Atorvastatin', 35.00, 120),
    ]
    for tn, sn, price, stock in meds_data:
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

    # ── 7. Create supplier ──
    from models.medication import Supplier

    db.session.add(
        Supplier(
            tenant_id=tid,
            name='شركة الأدوية المتحدة',
            contact_person='أبو خالد',
            phone='0481234567',
            email='supplier@united-pharma.local',
            is_active=True,
        )
    )

    # ── 8. Assign permissions via app_factory mechanism ──
    from models.permissions import (
        assign_super_admin_permissions,
        create_default_permissions,
        create_default_roles,
    )

    create_default_permissions()
    create_default_roles()
    assign_super_admin_permissions()

    # Assign role-specific permissions via direct ORM
    from models.permissions import Permission as PermModel
    from models.permissions import Role as RoleModel
    from models.permissions import RolePermission as RPModel

    # Use direct SQL for role-permission assignment (same as app_factory)
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
        'emergency': ['patient_create', 'patient_update', 'patient_read', 'medical_records_create'],
        'accountant': [
            'financial_view',
            'financial_manage',
            'financial_reports',
            'financial_export',
            'pricing_manage',
        ],
        'pharmacist': ['medical_records_read', 'reports_view', 'pharmacy.manage'],
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
        r = db.session.execute(select(RoleModel).filter_by(name=role_name)).scalars().first()
        if not r:
            continue
        for pname in perm_names:
            pm = db.session.execute(select(PermModel).filter_by(name=pname)).scalars().first()
            if not pm:
                continue
            exists = (
                db.session.execute(select(RPModel).filter_by(role_id=r.id, permission_id=pm.id))
                .scalars()
                .first()
            )
            if not exists:
                db.session.add(RPModel(role_id=r.id, permission_id=pm.id))

    safe_commit_ok = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'Commit error: {e}')
        safe_commit_ok = False

    # ── Final counts ──
    counts = {}
    for table in ('tenants', 'users', 'departments', 'patients', 'medications', 'suppliers'):
        n = db.session.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
        counts[table] = n

    print('\n=== FRESH SETUP COMPLETE ===')
    for k, v in counts.items():
        print(f'  {k}: {v}')
    print('\nLogin at http://127.0.0.1:8080/auth/login')
