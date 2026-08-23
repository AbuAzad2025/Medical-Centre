"""Seed sample data for manual testing (ORM-based — handles defaults)."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

import os
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
os.environ['APP_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system_test'

from sqlalchemy import select

from app_factory import create_app
from app.extensions import db

app = create_app('testing')
with app.app_context():
    from models.department import Department
    from models.medication import Medication
    from models.patient import Patient

    # Departments
    for name_ar, name in [('طوارئ', 'Emergency'), ('باطنية', 'Internal Medicine'), ('أطفال', 'Pediatrics')]:
        if not db.session.execute(select(Department).filter_by(name=name)).scalars().first():
            db.session.add(Department(tenant_id=1, name=name, name_ar=name_ar, is_active=True))

    # Patients
    for fn_ar, ln_ar, g, ph in [
        ('أحمد', 'محمد', 'M', '0501111111'),
        ('فاطمة', 'علي', 'F', '0502222222'),
        ('خالد', 'سعيد', 'M', '0503333333'),
    ]:
        if not db.session.execute(select(Patient).filter_by(phone=ph)).scalars().first():
            db.session.add(Patient(
                tenant_id=1, first_name_ar=fn_ar, last_name_ar=ln_ar,
                gender=g, phone=ph, first_name=fn_ar, last_name=ln_ar,
            ))

    # Medications
    for tn, sn, price, stock in [
        ('Paracetamol 500mg', 'Acetaminophen', 15.50, 200),
        ('Amoxicillin 500mg', 'Amoxicillin', 25.00, 100),
        ('Ibuprofen 400mg', 'Ibuprofen', 8.75, 150),
    ]:
        if not db.session.execute(select(Medication).filter_by(trade_name=tn)).scalars().first():
            db.session.add(Medication(
                tenant_id=1, trade_name=tn, scientific_name=sn,
                dosage_form='tablet', strength='500mg',
                price=price, stock_quantity=stock, minimum_stock=20,
                category='general', is_active=True,
            ))

    db.session.commit()

    p = db.session.execute(select(Patient)).scalars().all()
    d = db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
    m = db.session.execute(select(Medication).filter_by(is_active=True)).scalars().all()
    print(f'patients={len(p)}, departments={len(d)}, medications={len(m)}')
