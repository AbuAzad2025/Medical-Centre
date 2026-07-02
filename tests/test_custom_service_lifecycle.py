"""Tests for custom service lifecycle (Ticket 6)."""
import pytest

from models.service import ServiceMaster
from models.visit import Visit
from models.patient import Patient
from models.invoice import InvoiceService
from app_factory import db as _db


class TestCustomServiceLifecycle:
    def test_custom_service_created_inactive(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        from models.department import Department
        import uuid
        d = Department(name=f'Lab-{uuid.uuid4().hex[:6]}', name_ar='المختبر', is_active=True)
        _db.session.add(d)
        _db.session.commit()

        login_as(client, 'recv_custom_t6', 'reception')

        with app.test_request_context():
            from flask import g
            from flask_login import current_user
            g.tenant_id = tenant_id
            from routes.reception.visits import _process_custom_services
            svc_ids = _process_custom_services(
                ['Custom Blood Test'], ['150.0'], d.id, current_user
            )
        assert len(svc_ids) == 1
        svc = _db.session.get(ServiceMaster, int(svc_ids[0]))
        assert svc.is_custom is True
        assert svc.is_active is False
        assert svc.created_by is not None

    def test_approved_custom_service_becomes_active(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        import uuid
        code = f'CUSTOM-T6-{uuid.uuid4().hex[:6].upper()}'
        svc = ServiceMaster(
            code=code, name='Custom T6', category='lab',
            base_price=100, is_custom=True, is_active=False,
            tenant_id=tenant_id
        )
        _db.session.add(svc)
        _db.session.commit()

        login_as(client, 'mgr_approve_t6', 'manager')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(f'/manager/approve-custom-service/{svc.id}', follow_redirects=False)
        assert resp.status_code == 302

        svc_after = _db.session.get(ServiceMaster, svc.id)
        assert svc_after.is_active is True
        assert svc_after.approved_by is not None
        assert svc_after.approved_at is not None

    def test_rejected_custom_service_stays_inactive(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        import uuid
        code = f'CUSTOM-T6-{uuid.uuid4().hex[:6].upper()}'
        svc = ServiceMaster(
            code=code, name='Custom T6 Rejected', category='lab',
            base_price=100, is_custom=True, is_active=False,
            tenant_id=tenant_id
        )
        _db.session.add(svc)
        _db.session.commit()

        login_as(client, 'mgr_reject_t6', 'manager')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/manager/reject-custom-service/{svc.id}',
                data={'rejection_reason': 'Not suitable for catalog'},
                follow_redirects=False
            )
        assert resp.status_code == 302

        svc_after = _db.session.get(ServiceMaster, svc.id)
        assert svc_after.is_active is False
        assert svc_after.approved_by is not None
        assert 'مرفوض' in (svc_after.description or '')

    def test_cross_tenant_custom_service_approval_denied(self, app, test_tenant, client, login_as):
        from app.core.tenant.models import Tenant
        tenant_id = test_tenant.id
        import uuid
        other = Tenant(name='Other', slug=f'other-custom-{uuid.uuid4().hex[:8]}', contact_email='other@example.com')
        _db.session.add(other)
        _db.session.commit()

        import uuid
        code = f'CUSTOM-T6-{uuid.uuid4().hex[:6].upper()}'
        svc = ServiceMaster(
            code=code, name='Custom T6 Cross', category='lab',
            base_price=100, is_custom=True, is_active=False,
            tenant_id=other.id
        )
        _db.session.add(svc)
        _db.session.commit()

        login_as(client, 'mgr_cross_t6', 'manager')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(f'/manager/approve-custom-service/{svc.id}', follow_redirects=False)
        assert resp.status_code == 302

        svc_after = _db.session.get(ServiceMaster, svc.id)
        assert svc_after.approved_by is None

    def test_invoice_service_has_created_by(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(patient_id=p.id, tenant_id=tenant_id, status='OPEN', total_amount=100, paid_amount=0)
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_inv_t6', 'reception')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            from models.invoice import Invoice
            from flask_login import current_user
            import uuid
            inv = Invoice(visit_id=v.id, invoice_number=f'INV-T6-{uuid.uuid4().hex[:8]}', total_amount=100, created_by=current_user.id)
            _db.session.add(inv)
            _db.session.flush()
            line = InvoiceService(
                invoice_id=inv.id, visit_id=v.id, service_code='VISIT',
                service_name='خدمات زيارة', quantity=1, unit_price=100, total_price=100,
                created_by=current_user.id
            )
            _db.session.add(line)
            _db.session.commit()

        line_after = InvoiceService.query.filter_by(invoice_id=inv.id).first()
        assert line_after.created_by is not None

    def test_custom_service_not_in_catalog_before_approval(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        import uuid
        code = f'CUSTOM-T6-{uuid.uuid4().hex[:6].upper()}'
        svc = ServiceMaster(
            code=code, name='Pending Custom', category='lab',
            base_price=100, is_custom=True, is_active=False, tenant_id=tenant_id
        )
        _db.session.add(svc)
        _db.session.commit()

        # Verify the service is not returned by active catalog queries
        active = ServiceMaster.query.filter_by(is_active=True, tenant_id=tenant_id).all()
        assert svc not in active

    def test_custom_service_in_catalog_after_approval(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        import uuid
        code = f'CUSTOM-T6-{uuid.uuid4().hex[:6].upper()}'
        svc = ServiceMaster(
            code=code, name='Approved Custom', category='lab',
            base_price=100, is_custom=True, is_active=False, tenant_id=tenant_id
        )
        _db.session.add(svc)
        _db.session.commit()

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            svc.is_active = True
            svc.approved_by = 1
            svc.approved_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
            _db.session.commit()

        active = ServiceMaster.query.filter_by(is_active=True, tenant_id=tenant_id).all()
        assert svc in active
