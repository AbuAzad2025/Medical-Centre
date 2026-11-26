"""Create one paid, queued visit for a package-1 patient so the doctor UI can treat it."""

import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select

from app.core.tenant.models import Tenant
from app.extensions import db
from app.shared.enums import PaymentStatus, VisitState
from models.department import Department
from models.patient import Patient
from models.user import User
from models.visit import Visit
from seeds import tenant_bypass
from services.queue_management_service import QueueManagementService
from wsgi import app

TENANT_SLUG = 'dr-ahmed-clinic'
PATIENT_PHONE_END = os.environ.get('PATIENT_PHONE_END', '0001')
DEPARTMENT_NAME = 'العيادة العامة'
ADMIN_USERNAME = 'admin'

with app.app_context():
    tenant = db.session.execute(select(Tenant).filter_by(slug=TENANT_SLUG)).scalar_one()
    with tenant_bypass(tenant):
        doctor = db.session.execute(
            select(User).filter_by(tenant_id=tenant.id, username=ADMIN_USERNAME)
        ).scalar_one()
        patient = db.session.execute(select(Patient).filter_by(tenant_id=tenant.id)).scalars().all()
        patient = next(
            p for p in patient if (getattr(p, 'phone', '') or '').endswith(PATIENT_PHONE_END)
        )
        department = db.session.execute(
            select(Department).filter_by(tenant_id=tenant.id, name=DEPARTMENT_NAME)
        ).scalar_one_or_none()
        if department is None:
            department = (
                db.session.execute(
                    select(Department).filter_by(tenant_id=tenant.id, is_active=True)
                )
                .scalars()
                .first()
            )

        visit = Visit(
            patient_id=patient.id,
            department_id=department.id,
            doctor_id=doctor.id,
            visit_type='OUTPATIENT',
            status=VisitState.OPEN.value,
            payment_status=PaymentStatus.PAID.value,
            created_at=datetime.now(UTC),
            notes='مراجعة عيادة تجريبية للحزمة 1',
        )
        db.session.add(visit)
        db.session.flush()

        ok, message = QueueManagementService().add_patient_to_queue(
            patient_id=patient.id,
            department_id=department.id,
            doctor_id=doctor.id,
            visit_id=visit.id,
            queue_type='normal',
            created_by=doctor.id,
        )
        db.session.commit()
        print('tenant', tenant.id, tenant.slug)
        print('patient', patient.id, f'{patient.first_name} {patient.last_name}')
        print('doctor', doctor.id, doctor.username)
        print('visit', visit.id, visit.status, visit.payment_status)
        print('queue', ok, message)
