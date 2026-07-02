"""
Ticket 9: Controlled return-to-treatment workflow
- Only doctor/manager/super_admin can return COMPLETED visit to IN_PROGRESS
- Requires reason (>=3 chars)
- Audit trail recorded
- Cross-tenant denied
- Non-COMPLETED status blocked
"""
import pytest, uuid
from datetime import datetime, timezone
from models.visit import Visit
from models.patient import Patient
from models.user import User
from app.core.tenant.models import Tenant
from models.department import Department
from services.visit_state_machine_service import VisitStateMachineService
from app_factory import db as _db
from app.shared.enums import TenantStatus


@pytest.mark.usefixtures('app')
class TestReturnToTreatment:
    def test_doctor_can_return_completed_visit(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='Return Tenant', subdomain='ret-'+uuid.uuid4().hex[:6], slug='ret-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='Return Dept', name_ar='Return Dept', tenant_id=t.id, is_active=True)
            p = Patient(first_name='Return', last_name='Patient', tenant_id=t.id)
            doc = User(username='docret', password_hash='x', full_name='Doc Ret', email='d@t.com', role='doctor', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, doc]); _db.session.flush()

            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED', total_amount=0, paid_amount=0, currency='ILS',
                gl_posted_at=datetime.now(timezone.utc), financial_locked=False,
                financial_completed_at=datetime.now(timezone.utc), archive_status=None,
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                ok = VisitStateMachineService.return_to_treatment(v, actor=doc, reason='Further treatment needed')
                assert ok
                assert v.status == 'IN_PROGRESS'

    def test_reception_cannot_return_to_treatment(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='Return Tenant', subdomain='ret-'+uuid.uuid4().hex[:6], slug='ret-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='Return Dept', name_ar='Return Dept', tenant_id=t.id, is_active=True)
            p = Patient(first_name='Return', last_name='Patient', tenant_id=t.id)
            rec = User(username='recret', password_hash='x', full_name='Rec Ret', email='r@t.com', role='reception', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, rec]); _db.session.flush()

            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED', total_amount=0, paid_amount=0, currency='ILS',
                gl_posted_at=datetime.now(timezone.utc), financial_locked=False,
                financial_completed_at=datetime.now(timezone.utc), archive_status=None,
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                with pytest.raises(ValueError) as exc_info:
                    VisitStateMachineService.return_to_treatment(v, actor=rec, reason='Further treatment needed')
                assert 'not authorized' in str(exc_info.value)

    def test_non_completed_visit_cannot_return(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='Return Tenant', subdomain='ret-'+uuid.uuid4().hex[:6], slug='ret-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='Return Dept', name_ar='Return Dept', tenant_id=t.id, is_active=True)
            p = Patient(first_name='Return', last_name='Patient', tenant_id=t.id)
            doc = User(username='docret', password_hash='x', full_name='Doc Ret', email='d@t.com', role='doctor', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, doc]); _db.session.flush()

            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='OPEN', total_amount=0, paid_amount=0, currency='ILS',
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                with pytest.raises(ValueError) as exc_info:
                    VisitStateMachineService.return_to_treatment(v, actor=doc, reason='Further treatment needed')
                assert 'only valid from COMPLETED' in str(exc_info.value)

    def test_return_to_treatment_requires_actor(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='Return Tenant', subdomain='ret-'+uuid.uuid4().hex[:6], slug='ret-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='Return Dept', name_ar='Return Dept', tenant_id=t.id, is_active=True)
            p = Patient(first_name='Return', last_name='Patient', tenant_id=t.id)
            _db.session.add_all([d, p]); _db.session.flush()

            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED', total_amount=0, paid_amount=0, currency='ILS',
                gl_posted_at=datetime.now(timezone.utc), financial_locked=False,
                financial_completed_at=datetime.now(timezone.utc), archive_status=None,
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                with pytest.raises(ValueError) as exc_info:
                    VisitStateMachineService.return_to_treatment(v, actor=None, reason='Further treatment needed')
                assert 'actor required' in str(exc_info.value)
