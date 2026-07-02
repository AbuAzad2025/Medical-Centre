"""
Ticket 8: Service-line reconciliation and final archive enforcement
- can_archive_visit blocks when visit.total_amount != sum(InvoiceService.total_price)
- can_archive_visit allows when amounts match
- can_archive_visit allows zero-amount visits with no services
"""
import pytest, uuid
from datetime import datetime, timezone
from decimal import Decimal
from models.visit import Visit
from models.patient import Patient
from models.invoice import Invoice, InvoiceService
from models.user import User
from app.core.tenant.models import Tenant
from models.department import Department
from services.gatekeeper_service import GatekeeperService
from app_factory import db as _db


@pytest.mark.usefixtures('app')
class TestServiceLineReconciliation:
    def test_archive_allowed_when_reconciled(self, app):
        with app.app_context():
            from flask import g
            from app.shared.enums import TenantStatus
            t = Tenant(name='Recon Tenant', subdomain='recon-'+uuid.uuid4().hex[:6], slug='recon-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='Recon Dept', name_ar='Recon Dept', tenant_id=t.id, is_active=True)
            p = Patient(first_name='Recon', last_name='Patient', tenant_id=t.id)
            u = User(username='reconuser', password_hash='x', full_name='Recon User', email='r@t.com', role='reception', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, u]); _db.session.flush()

            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED',
                total_amount=100, paid_amount=100,
                currency='ILS',
                gl_posted_at=datetime.now(timezone.utc),
                financial_locked=False,
                financial_completed_at=datetime.now(timezone.utc),
                archive_status=None,
            )
            _db.session.add(v); _db.session.flush()

            inv = Invoice(
                invoice_number=f'INV-{v.id}-{uuid.uuid4().hex[:6]}',
                visit_id=v.id, tenant_id=t.id, status='ISSUED',
                total_amount=100, paid_amount=100,
                currency='ILS', created_by=u.id,
            )
            _db.session.add(inv); _db.session.flush()

            _db.session.add_all([
                InvoiceService(invoice_id=inv.id, visit_id=v.id, tenant_id=t.id, service_code='SVC-A', service_name='Service A', quantity=1, unit_price=50, total_price=50, created_by=u.id),
                InvoiceService(invoice_id=inv.id, visit_id=v.id, tenant_id=t.id, service_code='SVC-B', service_name='Service B', quantity=1, unit_price=50, total_price=50, created_by=u.id),
            ])
            _db.session.commit()

            with app.test_request_context():
                from flask import g
                g.tenant_id = t.id
                ok, msg = GatekeeperService.can_archive_visit(v.id, u.id)
                assert ok, msg

    def test_archive_blocked_when_mismatch(self, app):
        with app.app_context():
            from flask import g
            from app.shared.enums import TenantStatus
            t = Tenant(name='Recon Tenant', subdomain='recon-'+uuid.uuid4().hex[:6], slug='recon-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='Recon Dept', name_ar='Recon Dept', tenant_id=t.id, is_active=True)
            p = Patient(first_name='Recon', last_name='Patient', tenant_id=t.id)
            u = User(username='reconuser', password_hash='x', full_name='Recon User', email='r@t.com', role='reception', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, u]); _db.session.flush()

            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED',
                total_amount=100, paid_amount=100,
                currency='ILS',
                gl_posted_at=datetime.now(timezone.utc),
                financial_locked=False,
                financial_completed_at=datetime.now(timezone.utc),
                archive_status=None,
            )
            _db.session.add(v); _db.session.flush()

            inv = Invoice(
                invoice_number=f'INV-{v.id}-{uuid.uuid4().hex[:6]}',
                visit_id=v.id, tenant_id=t.id, status='ISSUED',
                total_amount=100, paid_amount=100,
                currency='ILS', created_by=u.id,
            )
            _db.session.add(inv); _db.session.flush()

            # Only one line for 50, but visit total says 100 → mismatch
            _db.session.add(InvoiceService(invoice_id=inv.id, visit_id=v.id, tenant_id=t.id, service_code='SVC-A', service_name='Service A', quantity=1, unit_price=50, total_price=50, created_by=u.id))
            _db.session.commit()

            with app.test_request_context():
                from flask import g
                g.tenant_id = t.id
                ok, msg = GatekeeperService.can_archive_visit(v.id, u.id)
                assert not ok
                assert 'تسوية' in msg or 'لا يتوافق' in msg

    def test_archive_allowed_zero_amount_no_services(self, app):
        with app.app_context():
            from flask import g
            from app.shared.enums import TenantStatus
            t = Tenant(name='Recon Tenant', subdomain='recon-'+uuid.uuid4().hex[:6], slug='recon-'+uuid.uuid4().hex[:6], status=TenantStatus.ACTIVE, contact_email='r@t.com')
            _db.session.add(t); _db.session.flush()
            g.tenant_id = t.id
            d = Department(name='Recon Dept', name_ar='Recon Dept', tenant_id=t.id, is_active=True)
            p = Patient(first_name='Recon', last_name='Patient', tenant_id=t.id)
            u = User(username='reconuser', password_hash='x', full_name='Recon User', email='r@t.com', role='reception', tenant_id=t.id, is_active=True)
            _db.session.add_all([d, p, u]); _db.session.flush()

            v = Visit(
                patient_id=p.id, tenant_id=t.id, department_id=d.id,
                status='COMPLETED',
                total_amount=0, paid_amount=0,
                currency='ILS',
                gl_posted_at=datetime.now(timezone.utc),
                financial_locked=False,
                financial_completed_at=datetime.now(timezone.utc),
                archive_status=None,
            )
            _db.session.add(v); _db.session.flush()
            _db.session.commit()

            with app.test_request_context():
                from flask import g
                g.tenant_id = t.id
                ok, msg = GatekeeperService.can_archive_visit(v.id, u.id)
                assert ok, msg
