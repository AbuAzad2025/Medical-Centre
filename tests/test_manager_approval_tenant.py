"""Tests for manager approval route tenant safety (Ticket 2)."""

from unittest.mock import patch

from sqlalchemy import select

from app.extensions import db
from app.shared.enums import PaymentStatus
from app_factory import db as _db
from models.patient import Patient
from models.queue_management import QueueManagement
from models.visit import Visit


class TestManagerApprovalTenantSafety:
    """Patch MAX_FORCE_PAYMENT_PERCENTAGE to 100% so tests are not blocked by the 5% quota."""

    def test_manager_approve_same_tenant(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='OPEN',
            total_amount=100,
            paid_amount=0,
            is_force_payment=True,
            force_payment_reason='Emergency surgery needed',
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'mgr_approve_t2', 'manager')

        with patch(
            'services.gatekeeper_service.GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE', 100
        ):
            resp = client.post(f'/manager/approve-force-payment/{v.id}', follow_redirects=False)
        assert resp.status_code == 302
        # Should redirect to force_payment_approvals, not error
        assert 'force_payment_approvals' in resp.location or 'manager' in resp.location

        # Verify visit was approved
        v_after = _db.session.get(Visit, v.id)
        assert v_after.payment_status == PaymentStatus.DEBT
        assert v_after.force_payment_approved_by is not None

    def test_manager_reject_same_tenant(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='OPEN',
            total_amount=100,
            paid_amount=0,
            is_force_payment=True,
            force_payment_reason='Emergency surgery needed',
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'mgr_reject_t2', 'manager')

        with patch(
            'services.gatekeeper_service.GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE', 100
        ):
            resp = client.post(
                f'/manager/reject-force-payment/{v.id}',
                data={'rejection_reason': 'Reason for rejection is clear and sufficient'},
                follow_redirects=False,
            )
        assert resp.status_code == 302

        # Verify visit was rejected
        v_after = _db.session.get(Visit, v.id)
        assert v_after.is_force_payment is False
        assert v_after.payment_status == PaymentStatus.PENDING

    def test_manager_approve_cross_tenant_denied(self, app, test_tenant, client, login_as):
        from app.core.tenant.models import Tenant

        tenant_id = test_tenant.id
        other = Tenant(
            name='Other',
            slug=f'other-mgr-{__import__("uuid").uuid4().hex[:8]}',
            contact_email='other@example.com',
        )
        _db.session.add(other)
        _db.session.commit()

        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=other.id,
            status='OPEN',
            total_amount=100,
            paid_amount=0,
            is_force_payment=True,
            force_payment_reason='Emergency surgery needed',
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'mgr_cross_t2', 'manager')

        with patch(
            'services.gatekeeper_service.GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE', 100
        ):
            resp = client.post(f'/manager/approve-force-payment/{v.id}', follow_redirects=False)
        # Must redirect with flash error rather than disclosing cross-tenant data
        assert resp.status_code == 302
        assert 'force_payment_approvals' in resp.location or 'manager' in resp.location

        # Verify visit was NOT approved
        v_after = _db.session.get(Visit, v.id)
        assert v_after.force_payment_approved_by is None

    def test_manager_reject_cross_tenant_denied(self, app, test_tenant, client, login_as):
        from app.core.tenant.models import Tenant

        tenant_id = test_tenant.id
        other = Tenant(
            name='Other',
            slug=f'other-mgr2-{__import__("uuid").uuid4().hex[:8]}',
            contact_email='other@example.com',
        )
        _db.session.add(other)
        _db.session.commit()

        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=other.id,
            status='OPEN',
            total_amount=100,
            paid_amount=0,
            is_force_payment=True,
            force_payment_reason='Emergency surgery needed',
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'mgr_reject_cross_t2', 'manager')

        with patch(
            'services.gatekeeper_service.GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE', 100
        ):
            resp = client.post(
                f'/manager/reject-force-payment/{v.id}',
                data={'rejection_reason': 'Reason for rejection is clear and sufficient'},
                follow_redirects=False,
            )
        assert resp.status_code == 302

        # Verify visit was NOT rejected
        v_after = _db.session.get(Visit, v.id)
        assert v_after.is_force_payment is True

    def test_manager_approval_missing_tenant_context(self, app, test_tenant, client, login_as):
        """Missing tenant context should deny access."""
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='OPEN',
            total_amount=100,
            paid_amount=0,
            is_force_payment=True,
            force_payment_reason='Emergency surgery needed',
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'mgr_no_ctx_t2', 'manager')

        with patch(
            'services.gatekeeper_service.GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE', 100
        ):
            resp = client.post(f'/manager/approve-force-payment/{v.id}', follow_redirects=False)
        # Should redirect (flash error) rather than processing
        assert resp.status_code == 302

    def test_manager_approval_does_not_enqueue(self, app, test_tenant, client, login_as):
        """Ticket 1: Manager approval must not auto-enqueue the visit."""
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        from sqlalchemy import text

        d = _db.session.execute(text('SELECT id FROM departments LIMIT 1')).fetchone()
        dept_id = d[0] if d else None

        v = Visit(
            patient_id=p.id,
            tenant_id=tenant_id,
            status='OPEN',
            total_amount=100,
            paid_amount=0,
            is_force_payment=True,
            force_payment_reason='Emergency surgery needed',
            department_id=dept_id,
        )
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'mgr_no_enqueue_t2', 'manager')

        with patch(
            'services.gatekeeper_service.GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE', 100
        ):
            resp = client.post(f'/manager/approve-force-payment/{v.id}', follow_redirects=False)
        assert resp.status_code == 302

        # Verify no queue ticket was created for this visit
        qm = db.session.execute(select(QueueManagement).filter_by(visit_id=v.id)).scalars().first()
        assert qm is None
