"""Local dev story seeder (``--dev``).

Builds a self-contained mock tenant ("Azad Dev Hospital", tenant id 1) with all
14 application modules active, standard clinic staff (reception, doctor, lab,
pharmacy), and a linked clinical flow:

    patient → active visit → pending lab order → unfilled prescription → unpaid bill

Designed for local development and demos. Idempotent.
"""

import contextlib
import uuid

from sqlalchemy import select

from app.core.module.models import TenantModule
from app.core.module.registry import MODULE_REGISTRY
from app.core.tenant.models import Tenant
from app.extensions import db
from models.invoice import Invoice
from models.lab_request import LabRequest
from models.medication import Prescription
from models.patient import Patient
from models.user import User
from models.visit import Visit

from . import tenant_bypass

DEV_TENANT_ID = 1
DEV_TENANT_SLUG = 'azad-dev'
DEV_TENANT_NAME = 'Azad Dev Hospital'

# (role_key, username, full_name, role)
STAFF = [
    ('reception', 'dev_reception', 'Dev Receptionist', 'reception'),
    ('doctor', 'dev_doctor', 'Dr. Dev', 'doctor'),
    ('lab', 'dev_lab', 'Dev Lab Tech', 'lab'),
    ('pharmacy', 'dev_pharmacist', 'Dev Pharmacist', 'pharmacist'),
]

DEV_PASSWORD = 'dev12345'


def _sync_tenant_sequence(tenant_id: int) -> None:
    """Ensure the tenants.id sequence is past any explicitly-set id."""
    with contextlib.suppress(Exception):
        db.session.execute(
            db.text(
                "SELECT setval(pg_get_serial_sequence('tenants','id'), "
                'GREATEST(:tid, (SELECT MAX(id) FROM tenants)), true)'
            ).bindparams(tid=tenant_id)
        )


def seed_dev_tenant(session=None):
    session = session or db.session
    with tenant_bypass():
        # Keyed by slug (not a hard-coded id) so it never clobbers an
        # existing tenant — in a fresh production DB it simply gets the next
        # available id; in tests it coexists with the default tenant.
        tenant = (
            db.session.execute(select(Tenant).filter_by(slug=DEV_TENANT_SLUG)).scalars().first()
        )
        if tenant is None:
            tenant = Tenant(
                slug=DEV_TENANT_SLUG,
                name=DEV_TENANT_NAME,
                contact_email='dev@azad.local',
                status='active',
                product_profile_code='doctor_clinic_full',
            )
            session.add(tenant)
            session.flush()
        return tenant


def activate_modules(tenant, session=None):
    session = session or db.session
    with tenant_bypass():
        import datetime

        now = datetime.datetime.now(datetime.UTC)
        count = 0
        for name in MODULE_REGISTRY:
            if name == 'owner':
                continue
            row = db.session.execute(
                select(TenantModule).filter_by(tenant_id=tenant.id, module_name=name)
            ).scalar()
            if row is None:
                row = TenantModule(tenant_id=tenant.id, module_name=name)
                session.add(row)
            row.is_active = True
            row.activated_at = now
            count += 1
        session.commit()
        return count


def seed_staff(tenant, session=None):
    session = session or db.session
    with tenant_bypass():
        created = {}
        for _key, username, full_name, role in STAFF:
            user = db.session.execute(
                select(User).filter_by(username=username, tenant_id=tenant.id)
            ).scalar()
            if user is None:
                user = User(
                    username=username,
                    email=f'{username}@azad.local',
                    full_name=full_name,
                    role=role,
                    tenant_id=tenant.id,
                    is_active=True,
                )
                user.set_password(DEV_PASSWORD)
                session.add(user)
                session.flush()
            created[role] = user
        session.commit()
        return created


def seed_clinical_flow(tenant, staff, session=None):
    session = session or db.session
    with tenant_bypass():
        # Idempotent: reuse existing patient/visit if present
        patient = db.session.execute(
            select(Patient).filter_by(tenant_id=tenant.id, phone='0500000001')
        ).scalar()
        if patient is None:
            patient = Patient(
                tenant_id=tenant.id,
                first_name='Dev',
                last_name='Patient',
                phone='0500000001',
            )
            session.add(patient)
            session.flush()

        doctor = staff['doctor']
        visit = db.session.execute(
            select(Visit).filter_by(
                tenant_id=tenant.id, patient_id=patient.id, status='IN_PROGRESS'
            )
        ).scalar()
        if visit is None:
            visit = Visit(
                tenant_id=tenant.id,
                patient_id=patient.id,
                doctor_id=doctor.id,
                status='IN_PROGRESS',
            )
            session.add(visit)
            session.flush()

        lab_request = db.session.execute(
            select(LabRequest).filter_by(tenant_id=tenant.id, visit_id=visit.id, status='REQUESTED')
        ).scalar()
        if lab_request is None:
            lab_request = LabRequest(
                tenant_id=tenant.id,
                visit_id=visit.id,
                patient_id=patient.id,
                requested_by=doctor.id,
                status='REQUESTED',
            )
            session.add(lab_request)
            session.flush()

        prescription = db.session.execute(
            select(Prescription).filter_by(tenant_id=tenant.id, visit_id=visit.id, status='active')
        ).scalar()
        if prescription is None:
            prescription = Prescription(
                tenant_id=tenant.id,
                patient_id=patient.id,
                doctor_id=doctor.id,
                visit_id=visit.id,
                prescription_number=f'RX-{uuid.uuid4().hex[:8]}',
                status='active',
            )
            session.add(prescription)
            session.flush()

        invoice = db.session.execute(
            select(Invoice).filter_by(tenant_id=tenant.id, visit_id=visit.id, status='ISSUED')
        ).scalar()
        if invoice is None:
            invoice = Invoice(
                tenant_id=tenant.id,
                visit_id=visit.id,
                invoice_number=f'INV-{uuid.uuid4().hex[:8]}',
                total_amount=100,
                paid_amount=0,
                status='ISSUED',
            )
            session.add(invoice)
        session.commit()

        return {
            'patient': patient,
            'visit': visit,
            'lab_request': lab_request,
            'prescription': prescription,
            'invoice': invoice,
        }


def run(app=None, with_clinical: bool = True):
    """Standalone entry point: ``python -m seeds.local_dev_story``."""
    if app is None:
        from app_factory import create_app

        app = create_app()
    with app.app_context():
        tenant = seed_dev_tenant()
        activate_modules(tenant)
        staff = seed_staff(tenant)
        seed_clinical_flow(tenant, staff) if with_clinical else {}
        return tenant
