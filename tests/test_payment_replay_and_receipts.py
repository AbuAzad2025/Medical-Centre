"""Replay-safety and receipt-accumulation regression tests."""

import time
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from models.payment import Payment
from services.gatekeeper_service import GatekeeperService
from tests.tenant_context import ensure_test_user, login_test_client


def _mk_patient(db, tenant_id: int, nid: str):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name='أحمد',
        last_name='الاختبار',
        national_id=nid,
    )
    db.session.add(p)
    db.session.flush()
    return p


def _mk_completed_visit(db, tenant_id: int, patient_id: int, total: str, paid: str):
    from models.visit import Visit

    v = Visit(
        tenant_id=tenant_id,
        patient_id=patient_id,
        visit_type='REGULAR',
        status='COMPLETED',
        visit_date=date.today(),
        currency='ILS',
        payment_method='CASH',
        payment_status='PAID' if Decimal(paid) >= Decimal(total) else 'PENDING',
        total_amount=Decimal(total),
        paid_amount=Decimal(paid),
        gl_posted_at=datetime.now(UTC),
        financial_locked=False,
        is_emergency=False,
        is_strong_pay=False,
        created_at=datetime.now(UTC),
    )
    db.session.add(v)
    db.session.flush()
    return v


@pytest.mark.usefixtures('rollback_db')
class TestPaymentReplaySingleCredit:
    def test_replay_same_key_credits_once_and_marks_replayed(self, app, client, db, test_tenant):
        p = _mk_patient(db, test_tenant.id, 'RPLNAT000001')
        v = _mk_completed_visit(db, test_tenant.id, p.id, total='100', paid='0')

        u = ensure_test_user(db, test_tenant, username='rpl_acct', role='accountant')
        login_test_client(client, u, test_tenant)

        data = {
            'paid_amount': '50',
            'payment_method': 'cash',
            'payment_currency': 'ILS',
        }
        resp1 = client.post(
            f'/payment/process/{v.id}', data=data, headers={'Accept': 'application/json'}
        )
        assert resp1.status_code == 200, resp1.get_data(as_text=True)[:300]
        body1 = resp1.get_json()
        assert body1['success'] is True
        assert body1['replayed'] is False

        resp2 = client.post(
            f'/payment/process/{v.id}', data=data, headers={'Accept': 'application/json'}
        )
        assert resp2.status_code == 200, resp2.get_data(as_text=True)[:300]
        body2 = resp2.get_json()
        assert body2['success'] is True
        assert body2['replayed'] is True

        db.session.expire_all()
        fresh = db.session.get(type(v), v.id)
        assert Decimal(str(fresh.paid_amount)) == Decimal('50')

        count = db.session.execute(
            select(func.count()).select_from(Payment).filter_by(visit_id=v.id)
        ).scalar()
        assert count == 1


@pytest.mark.usefixtures('rollback_db')
class TestSystemReceiptAccumulation:
    def test_two_system_receipts_accumulate(self, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='rcp_rc1', role='reception')
        p = _mk_patient(db, test_tenant.id, 'RCPNAT000001')
        v = _mk_completed_visit(db, test_tenant.id, p.id, total='100', paid='0')

        ok1, msg1 = GatekeeperService.create_system_receipt(v.id, u.id, 30)
        assert ok1 is True, msg1
        time.sleep(1.05)
        ok2, msg2 = GatekeeperService.create_system_receipt(v.id, u.id, 20)
        assert ok2 is True, msg2

        db.session.expire_all()
        fresh = db.session.get(type(v), v.id)
        assert Decimal(str(fresh.paid_amount)) == Decimal('50')


@pytest.mark.usefixtures('rollback_db')
class TestArchiveGateAfterAccumulation:
    def test_archive_gate_passes_only_after_full_accumulation(self, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='arc_rc1', role='reception')
        p = _mk_patient(db, test_tenant.id, 'ARCNAT000001')
        v = _mk_completed_visit(db, test_tenant.id, p.id, total='100', paid='0')

        ok1, msg1 = GatekeeperService.create_system_receipt(v.id, u.id, 30)
        assert ok1 is True, msg1
        time.sleep(1.05)
        ok2, msg2 = GatekeeperService.create_system_receipt(v.id, u.id, 20)
        assert ok2 is True, msg2

        can_mid, mid_msg = GatekeeperService.can_archive_visit(v.id, u.id)
        assert can_mid is False
        assert any(w in str(mid_msg) for w in ('أقل', 'رصيد', 'المتأخر'))

        time.sleep(1.05)
        ok3, msg3 = GatekeeperService.create_system_receipt(v.id, u.id, 50)
        assert ok3 is True, msg3

        db.session.expire_all()
        fresh = db.session.get(type(v), v.id)
        assert Decimal(str(fresh.paid_amount)) == Decimal('100')

        can_final, final_msg = GatekeeperService.can_archive_visit(v.id, u.id)
        assert can_final is True, final_msg
