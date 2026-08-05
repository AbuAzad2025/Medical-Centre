"""Tests for archive, settlement, and financial mutation lockdown (Ticket 4)."""

from sqlalchemy import select

from app.extensions import db
from app_factory import db as _db
from models.invoice import Invoice
from models.patient import Patient
from models.visit import Visit


class TestArchiveGatekeeperLockdown:
    def test_non_completed_visit_cannot_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='OPEN',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
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
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED',
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
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            can, _msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is True


class TestReceptionArchiveRoute:
    def test_reception_archive_non_completed_blocked(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='OPEN',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
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
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED',
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

    def test_reception_archive_success_when_conditions_met(
        self, app, test_tenant, client, login_as
    ):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
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
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
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
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'mgr_arch_t4', 'manager')

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            resp = client.post(f'/finance/visits/{v.id}/archive', follow_redirects=False)
        # Ticket 1: finance archive route disabled for admin/manager
        assert resp.status_code == 403

        v_after = _db.session.get(Visit, v.id)
        assert v_after.archive_status != 'ARCHIVED'


class TestPaymentMutationBlockedAfterArchive:
    def test_reception_payment_blocked_after_archive(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED',
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'recv_pay_arch_t4', 'reception')

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            resp = client.post(
                f'/reception/visits/{v.id}/send-to-accounting', follow_redirects=False
            )
        # Must redirect with error, not 200/302 success
        assert resp.status_code == 302
        # Verify no new invoice was created
        invoices = db.session.execute(select(Invoice).filter_by(visit_id=v.id)).scalars().all()
        assert len(invoices) == 0

    def test_accountant_payment_blocked_after_archive(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED',
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
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED',
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


class TestTicket1ArchiveSettlementLockdown:
    """Ticket 1: Require paid_amount >= total_amount and reception-only archive."""

    def test_unpaid_completed_visit_cannot_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=0,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            can, msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is False
        assert 'أقل' in msg or 'less' in msg.lower() or 'outstanding' in msg.lower()

    def test_partially_paid_completed_visit_cannot_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=50,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            can, _msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is False

    def test_fully_paid_reconciled_visit_can_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            can, _msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is True

    def test_reception_can_archive_service(self, app, test_tenant):
        import uuid

        from models.user import User

        tenant_id = test_tenant.id
        u_suffix = uuid.uuid4().hex[:8]
        p = Patient(first_name='ت', last_name='ت')
        rec = User(
            username=f'rec_arch_{u_suffix}',
            password_hash='x',
            full_name='Rec',
            email=f'rec_arch_{u_suffix}@t.com',
            role='reception',
            tenant_id=tenant_id,
            is_active=True,
        )
        _db.session.add_all([p, rec])
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=0,
            paid_amount=0,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            ok, _msg = GatekeeperService.archive_visit(v.id, rec.id)
        assert ok is True

    def test_manager_cannot_archive_service(self, app, test_tenant):
        import uuid

        from models.user import User

        tenant_id = test_tenant.id
        u_suffix = uuid.uuid4().hex[:8]
        p = Patient(first_name='ت', last_name='ت')
        mgr = User(
            username=f'mgr_arch_{u_suffix}',
            password_hash='x',
            full_name='Mgr',
            email=f'mgr_arch_{u_suffix}@t.com',
            role='manager',
            tenant_id=tenant_id,
            is_active=True,
        )
        _db.session.add_all([p, mgr])
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=0,
            paid_amount=0,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            ok, msg = GatekeeperService.archive_visit(v.id, mgr.id)
        assert ok is False
        assert 'صلاحية' in msg or 'authorized' in msg.lower()

    def test_accountant_cannot_archive_service(self, app, test_tenant):
        import uuid

        from models.user import User

        tenant_id = test_tenant.id
        u_suffix = uuid.uuid4().hex[:8]
        p = Patient(first_name='ت', last_name='ت')
        acc = User(
            username=f'acc_arch_{u_suffix}',
            password_hash='x',
            full_name='Acc',
            email=f'acc_arch_{u_suffix}@t.com',
            role='accountant',
            tenant_id=tenant_id,
            is_active=True,
        )
        _db.session.add_all([p, acc])
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=0,
            paid_amount=0,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            ok, _msg = GatekeeperService.archive_visit(v.id, acc.id)
        assert ok is False

    def test_finance_archive_route_returns_403(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=0,
            paid_amount=0,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'fin_mgr_arch', 'manager')
        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            resp = client.post(f'/finance/visits/{v.id}/archive')
        assert resp.status_code == 403


class TestCore1ArchiveBlocksUnpaid:
    """Final Core Correction 1: archive must block when paid_amount < total_amount."""

    def test_fully_paid_completed_can_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            can, _msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is True

    def test_unpaid_completed_cannot_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=0,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            can, _msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is False

    def test_partially_paid_completed_cannot_archive(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=50,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            can, _msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is False

    def test_reconciled_lines_with_outstanding_blocked(self, app, test_tenant):
        from models.invoice import InvoiceService

        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=0,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
        )
        _db.session.add(v)
        _db.session.commit()

        svc = __import__('models.service', fromlist=['ServiceMaster']).ServiceMaster(
            code=f'LINE-REC-{__import__("uuid").uuid4().hex[:6].upper()}',
            name='Line Reconcile Test',
            category='lab',
            base_price=100,
            is_active=True,
            tenant_id=tenant_id,
            department_id=None,
        )
        _db.session.add(svc)
        _db.session.commit()

        from models.invoice import Invoice

        inv = Invoice(
            invoice_number=f'INV-REC-{v.id}', visit_id=v.id, total_amount=100, status='ISSUED'
        )
        _db.session.add(inv)
        _db.session.flush()
        line = InvoiceService(
            invoice_id=inv.id,
            visit_id=v.id,
            service_master_id=svc.id,
            service_code=svc.code,
            service_name=svc.name,
            quantity=1,
            unit_price=100,
            total_price=100,
        )
        _db.session.add(line)
        _db.session.commit()

        from services.gatekeeper_service import GatekeeperService

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            can, msg = GatekeeperService.can_archive_visit(v.id, 1)
        assert can is False
        assert 'أقل' in msg or 'outstanding' in msg.lower()

    def test_already_archived_cannot_archive_again(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()
        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            financial_locked=False,
            archive_status='ARCHIVED',
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
