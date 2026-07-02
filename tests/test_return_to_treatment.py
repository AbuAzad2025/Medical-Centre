"""
Final Core Correction 2: MC-009 return-to-treatment.

- Reception only
- COMPLETED -> OPEN
- Requires audited reason (>=3 chars)
- Doctor/manager/admin denied
- Add-service does not change visit status
"""
import pytest, uuid, json
from datetime import datetime, timezone
from models.visit import Visit
from models.patient import Patient
from models.user import User
from models.department import Department
from services.visit_state_machine_service import VisitStateMachineService
from app_factory import db as _db
from app.shared.enums import TenantStatus
from app.core.tenant.models import Tenant


@pytest.mark.usefixtures('app')
class TestReturnToTreatment:
    def test_reception_can_return_completed_visit_to_open(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='RTT', subdomain='rtt-'+uuid.uuid4().hex[:6], slug='rtt-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='RTT Dept', name_ar=('\u0642' + '\u0633' + '\u0645'), tenant_id=t.id, is_active=True)
            p = Patient(first_name='RTT', last_name='P', tenant_id=t.id)
            rec = User(username='rec_rtt', password_hash='x', full_name='Rec RTT', email='r@t.com', role='reception', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, rec]); _db.session.flush()
            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED', total_amount=0, paid_amount=0, currency='ILS',
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                ok = VisitStateMachineService.return_to_treatment(v, actor=rec, reason='Follow-up needed')
                assert ok
                assert v.status == 'OPEN'

    def test_doctor_cannot_return_to_treatment(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='RTT2', subdomain='rtt2-'+uuid.uuid4().hex[:6], slug='rtt2-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r2@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='RTT2 Dept', name_ar=('\u0642' + '\u0633' + '\u0645'), tenant_id=t.id, is_active=True)
            p = Patient(first_name='RTT2', last_name='P', tenant_id=t.id)
            doc = User(username='doc_rtt2', password_hash='x', full_name='Doc RTT', email='d@t.com', role='doctor', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, doc]); _db.session.flush()
            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED', total_amount=0, paid_amount=0, currency='ILS',
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                with pytest.raises(ValueError) as exc_info:
                    VisitStateMachineService.return_to_treatment(v, actor=doc, reason='Follow-up')
                assert 'not authorized' in str(exc_info.value)


    def test_manager_cannot_return_to_treatment(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='RTT3', subdomain='rtt3-'+uuid.uuid4().hex[:6], slug='rtt3-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r3@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='RTT3 Dept', name_ar=('\u0642' + '\u0633' + '\u0645'), tenant_id=t.id, is_active=True)
            p = Patient(first_name='RTT3', last_name='P', tenant_id=t.id)
            mgr = User(username='mgr_rtt3', password_hash='x', full_name='Mgr RTT', email='m@t.com', role='manager', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, mgr]); _db.session.flush()
            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED', total_amount=0, paid_amount=0, currency='ILS',
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                with pytest.raises(ValueError) as exc_info:
                    VisitStateMachineService.return_to_treatment(v, actor=mgr, reason='Follow-up')
                assert 'not authorized' in str(exc_info.value)

    def test_non_completed_visit_cannot_return(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='RTT4', subdomain='rtt4-'+uuid.uuid4().hex[:6], slug='rtt4-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r4@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='RTT4 Dept', name_ar=('\u0642' + '\u0633' + '\u0645'), tenant_id=t.id, is_active=True)
            p = Patient(first_name='RTT4', last_name='P', tenant_id=t.id)
            rec = User(username='rec_rtt4', password_hash='x', full_name='Rec RTT4', email='r4@t.com', role='reception', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, rec]); _db.session.flush()
            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='OPEN', total_amount=0, paid_amount=0, currency='ILS',
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                with pytest.raises(ValueError) as exc_info:
                    VisitStateMachineService.return_to_treatment(v, actor=rec, reason='Follow-up')
                assert 'only valid from COMPLETED' in str(exc_info.value)

    def test_return_to_treatment_requires_actor(self, app):
        with app.app_context():
            from flask import g
            t = Tenant(name='RTT5', subdomain='rtt5-'+uuid.uuid4().hex[:6], slug='rtt5-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r5@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='RTT5 Dept', name_ar=('\u0642' + '\u0633' + '\u0645'), tenant_id=t.id, is_active=True)
            p = Patient(first_name='RTT5', last_name='P', tenant_id=t.id)
            _db.session.add_all([d, p]); _db.session.flush()
            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED', total_amount=0, paid_amount=0, currency='ILS',
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                g.tenant_id = t.id
                with pytest.raises(ValueError) as exc_info:
                    VisitStateMachineService.return_to_treatment(v, actor=None, reason='Follow-up')
                assert 'actor required' in str(exc_info.value)


    def test_add_service_does_not_change_visit_status(self, app, test_tenant, client, login_as):
        from models.service import ServiceMaster
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p); _db.session.commit()
        d = Department(name='Dept-RTT-' + uuid.uuid4().hex[:6], name_ar='قسم', is_active=True)
        _db.session.add(d); _db.session.commit()
        svc = ServiceMaster(code='CATALOG-RTT-' + uuid.uuid4().hex[:6].upper(), name='RTT Service', category='lab', base_price=50, is_active=True, tenant_id=tenant_id, department_id=d.id)
        _db.session.add(svc); _db.session.commit()
        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=100, paid_amount=100
        )
        _db.session.add(v); _db.session.commit()

        login_as(client, 'recv_rtt_add', 'reception')
        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/add-service',
                data={'service_id': svc.id},
                follow_redirects=False
            )
        assert resp.status_code == 302
        v_after = _db.session.get(Visit, v.id)
        assert v_after.status == 'COMPLETED'

    def test_reception_return_to_treatment_route_creates_audit(self, app, test_tenant, client, login_as):
        from models.audit_trail import AuditTrail
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p); _db.session.commit()
        d = Department(name='Dept-RTT-AUD-' + uuid.uuid4().hex[:6], name_ar='قسم', is_active=True)
        _db.session.add(d); _db.session.commit()
        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=0, paid_amount=0
        )
        _db.session.add(v); _db.session.commit()

        login_as(client, 'recv_rtt_aud', 'reception')
        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/return-to-treatment',
                data={'reason': 'Test reason for audit'},
                follow_redirects=False
            )
        assert resp.status_code == 302
        v_after = _db.session.get(Visit, v.id)
        assert v_after.status == 'OPEN'

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            audit = AuditTrail.query.filter_by(
                entity_type='visit', entity_id=v.id
            ).order_by(AuditTrail.id.desc()).first()
        assert audit is not None
        assert 'إعادة فتح' in (audit.description or '')

