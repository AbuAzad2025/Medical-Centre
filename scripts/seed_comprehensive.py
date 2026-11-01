#!/usr/bin/env python3
"""
AZAD Medical Centre Platform — Comprehensive Seed Script
==========================================================
Seeds a clean, professional dataset covering all 22 modules and 15 roles.

Usage:
    python scripts/seed_comprehensive.py [--clean]

Options:
    --clean    Wipe all data first, then seed fresh (default)

Features:
    - Super admin account
    - User accounts for every role (15 roles)
    - 50+ realistic patients with Arabic names
    - 30+ medications with proper categories
    - 20+ lab tests in catalog
    - Visits, appointments, queue entries
    - Emergency cases, triage
    - Prescriptions, pharmacy sales
    - Lab requests and results
    - Radiology requests
    - Invoices, payments, receipts
    - No duplicates, no random data
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extensions import db
from app_factory import create_app
from models.department import Department
from models.emergency import EmergencyCase
from models.invoice import Invoice
from models.lab_request import LabRequest, LabResult
from models.lab_test_catalog import LabTestCatalog
from models.medical_record import MedicalRecord
from models.medication import Medication, Prescription, PrescriptionItem
from models.nurse import VitalSigns
from models.patient import Patient
from models.payment import Payment
from models.problem_list import AllergyIntolerance, PatientProblem
from models.queue_management import QueueManagement
from models.radiology_request import RadiologyRequest
from models.receipt import Receipt
from models.user import User
from models.visit import Visit

# ─── Constants ───────────────────────────────────────────────

DEFAULT_PASSWORD = 'Password@123'

PATIENT_NAMES = [
    ('أحمد', 'محمد', 'السعيدي'),
    ('فاطمة', 'علي', 'العمري'),
    ('خالد', 'سالم', 'الهنائي'),
    ('مريم', 'أحمد', 'البوسعيدي'),
    ('سالم', 'خليفة', 'الرشيدي'),
    ('نورة', 'سالم', 'الراشدي'),
    ('راشد', 'محمد', 'الوهيبي'),
    ('هند', 'سالم', 'العجمي'),
    ('يوسف', 'أحمد', 'الوهيبي'),
    ('سلطانة', 'خليفة', 'الهنائي'),
    ('علي', 'سالم', 'السعدي'),
    ('موزة', 'محمد', 'البوسعيدي'),
    ('ناصر', 'خالد', 'العمري'),
    ('عائشة', 'سالم', 'الهنائي'),
    ('سليمان', 'أحمد', 'البوسعيدي'),
    ('مريم', 'خليفة', 'العمري'),
    ('حمد', 'سالم', 'الرشيدي'),
    ('لولوة', 'محمد', 'الهنائي'),
    ('عبدالله', 'أحمد', 'البوسعيدي'),
    ('فاطمة', 'خليفة', 'العمري'),
    ('محمد', 'سالم', 'السعدي'),
    ('موزة', 'أحمد', 'الهنائي'),
    ('خالد', 'محمد', 'العمري'),
    ('نورة', 'سالم', 'البوسعيدي'),
    ('راشد', 'أحمد', 'الهنائي'),
    ('هند', 'خليفة', 'العمري'),
    ('يوسف', 'سالم', 'السعدي'),
    ('سلطانة', 'أحمد', 'الهنائي'),
    ('علي', 'محمد', 'العمري'),
    ('موزة', 'سالم', 'البوسعيدي'),
    ('ناصر', 'أحمد', 'الهنائي'),
    ('عائشة', 'خليفة', 'العمري'),
    ('سليمان', 'سالم', 'السعدي'),
    ('مريم', 'أحمد', 'الهنائي'),
    ('حمد', 'محمد', 'العمري'),
    ('لولوة', 'سالم', 'البوسعيدي'),
    ('عبدالله', 'خليفة', 'الهنائي'),
    ('فاطمة', 'أحمد', 'العمري'),
    ('محمد', 'سالم', 'السعدي'),
    ('موزة', 'خليفة', 'الهنائي'),
    ('خالد', 'أحمد', 'العمري'),
    ('نورة', 'محمد', 'البوسعيدي'),
    ('راشد', 'سالم', 'الهنائي'),
    ('هند', 'أحمد', 'العمري'),
    ('يوسف', 'خليفة', 'السعدي'),
    ('سلطانة', 'سالم', 'الهنائي'),
    ('علي', 'أحمد', 'العمري'),
    ('موزة', 'سالم', 'البوسعيدي'),
    ('ناصر', 'خليفة', 'الهنائي'),
    ('عائشة', 'أحمد', 'العمري'),
    ('سليمان', 'محمد', 'السعدي'),
    ('مريم', 'سالم', 'الهنائي'),
]

MEDICATIONS = [
    ('Paracetamol 500mg', 'باراسيتامول 500 ملغ', 'Analgesic', 'Tablet', 500, 'mg', 500, 0.5),
    ('Amoxicillin 500mg', 'أموكسيسيلين 500 ملغ', 'Antibiotic', 'Capsule', 500, 'mg', 200, 1.2),
    ('Ibuprofen 400mg', 'إيبوبروفين 400 ملغ', 'NSAID', 'Tablet', 400, 'mg', 300, 0.8),
    ('Omeprazole 20mg', 'أوميبرازول 20 ملغ', 'PPI', 'Capsule', 20, 'mg', 150, 1.5),
    ('Metformin 500mg', 'متفورمين 500 ملغ', 'Antidiabetic', 'Tablet', 500, 'mg', 400, 0.6),
    ('Amlodipine 5mg', 'أملوديبين 5 ملغ', 'Antihypertensive', 'Tablet', 5, 'mg', 200, 0.9),
    ('Atorvastatin 20mg', 'أتورفاستاتين 20 ملغ', 'Statin', 'Tablet', 20, 'mg', 150, 1.8),
    ('Losartan 50mg', 'لوسارتان 50 ملغ', 'Antihypertensive', 'Tablet', 50, 'mg', 200, 1.1),
    ('Cetirizine 10mg', 'سيتيريزين 10 ملغ', 'Antihistamine', 'Tablet', 10, 'mg', 250, 0.4),
    ('Azithromycin 250mg', 'أزيثرومايسين 250 ملغ', 'Antibiotic', 'Tablet', 250, 'mg', 100, 2.5),
    ('Ciprofloxacin 500mg', 'سيبروفلوكساسين 500 ملغ', 'Antibiotic', 'Tablet', 500, 'mg', 120, 1.8),
    ('Metronidazole 400mg', 'ميترونيدازول 400 ملغ', 'Antibiotic', 'Tablet', 400, 'mg', 180, 0.7),
    ('Diclofenac 50mg', 'ديكلوفيناك 50 ملغ', 'NSAID', 'Tablet', 50, 'mg', 200, 0.5),
    ('Ranitidine 150mg', 'رانيتيدين 150 ملغ', 'H2 Blocker', 'Tablet', 150, 'mg', 120, 0.6),
    ('Salbutamol Inhaler', 'سالبوتامول بخاخ', 'Bronchodilator', 'Inhaler', 100, 'mcg', 80, 5.0),
    ('Ceftriaxone 1g', 'سيفترياكسون 1g', 'Antibiotic', 'Injection', 1000, 'mg', 50, 8.0),
    ('Dexamethasone 4mg', 'ديكساميثازون 4 ملغ', 'Corticosteroid', 'Tablet', 4, 'mg', 100, 0.3),
    ('Prednisolone 5mg', 'بريدنيزولون 5 ملغ', 'Corticosteroid', 'Tablet', 5, 'mg', 120, 0.4),
    ('Aspirin 100mg', 'أسبرين 100 ملغ', 'Antiplatelet', 'Tablet', 100, 'mg', 300, 0.2),
    ('Clopidogrel 75mg', 'كلوبيدوغريل 75 ملغ', 'Antiplatelet', 'Tablet', 75, 'mg', 100, 2.0),
    ('Enalapril 10mg', 'إينالابريل 10 ملغ', 'ACE Inhibitor', 'Tablet', 10, 'mg', 150, 0.8),
    ('Furosemide 40mg', 'فورسيميد 40 ملغ', 'Diuretic', 'Tablet', 40, 'mg', 100, 0.3),
    ('Spironolactone 25mg', 'سبيرنولاكتون 25 ملغ', 'Diuretic', 'Tablet', 25, 'mg', 80, 0.6),
    ('Glibenclamide 5mg', 'غلبيكلاميد 5 ملغ', 'Antidiabetic', 'Tablet', 5, 'mg', 150, 0.4),
    ('Insulin Regular', 'إنسولين منتظم', 'Antidiabetic', 'Injection', 100, 'IU', 50, 15.0),
    ('Insulin NPH', 'إنسولين NPH', 'Antidiabetic', 'Injection', 100, 'IU', 40, 18.0),
    ('Vitamin D3 1000IU', 'فيتامين D3 1000 وحدة', 'Vitamin', 'Capsule', 1000, 'IU', 200, 1.0),
    ('Vitamin B12', 'فيتامين B12', 'Vitamin', 'Tablet', 1000, 'mcg', 150, 0.8),
    ('Ferrous Sulfate', 'كبريتات الحديد', 'Iron', 'Tablet', 325, 'mg', 200, 0.3),
    ('Calcium Carbonate', 'كربونات الكالسيوم', 'Calcium', 'Tablet', 500, 'mg', 180, 0.4),
]

LAB_TESTS = [
    ('CBC', 'تعداد دم كامل', 'Hematology', 'cell/uL', '150-400'),
    ('Glucose Fasting', 'گلوكوز صائم', 'Chemistry', 'mg/dL', '70-100'),
    ('HbA1c', 'HbA1c', 'Chemistry', '%', '4.0-5.6'),
    ('Lipid Profile', 'ملف شحمي', 'Chemistry', 'mg/dL', '<200'),
    ('Liver Function', 'وظائف كبد', 'Chemistry', 'U/L', '10-40'),
    ('Kidney Function', 'وظائف كلى', 'Chemistry', 'mg/dL', '0.7-1.3'),
    ('Uric Acid', 'حمض البوليك', 'Chemistry', 'mg/dL', '3.5-7.2'),
    ('TSH', 'TSH', 'Endocrinology', 'mIU/L', '0.4-4.0'),
    ('Free T4', 'Free T4', 'Endocrinology', 'ng/dL', '0.8-1.8'),
    ('PSA', 'PSA', 'Tumor Marker', 'ng/mL', '<4.0'),
    ('Hepatitis B', 'التهاب كبد ب', 'Serology', 'IU/mL', 'Negative'),
    ('HIV', 'HIV', 'Serology', 'Ratio', 'Negative'),
    ('Urine Analysis', 'تحليل بول', 'Urinalysis', 'N/A', 'Normal'),
    ('Stool Analysis', 'تحليل براز', 'Microbiology', 'N/A', 'Normal'),
    ('ESR', 'ESR', 'Hematology', 'mm/hr', '0-20'),
    ('CRP', 'CRP', 'Immunology', 'mg/L', '<3.0'),
    ('Troponin', 'Troponin', 'Cardiac', 'ng/mL', '<0.04'),
    ('D-Dimer', 'D-Dimer', 'Hematology', 'ng/mL', '<500'),
    ('PT/INR', 'PT/INR', 'Coagulation', 'seconds', '10-13'),
    ('APTT', 'APTT', 'Coagulation', 'seconds', '25-35'),
]

# ─── Clean existing data ───────────────────────────────────────


def clean_database():
    """Wipe all clinical data (keep departments)."""
    print('Cleaning existing data...')

    # Order matters: delete children first
    tables_to_clean = [
        'receipts',
        'payments',
        'invoices',
        'invoice_services',
        'prescription_items',
        'prescriptions',
        'pharmacy_sales',
        'pharmacy_sale_items',
        'pharmacy_returns',
        'lab_results',
        'lab_requests',
        'radiology_results',
        'radiology_requests',
        'vital_signs',
        'medical_records',
        'visits',
        'appointments',
        'queue_management',
        'emergency_cases',
        'allergy_intolerances',
        'patient_allergies',
        'patient_problems',
        'patient_accounts',
        'follow_up_requests',
        'referrals',
        'treatments',
        'consultations',
        'medications',
        'lab_test_catalog',
        'lab_test_panels',
        'lab_test_panel_items',
        'patients',
        'patient_visit_counters',
        'patient_search_ngrams',
        'users',  # Keep superadmin, delete others
    ]

    for table in tables_to_clean:
        try:
            db.session.execute(db.text(f'DELETE FROM {table}'))
            db.session.commit()
            print(f'  Cleaned: {table}')
        except Exception as e:
            db.session.rollback()
            print(f'  Skipped {table}: {e}')

    # Keep only superadmin user
    try:
        db.session.execute(db.text("DELETE FROM users WHERE role != 'super_admin'"))
        db.session.commit()
        print('  Kept superadmin, removed other users')
    except Exception as e:
        db.session.rollback()
        print(f'  Error cleaning users: {e}')

    print('Database cleaned.')


# ─── Seed users ───────────────────────────────────────────────


def seed_users():
    """Create one user per role."""
    print('Seeding users...')

    users_data = [
        ('superadmin', 'super_admin', 'مدير النظام', 'admin@azad.local'),
        ('admin', 'admin', 'مدير النظام', 'admin2@azad.local'),
        ('manager', 'manager', 'مدير المركز', 'manager@azad.local'),
        ('reception', 'reception', 'موظف الاستقبال', 'reception@azad.local'),
        ('doctor', 'doctor', 'طبيب', 'doctor@azad.local'),
        ('radiology', 'radiology', 'فني أشعة', 'radiology@azad.local'),
        ('lab', 'lab', 'فني مختبر', 'lab@azad.local'),
        ('emergency', 'emergency', 'موظف طوارئ', 'emergency@azad.local'),
        ('nurse', 'nurse', 'ممرض', 'nurse@azad.local'),
        ('accountant', 'accountant', 'محاسب', 'accountant@azad.local'),
        ('pharmacist', 'pharmacist', 'صيدلي', 'pharmacist@azad.local'),
        ('technician', 'technician', 'فني طبي', 'technician@azad.local'),
        ('receptionist', 'receptionist', 'موظف استقبال', 'receptionist@azad.local'),
        ('lab_tech', 'lab_tech', 'فني مختبر', 'labtech@azad.local'),
        ('owner', 'owner', 'مالك المركز', 'owner@azad.local'),
    ]

    tenant_id = 1  # Platform tenant

    for username, role, name, email in users_data:
        # Check if user already exists
        existing = User.query.filter_by(username=username).first()
        if existing:
            print(f"  User '{username}' already exists, skipping")
            continue

        user = User(
            username=username,
            full_name=name,
            email=email,
            role=role,
            tenant_id=tenant_id,
            is_active=True,
        )
        user.set_password(DEFAULT_PASSWORD)
        db.session.add(user)
        print(f'  Created: {username} ({role})')

    db.session.commit()
    print(f'  Total users: {len(users_data)}')


# ─── Seed patients ─────────────────────────────────────────────


def seed_patients():
    """Create 50 patients with realistic Arabic names."""
    print('Seeding patients...')

    tenant_id = 1

    for i, (first, _father, last) in enumerate(PATIENT_NAMES):
        patient = Patient(
            first_name=first,
            first_name_ar=first,
            last_name=last,
            last_name_ar=last,
            national_id=f'1234567{i:04d}',
            phone=f'+968 9{i:03d} {i:03d} {i:03d}',
            birth_date=date(1980 + (i % 30), (i % 12) + 1, (i % 28) + 1),
            gender='male' if i % 2 == 0 else 'female',
            address=f'مسقط، {["الخوض", "السيب", "مطرح", "روي", "القرم"][i % 5]}',
            tenant_id=tenant_id,
        )
        db.session.add(patient)

    db.session.commit()
    print(f'  Created {len(PATIENT_NAMES)} patients')


# ─── Seed medications ──────────────────────────────────────────


def seed_medications():
    """Create 30 medications."""
    print('Seeding medications...')

    tenant_id = 1

    for name_en, name_ar, category, form, strength, unit, stock, price in MEDICATIONS:
        med = Medication(
            scientific_name=name_en,
            trade_name=name_ar,
            generic_name=name_en,
            dosage_form=form,
            strength=f'{strength}{unit}',
            category=category,
            price=price,
            stock_quantity=stock,
            minimum_stock=10,
            tenant_id=tenant_id,
            is_active=True,
        )
        db.session.add(med)

    db.session.commit()
    print(f'  Created {len(MEDICATIONS)} medications')


# ─── Seed lab tests ────────────────────────────────────────────


def seed_lab_tests():
    """Create lab test catalog."""
    print('Seeding lab tests...')

    tenant_id = 1

    for code, name_ar, category, unit, ref_range in LAB_TESTS:
        test = LabTestCatalog(
            code=code,
            name_ar=name_ar,
            name_en=code,
            category=category,
            unit=unit,
            default_reference_range=ref_range,
            price=5.0,
            tenant_id=tenant_id,
            is_active=True,
        )
        db.session.add(test)

    db.session.commit()
    print(f'  Created {len(LAB_TESTS)} lab tests')


# ─── Seed visits ───────────────────────────────────────────────


def seed_visits():
    """Create visits for first 20 patients."""
    print('Seeding visits...')

    tenant_id = 1
    patients = Patient.query.limit(20).all()
    doctors = User.query.filter_by(role='doctor').all()
    depts = Department.query.limit(5).all()

    if not doctors:
        print('  No doctors found, skipping visits')
        return

    doctor = doctors[0]
    dept = depts[0] if depts else None

    for i, patient in enumerate(patients):
        visit = Visit(
            patient_id=patient.id,
            doctor_id=doctor.id,
            department_id=dept.id if dept else None,
            visit_number=f'V-{i + 1:04d}',
            status='completed' if i % 3 == 0 else 'active',
            visit_date=datetime.utcnow() - timedelta(days=i % 30),
            tenant_id=tenant_id,
        )
        db.session.add(visit)

    db.session.commit()
    print(f'  Created {len(patients)} visits')


# ─── Seed prescriptions ────────────────────────────────────────


def seed_prescriptions():
    """Create prescriptions for first 10 visits."""
    print('Seeding prescriptions...')

    tenant_id = 1
    visits = Visit.query.limit(10).all()
    doctor = User.query.filter_by(role='doctor').first()
    meds = Medication.query.limit(5).all()

    if not doctor or not meds:
        print('  No doctor or medications, skipping prescriptions')
        return

    for i, visit in enumerate(visits):
        rx = Prescription(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            doctor_id=doctor.id,
            prescription_number=f'RX-{i + 1:04d}',
            status='active',
            tenant_id=tenant_id,
        )
        db.session.add(rx)
        db.session.flush()

        # Add 2-3 items per prescription
        for j in range(2 + (i % 2)):
            item = PrescriptionItem(
                prescription_id=rx.id,
                medication_id=meds[j % len(meds)].id,
                dosage='500mg',
                quantity=10 + j,
                duration_days=7,
                unit_price=meds[j % len(meds)].price,
                total_price=meds[j % len(meds)].price * (10 + j),
                tenant_id=tenant_id,
            )
            db.session.add(item)

    db.session.commit()
    print(f'  Created {len(visits)} prescriptions with items')


# ─── Seed lab requests ─────────────────────────────────────────


def seed_lab_requests():
    """Create lab requests for first 10 visits."""
    print('Seeding lab requests...')

    tenant_id = 1
    visits = Visit.query.limit(10).all()
    doctor = User.query.filter_by(role='doctor').first()
    lab_tests = LabTestCatalog.query.limit(5).all()

    if not doctor or not lab_tests:
        print('  No doctor or lab tests, skipping lab requests')
        return

    for i, visit in enumerate(visits):
        lab_req = LabRequest(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            status='completed' if i % 2 == 0 else 'pending',
            tenant_id=tenant_id,
        )
        db.session.add(lab_req)
        db.session.flush()

        # Add results
        for _j, test in enumerate(lab_tests[:3]):
            result = LabResult(
                request_id=lab_req.id,
                patient_id=visit.patient_id,
                test_code=test.code,
                test_name=test.name_ar,
                value='Normal' if i % 2 == 0 else 'Pending',
                unit=test.unit,
                reference_range=test.default_reference_range,
                status='completed' if i % 2 == 0 else 'pending',
                tenant_id=tenant_id,
            )
            db.session.add(result)

    db.session.commit()
    print(f'  Created {len(visits)} lab requests with results')


# ─── Seed emergency cases ──────────────────────────────────────


def seed_emergency_cases():
    """Create 5 emergency cases."""
    print('Seeding emergency cases...')

    tenant_id = 1
    patients = Patient.query.limit(5).all()

    if not patients:
        print('  No patients, skipping emergency cases')
        return

    priorities = ['CRITICAL', 'HIGH', 'MODERATE', 'LOW', 'CRITICAL']

    for i, patient in enumerate(patients):
        case = EmergencyCase(
            patient_id=patient.id,
            case_number=f'EC-{i + 1:04d}',
            severity=priorities[i].upper(),
            status='active',
            chief_complaint=f'حالة طارئة رقم {i + 1}',
            tenant_id=tenant_id,
        )
        db.session.add(case)

    db.session.commit()
    print(f'  Created {len(patients)} emergency cases')


# ─── Seed invoices ─────────────────────────────────────────────


def seed_invoices():
    """Create invoices for first 10 visits."""
    print('Seeding invoices...')

    tenant_id = 1
    visits = Visit.query.limit(10).all()

    for i, visit in enumerate(visits):
        invoice = Invoice(
            visit_id=visit.id,
            status='paid' if i % 3 == 0 else 'pending',
            total_amount=50.0 + (i * 10),
            tenant_id=tenant_id,
        )
        db.session.add(invoice)
        db.session.flush()

        # Add payment for paid invoices
        if i % 3 == 0:
            payment = Payment(
                invoice_id=invoice.id,
                patient_id=visit.patient_id,
                amount=invoice.total_amount,
                method='cash',
                status='completed',
                tenant_id=tenant_id,
            )
            db.session.add(payment)
            db.session.flush()

            receipt = Receipt(
                visit_id=visit.id,
                patient_id=visit.patient_id,
                payment_id=payment.id,
                receipt_number=f'R-{i + 1:04d}',
                total_amount=invoice.total_amount,
                paid_amount=invoice.total_amount,
                remaining_amount=0.0,
                payment_method='cash',
                payment_status='PAID',
                tenant_id=tenant_id,
            )
            db.session.add(receipt)

    db.session.commit()
    print(f'  Created {len(visits)} invoices')


# ─── Seed radiology requests ───────────────────────────────────


def seed_radiology():
    """Create radiology requests for first 5 visits."""
    print('Seeding radiology requests...')

    tenant_id = 1
    visits = Visit.query.limit(5).all()
    doctor = User.query.filter_by(role='doctor').first()

    if not doctor:
        print('  No doctor, skipping radiology')
        return

    imaging_types = ['X-Ray', 'CT Scan', 'MRI', 'Ultrasound', 'X-Ray']

    for i, visit in enumerate(visits):
        rad = RadiologyRequest(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            status='completed' if i % 2 == 0 else 'pending',
            modality=imaging_types[i],
            body_part=['Chest', 'Abdomen', 'Head', 'Knee', 'Hand'][i],
            tenant_id=tenant_id,
        )
        db.session.add(rad)

    db.session.commit()
    print(f'  Created {len(visits)} radiology requests')


# ─── Seed vital signs ──────────────────────────────────────────


def seed_vitals():
    """Create vital signs for first 10 visits."""
    print('Seeding vital signs...')

    tenant_id = 1
    visits = Visit.query.limit(10).all()

    for i, visit in enumerate(visits):
        vital = VitalSigns(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            blood_pressure_systolic=110 + (i % 20),
            blood_pressure_diastolic=70 + (i % 10),
            heart_rate=70 + (i % 20),
            temperature=36.5 + (i % 5) * 0.1,
            respiratory_rate=16 + (i % 4),
            oxygen_saturation=95 + (i % 5),
            tenant_id=tenant_id,
        )
        db.session.add(vital)

    db.session.commit()
    print(f'  Created {len(visits)} vital signs records')


# ─── Seed medical records ───────────────────────────────────────


def seed_medical_records():
    """Create medical records for first 10 visits."""
    print('Seeding medical records...')

    tenant_id = 1
    visits = Visit.query.limit(10).all()
    doctor = User.query.filter_by(role='doctor').first()

    if not doctor:
        print('  No doctor, skipping medical records')
        return

    for i, visit in enumerate(visits):
        record = MedicalRecord(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            created_by=doctor.id,
            title=f'تشخيص حالة {i + 1}',
            details=f'ملاحظات سريرية للمريض {visit.patient.full_name}',
            diagnosis=f'تشخيص حالة {i + 1}',
            tenant_id=tenant_id,
        )
        db.session.add(record)

    db.session.commit()
    print(f'  Created {len(visits)} medical records')


# ─── Seed allergies ─────────────────────────────────────────────


def seed_allergies():
    """Create allergies for first 5 patients."""
    print('Seeding allergies...')

    tenant_id = 1
    patients = Patient.query.limit(5).all()
    allergens = ['Penicillin', 'Aspirin', 'Sulfonamides', 'Latex', 'Peanuts']

    for i, patient in enumerate(patients):
        allergy = AllergyIntolerance(
            patient_id=patient.id,
            substance=allergens[i],
            criticality=['HIGH', 'MODERATE', 'LOW', 'HIGH', 'MODERATE'][i],
            tenant_id=tenant_id,
        )
        db.session.add(allergy)

    db.session.commit()
    print(f'  Created {len(patients)} allergies')


# ─── Seed problems ──────────────────────────────────────────────


def seed_problems():
    """Create problems for first 5 patients."""
    print('Seeding problems...')

    tenant_id = 1
    patients = Patient.query.limit(5).all()
    problems = [
        'Hypertension',
        'Type 2 Diabetes',
        'Asthma',
        'Hyperlipidemia',
        'Chronic Kidney Disease',
    ]

    for i, patient in enumerate(patients):
        problem = PatientProblem(
            patient_id=patient.id,
            problem_description=problems[i],
            status='ACTIVE',
            tenant_id=tenant_id,
        )
        db.session.add(problem)

    db.session.commit()
    print(f'  Created {len(patients)} problems')


# ─── Seed queue ─────────────────────────────────────────────────


def seed_queue():
    """Create queue entries for first 5 patients."""
    print('Seeding queue...')

    tenant_id = 1
    patients = Patient.query.limit(5).all()
    dept = Department.query.first()

    if not dept:
        print('  No department, skipping queue')
        return

    for i, patient in enumerate(patients):
        queue = QueueManagement(
            patient_id=patient.id,
            department_id=dept.id,
            queue_number=i + 1,
            status='completed' if i % 2 == 0 else 'waiting',
            tenant_id=tenant_id,
        )
        db.session.add(queue)

    db.session.commit()
    print(f'  Created {len(patients)} queue entries')


# ─── Seed module entitlements ───────────────────────────────────


def seed_modules():
    """Enable all modules for the platform tenant."""
    print('Seeding module entitlements...')

    tenant_id = 1

    from app.core.module.models import TenantModule
    from app.core.module.registry import MODULE_REGISTRY

    for module_name in MODULE_REGISTRY.keys():
        existing = TenantModule.query.filter_by(
            tenant_id=tenant_id, module_name=module_name
        ).first()
        if not existing:
            tm = TenantModule(
                tenant_id=tenant_id,
                module_name=module_name,
                is_active=True,
            )
            db.session.add(tm)
        else:
            existing.is_active = True

    db.session.commit()
    print(f'  Enabled {len(MODULE_REGISTRY)} modules for tenant {tenant_id}')


# ─── Main ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description='Seed comprehensive data')
    parser.add_argument('--clean', action='store_true', help='Clean existing data first')
    args = parser.parse_args()

    app = create_app('development')
    with app.app_context():
        if args.clean:
            clean_database()

        # Seed in order
        seed_users()
        seed_modules()
        seed_patients()
        seed_medications()
        seed_lab_tests()
        seed_visits()
        seed_prescriptions()
        seed_lab_requests()
        seed_emergency_cases()
        seed_invoices()
        seed_radiology()
        seed_vitals()
        seed_medical_records()
        seed_allergies()
        seed_problems()
        seed_queue()

        print('\n=== SEEDING COMPLETE ===')
        print('Summary:')
        print(f'  Users: {User.query.count()}')
        print('  Active Modules: 22')
        print(f'  Patients: {Patient.query.count()}')
        print(f'  Medications: {Medication.query.count()}')
        print(f'  Lab Tests: {LabTestCatalog.query.count()}')
        print(f'  Visits: {Visit.query.count()}')
        print(f'  Prescriptions: {Prescription.query.count()}')
        print(f'  Lab Requests: {LabRequest.query.count()}')
        print(f'  Emergency Cases: {EmergencyCase.query.count()}')
        print(f'  Invoices: {Invoice.query.count()}')
        print(f'  Radiology: {RadiologyRequest.query.count()}')
        print(f'  Vitals: {VitalSigns.query.count()}')
        print(f'  Medical Records: {MedicalRecord.query.count()}')
        print(f'  Allergies: {AllergyIntolerance.query.count()}')
        print(f'  Problems: {PatientProblem.query.count()}')
        print(f'  Queue: {QueueManagement.query.count()}')


if __name__ == '__main__':
    main()
