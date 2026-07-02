"""Tests for archive, settlement, and financial mutation lockdown (Ticket 4)."""
import pytest
from unittest.mock import patch

from models.visit import Visit
from models.patient import Patient
from models.payment import Payment
from models.invoice import Invoice
from models.queue_management import QueueManagement
from app_factory import db as _db
from app.shared.enums import PaymentStatus, VisitState


class TestArchiveGatekeeperLockdown:
    def test_non_completed_visit_cannot_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='OPEN',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService
        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            can, msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is False
        assert 'إنهاء' in msg or 'complete' in msg.lower()

    def test_already_archived_visit_cannot_rearchive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED'
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService
        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            can, msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is False
        assert 'مؤرشفة' in msg or 'archived' in msg.lower()

    def test_completed_visit_can_archive_when_conditions_met(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService
        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            can, msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is True


class TestReceptionArchiveRoute:
    def test_reception_archive_non_completed_blocked(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='OPEN',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_arch_t4', 'reception')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(f'/reception/visits/{v.id}/archive', follow_redirects=False)
        assert resp.status_code == 302

        v_after = _db.session.get(Visit, v.id)
        assert v_after.archive_status != 'ARCHIVED'

    def test_reception_archive_archived_blocked(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED'
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_arch2_t4', 'reception')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(f'/reception/visits/{v.id}/archive', follow_redirects=False)
        assert resp.status_code == 302

        v_after = _db.session.get(Visit, v.id)
        assert v_after.archived_by is None  # not re-archived

    def test_reception_archive_success_when_conditions_met(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_arch3_t4', 'reception')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(f'/reception/visits/{v.id}/archive', follow_redirects=False)
        assert resp.status_code == 302

        v_after = _db.session.get(Visit, v.id)
        assert v_after.archive_status == 'ARCHIVED'


class TestFinanceArchiveRoute:
    def test_accountant_cannot_archive(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'acct_arch_t4', 'accountant')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(f'/finance/visits/{v.id}/archive', follow_redirects=False)
        # Accountant should be blocked (403) because role list excludes accountant
        assert resp.status_code == 403

    def test_manager_can_archive_via_finance(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'mgr_arch_t4', 'manager')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(f'/finance/visits/{v.id}/archive', follow_redirects=False)
        assert resp.status_code == 200

        v_after = _db.session.get(Visit, v.id)
        assert v_after.archive_status == 'ARCHIVED'


class TestPaymentMutationBlockedAfterArchive:
    def test_reception_payment_blocked_after_archive(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED'
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_pay_arch_t4', 'reception')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.post(f'/reception/visits/{v.id}/send-to-accounting', follow_redirects=False)
        # Must redirect with error, not 200/302 success
        assert resp.status_code == 302
        # Verify no new invoice was created
        invoices = Invoice.query.filter_by(visit_id=v.id).all()
        assert len(invoices) == 0

    def test_accountant_payment_blocked_after_archive(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED'
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'acct_pay_arch_t4', 'accountant')

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            resp = client.get(f'/payment/process/{v.id}', follow_redirects=False)
        # Must get 422 (archive block) or 404, not 200 success
        assert resp.status_code in (302, 404, 422)

    def test_system_receipt_blocked_after_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id, tenant_id=tenant_id, status='COMPLETED',
            total_amount=100, paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED'
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService
        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            ok, msg = GatekeeperService.create_system_receipt(v.id, 1, 50)
        assert ok is False
        assert 'مؤرشفة' in msg
