"""Tests for adding services without reopening clinical workflow (Ticket 7)."""
import pytest
from decimal import Decimal

from models.visit import Visit
from models.patient import Patient
from models.service import ServiceMaster
from models.department import Department
from models.invoice import Invoice, InvoiceService
from models.audit_trail import AuditTrail
from app_factory import db as _db
from app.shared.enums import PaymentStatus, VisitState
from sqlalchemy import select
from app.extensions import db


class TestAddServiceWithoutReopening:
    def test_reception_adds_catalog_service_to_completed_visit(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        d = Department(name=f'Dept-{__import__("uuid").uuid4().hex[:6]}', name_ar='قسم', is_active=True)
        _db.session.add(d)
        _db.session.commit()

        svc = ServiceMaster(
            code=f'CATALOG-T7-'+__import__('uuid').uuid4().hex[:6].upper(), name='Catalog T7', category='lab',
            base_price=Decimal('50.00'), is_active=True, is_custom=False,
            tenant_id=tenant_id, department_id=d.id
        )
        _db.session.add(svc)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=Decimal('100.00'), paid_amount=Decimal('100.00')
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_add_t7', 'reception')

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
        assert v_after.status == 'COMPLETED'  # clinical status unchanged
        assert v_after.total_amount == Decimal('150.00')  # total increased
        # InvoiceService line created
        lines = db.session.execute(select(InvoiceService).filter_by(visit_id=v.id, service_master_id=svc.id)).scalars().all()
        assert len(lines) >= 1

    def test_add_service_rejected_after_archive(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        d = Department(name=f'Dept-{__import__("uuid").uuid4().hex[:6]}', name_ar='قسم', is_active=True)
        _db.session.add(d)
        _db.session.commit()

        svc = ServiceMaster(
            code=f'CATALOG-T7-'+__import__('uuid').uuid4().hex[:6].upper(), name='Catalog T7 Archived', category='lab',
            base_price=Decimal('50.00'), is_active=True, is_custom=False,
            tenant_id=tenant_id, department_id=d.id
        )
        _db.session.add(svc)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=Decimal('100.00'), paid_amount=Decimal('100.00'),
            archive_status='ARCHIVED'
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_add_arch_t7', 'reception')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/add-service',
                data={'service_id': svc.id},
                follow_redirects=False
            )
        assert resp.status_code == 302

        # No new invoice service line should be created
        lines = db.session.execute(select(InvoiceService).filter_by(visit_id=v.id, service_master_id=svc.id)).scalars().all()
        assert len(lines) == 0

    def test_non_reception_cannot_add_service(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        d = Department(name=f'Dept-{__import__("uuid").uuid4().hex[:6]}', name_ar='قسم', is_active=True)
        _db.session.add(d)
        _db.session.commit()

        svc = ServiceMaster(
            code=f'CATALOG-T7-'+__import__('uuid').uuid4().hex[:6].upper(), name='Catalog T7 Doctor', category='lab',
            base_price=Decimal('50.00'), is_active=True, is_custom=False,
            tenant_id=tenant_id, department_id=d.id
        )
        _db.session.add(svc)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=Decimal('100.00'), paid_amount=Decimal('100.00')
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'doc_add_t7', 'doctor')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/add-service',
                data={'service_id': svc.id},
                follow_redirects=False
            )
        # Doctor should be blocked (403 or redirect to login)
        assert resp.status_code in (302, 403)

    def test_cross_tenant_add_service_denied(self, app, test_tenant, client, login_as):
        from app.core.tenant.models import Tenant
        tenant_id = test_tenant.id
        other = Tenant(name='Other', slug=f'other-t7-{__import__("uuid").uuid4().hex[:8]}', contact_email='other@example.com')
        _db.session.add(other)
        _db.session.commit()

        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        d = Department(name=f'Dept-{__import__("uuid").uuid4().hex[:6]}', name_ar='قسم', is_active=True)
        _db.session.add(d)
        _db.session.commit()

        svc = ServiceMaster(
            code=f'CATALOG-T7-'+__import__('uuid').uuid4().hex[:6].upper(), name='Catalog T7 Cross', category='lab',
            base_price=Decimal('50.00'), is_active=True, is_custom=False,
            tenant_id=other.id, department_id=d.id
        )
        _db.session.add(svc)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=Decimal('100.00'), paid_amount=Decimal('100.00')
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_cross_t7', 'reception')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/add-service',
                data={'service_id': svc.id},
                follow_redirects=False
            )
        assert resp.status_code == 302

        lines = db.session.execute(select(InvoiceService).filter_by(visit_id=v.id, service_master_id=svc.id)).scalars().all()
        assert len(lines) == 0


class TestTicket4CorrectiveAddServiceAuthority:
    """Corrective Ticket 4: Post-completion add-service authority."""

    def test_admin_cannot_add_service(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        d = Department(name=f'Dept-{__import__("uuid").uuid4().hex[:6]}', name_ar='قسم', is_active=True)
        _db.session.add(d)
        _db.session.commit()

        svc = ServiceMaster(
            code=f'CATALOG-T4-'+__import__('uuid').uuid4().hex[:6].upper(), name='Catalog T4 Admin', category='lab',
            base_price=Decimal('50.00'), is_active=True, is_custom=False,
            tenant_id=tenant_id, department_id=d.id
        )
        _db.session.add(svc)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=Decimal('100.00'), paid_amount=Decimal('100.00')
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'admin_add_t4', 'admin')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/add-service',
                data={'service_id': svc.id},
                follow_redirects=False
            )
        assert resp.status_code in (302, 403)

        v_after = _db.session.get(Visit, v.id)
        assert v_after.total_amount == Decimal('100.00')

    def test_super_admin_add_service_creates_audit(self, app, test_tenant, client, login_as):
        from models.audit_trail import AuditTrail
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        d = Department(name=f'Dept-{__import__("uuid").uuid4().hex[:6]}', name_ar='قسم', is_active=True)
        _db.session.add(d)
        _db.session.commit()

        svc = ServiceMaster(
            code=f'CATALOG-T4-'+__import__('uuid').uuid4().hex[:6].upper(), name='Catalog T4 Super', category='lab',
            base_price=Decimal('75.00'), is_active=True, is_custom=False,
            tenant_id=tenant_id, department_id=d.id
        )
        _db.session.add(svc)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=Decimal('100.00'), paid_amount=Decimal('100.00')
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'super_add_t4', 'super_admin')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/add-service',
                data={'service_id': svc.id},
                follow_redirects=False
            )
        assert resp.status_code == 302
        assert 'view_visit' in resp.location, f"Expected redirect to view_visit, got: {resp.location}"

        v_after = _db.session.get(Visit, v.id)
        assert v_after.total_amount == Decimal('175.00')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            audit = AuditTrail.query.filter_by(
                entity_type='visit', entity_id=v.id
            ).order_by(AuditTrail.id.desc()).first()
        assert audit is not None
        assert 'إضافة خدمة' in (audit.description or '')

    def test_price_comes_from_catalog_not_client(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        d = Department(name=f'Dept-{__import__("uuid").uuid4().hex[:6]}', name_ar='قسم', is_active=True)
        _db.session.add(d)
        _db.session.commit()

        svc = ServiceMaster(
            code=f'CATALOG-T4-'+__import__('uuid').uuid4().hex[:6].upper(), name='Catalog T4 Price', category='lab',
            base_price=Decimal('120.00'), is_active=True, is_custom=False,
            tenant_id=tenant_id, department_id=d.id
        )
        _db.session.add(svc)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            department_id=d.id, total_amount=Decimal('100.00'), paid_amount=Decimal('100.00')
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_price_t4', 'reception')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/add-service',
                data={'service_id': svc.id, 'unit_price': '9999'},
                follow_redirects=False
            )
        assert resp.status_code == 302

        v_after = _db.session.get(Visit, v.id)
        assert v_after.total_amount == Decimal('220.00')

        line = InvoiceService.query.filter_by(
            visit_id=v.id, service_master_id=svc.id
        ).first()
        assert line is not None
        assert line.unit_price == Decimal('120.00')
        assert line.total_price == Decimal('120.00')
