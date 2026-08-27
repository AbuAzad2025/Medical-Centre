"""High-risk hardening: booking payment amount/rate-limit, eMAR safety guards, reveal-password restriction."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from tests.tenant_context import ensure_test_user, login_test_client


def _mk_booking(db, tenant_id, amount='50.00'):
    from models.online_booking import OnlineBooking

    b = OnlineBooking(
        tenant_id=tenant_id,
        booking_reference=f'HR{uuid.uuid4().hex[:8].upper()}',
        confirmation_code=uuid.uuid4().hex[:6],
        first_name='محمد',
        last_name='الاختبار',
        phone='0599000001',
        doctor_id=None,
        appointment_date=datetime.now(UTC).date(),
        appointment_time=datetime.min.time().replace(hour=10),
        visit_type='first',
        status='pending',
        payment_amount=Decimal(amount),
    )
    db.session.add(b)
    db.session.flush()
    return b


def _mk_patient(db, tenant_id, nid):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name='سعاد',
        last_name='الاختبار',
        national_id=nid,
    )
    db.session.add(p)
    db.session.flush()
    return p


def _mk_medication(db, tenant_id, trade_name):
    from models.medication import Medication

    m = Medication(
        tenant_id=tenant_id,
        trade_name=trade_name,
        scientific_name=trade_name,
        dosage_form='tablet',
        strength='500mg',
        price=Decimal('10.00'),
    )
    db.session.add(m)
    db.session.flush()
    return m


def _mk_prescription(db, tenant_id, patient_id):
    from models.medication import Prescription

    pres = Prescription(
        tenant_id=tenant_id,
        patient_id=patient_id,
        prescription_number=f'HRX{uuid.uuid4().hex[:10].upper()}',
        status='active',
    )
    db.session.add(pres)
    db.session.flush()
    return pres


def _mk_emar(db, tenant_id, patient_id, medication_id):
    from models.emar import eMARAdministration

    pres = _mk_prescription(db, tenant_id, patient_id)
    row = eMARAdministration(
        tenant_id=tenant_id,
        patient_id=patient_id,
        prescription_id=pres.id,
        medication_id=medication_id,
        scheduled_time=datetime.now(UTC),
        status='SCHEDULED',
    )
    db.session.add(row)
    db.session.flush()
    return row


def _assert_arabic_409(resp, *keywords):
    assert resp.status_code == 409, resp.status_code
    body = resp.get_json(silent=True) or {}
    assert body.get('success') is False, body
    msg = str(body.get('message') or '')
    assert any(k in msg for k in keywords), msg


@pytest.mark.usefixtures('rollback_db')
class TestBookingPaymentAmountGuard:
    def test_tampered_amount_rejected_with_arabic_error(self, app, client, db, test_tenant):
        b = _mk_booking(db, test_tenant.id)
        db.session.commit()

        resp = client.post(
            f'/booking/payment/{b.id}',
            data={'amount': '999.00', 'payment_method': 'CARD'},
            headers={'Accept': 'application/json'},
        )

        assert resp.status_code == 400, resp.status_code
        body = resp.get_json(silent=True) or {}
        assert body.get('success') is False, body
        assert 'المبلغ المطلوب غير مطابق' in str(body.get('message')), body

        from models.online_booking import PaymentTransaction

        txns = (
            db.session.execute(select(PaymentTransaction).filter_by(booking_id=b.id))
            .scalars()
            .all()
        )
        assert txns == []

    def test_exact_amount_creates_transaction_at_server_price(self, app, client, db, test_tenant):
        b = _mk_booking(db, test_tenant.id, amount='50.00')
        db.session.commit()

        resp = client.post(
            f'/booking/payment/{b.id}',
            data={'amount': '50.00', 'payment_method': 'CARD'},
            headers={'Accept': 'application/json'},
        )

        assert resp.status_code in (200, 302), resp.status_code

        from models.online_booking import PaymentTransaction

        txn = (
            db.session.execute(select(PaymentTransaction).filter_by(booking_id=b.id))
            .scalars()
            .first()
        )
        assert txn is not None
        assert Decimal(str(txn.amount)) == Decimal('50.00')

    def test_doctor_pricing_overrides_client_amount(self, app, client, db, test_tenant):
        from models.pricing import DoctorPricing

        doctor = ensure_test_user(db, test_tenant, username='hr_pricedoc', role='doctor')
        b = _mk_booking(db, test_tenant.id, amount='999.00')
        b.doctor_id = doctor.id
        db.session.add(
            DoctorPricing(
                tenant_id=test_tenant.id,
                doctor_id=doctor.id,
                consultation_price=Decimal('75.00'),
                is_active=True,
            )
        )
        db.session.commit()

        resp = client.post(
            f'/booking/payment/{b.id}',
            data={'amount': '75.00', 'payment_method': 'CASH'},
            headers={'Accept': 'application/json'},
        )

        assert resp.status_code in (200, 302), resp.status_code

        from models.online_booking import PaymentTransaction

        txn = (
            db.session.execute(select(PaymentTransaction).filter_by(booking_id=b.id))
            .scalars()
            .first()
        )
        assert txn is not None and Decimal(str(txn.amount)) == Decimal('75.00')

    def test_payment_endpoint_rate_limits_public_posts(
        self, app, client, db, test_tenant, monkeypatch
    ):
        monkeypatch.setitem(app.config, 'TESTING', False)
        b = _mk_booking(db, test_tenant.id)
        db.session.commit()

        last = None
        for _ in range(12):
            last = client.post(
                f'/booking/payment/{b.id}',
                data={'amount': '50.00', 'payment_method': 'CASH'},
                headers={'Accept': 'application/json'},
            )
            if last.status_code == 429:
                break

        assert last is not None and last.status_code == 429, getattr(last, 'status_code', None)
        body = last.get_json(silent=True) or {}
        assert body.get('success') is False, body


@pytest.mark.usefixtures('rollback_db')
class TestEmarSafetyGuards:
    def test_wrong_patient_blocked_409_arabic(self, app, client, db, test_tenant):
        nurse = ensure_test_user(db, test_tenant, username='hr_nurse_pat', role='nurse')
        login_test_client(client, nurse, test_tenant)

        p1 = _mk_patient(db, test_tenant.id, f'HRPA{uuid.uuid4().hex[:8]}')
        p2 = _mk_patient(db, test_tenant.id, f'HRPB{uuid.uuid4().hex[:8]}')
        med = _mk_medication(db, test_tenant.id, 'دواء-مريض-أ')
        row = _mk_emar(db, test_tenant.id, p1.id, med.id)
        db.session.commit()

        resp = client.post(
            f'/emar/administer/{row.id}',
            data={'patient_id': str(p2.id)},
            headers={'Accept': 'application/json'},
        )

        _assert_arabic_409(resp, 'المريض غير مطابق')

    def test_wrong_drug_blocked_409_arabic(self, app, client, db, test_tenant):
        nurse = ensure_test_user(db, test_tenant, username='hr_nurse_drug', role='nurse')
        login_test_client(client, nurse, test_tenant)

        med_a = _mk_medication(db, test_tenant.id, 'دواء-أ')
        med_b = _mk_medication(db, test_tenant.id, 'دواء-ب')
        p1 = _mk_patient(db, test_tenant.id, f'HRPC{uuid.uuid4().hex[:8]}')
        row = _mk_emar(db, test_tenant.id, p1.id, med_a.id)
        db.session.commit()

        resp = client.post(
            f'/emar/administer/{row.id}',
            data={'medication_id': str(med_b.id)},
            headers={'Accept': 'application/json'},
        )

        _assert_arabic_409(resp, 'الدواء غير مطابق')

    def test_repeat_given_blocked_409_arabic(self, app, client, db, test_tenant):
        nurse = ensure_test_user(db, test_tenant, username='hr_nurse_rep', role='nurse')
        login_test_client(client, nurse, test_tenant)

        p1 = _mk_patient(db, test_tenant.id, f'HRPD{uuid.uuid4().hex[:8]}')
        med = _mk_medication(db, test_tenant.id, 'دواء-تكرار')
        row = _mk_emar(db, test_tenant.id, p1.id, med.id)
        db.session.commit()

        first = client.post(f'/emar/administer/{row.id}')
        assert first.status_code in (302, 303), first.status_code

        second = client.post(
            f'/emar/administer/{row.id}',
            headers={'Accept': 'application/json'},
        )
        _assert_arabic_409(second, 'مسبقاً')

    def test_refusal_stores_reason(self, app, client, db, test_tenant):
        nurse = ensure_test_user(db, test_tenant, username='hr_nurse_ref', role='nurse')
        login_test_client(client, nurse, test_tenant)

        p1 = _mk_patient(db, test_tenant.id, f'HRPE{uuid.uuid4().hex[:8]}')
        med = _mk_medication(db, test_tenant.id, 'دواء-رفض')
        row = _mk_emar(db, test_tenant.id, p1.id, med.id)
        db.session.commit()

        resp = client.post(
            f'/emar/administer/{row.id}',
            data={'status': 'REFUSED', 'refusal_reason': 'رفض المريض الدواء'},
            headers={'Accept': 'application/json'},
        )

        assert resp.status_code in (302, 303), resp.status_code
        db.session.refresh(row)
        assert row.status == 'REFUSED'
        assert row.refusal_reason == 'رفض المريض الدواء'

    def test_given_requires_scheduled_status(self, app, client, db, test_tenant):
        nurse = ensure_test_user(db, test_tenant, username='hr_nurse_held', role='nurse')
        login_test_client(client, nurse, test_tenant)

        p1 = _mk_patient(db, test_tenant.id, f'HRPF{uuid.uuid4().hex[:8]}')
        med = _mk_medication(db, test_tenant.id, 'دواء-معلق')
        row = _mk_emar(db, test_tenant.id, p1.id, med.id)
        row.status = 'HELD'
        db.session.commit()

        resp = client.post(
            f'/emar/administer/{row.id}',
            headers={'Accept': 'application/json'},
        )

        _assert_arabic_409(resp, 'مسبقاً')
        db.session.refresh(row)
        assert row.status == 'HELD'


@pytest.mark.usefixtures('rollback_db')
class TestOwnerRevealPasswordRestriction:
    def test_owner_role_denied_json(self, app, client, db, test_tenant):
        owner_u = ensure_test_user(db, test_tenant, username='hr_owner', role='owner')
        target = ensure_test_user(db, test_tenant, username='hr_target_o', role='reception')
        login_test_client(client, owner_u, test_tenant)

        resp = client.post(
            f'/owner/users/{target.id}/reveal-password',
            headers={'Accept': 'application/json'},
        )

        assert resp.status_code == 403, resp.status_code
        body = resp.get_json(silent=True) or {}
        assert body.get('success') is False, body
        assert 'غير متاح' in str(body.get('message')), body

    def test_super_admin_allowed_and_security_audit_written(self, app, client, db, test_tenant):
        sa = ensure_test_user(db, test_tenant, username='hr_superadmin', role='super_admin')
        target = ensure_test_user(db, test_tenant, username='hr_target_s', role='reception')
        login_test_client(client, sa, test_tenant)

        resp = client.post(f'/owner/users/{target.id}/reveal-password')

        assert resp.status_code in (302, 303), resp.status_code

        from models.audit_trail import AuditTrail

        row = (
            db.session.execute(
                select(AuditTrail)
                .where(AuditTrail.action == 'security', AuditTrail.entity_id == target.id)
                .order_by(AuditTrail.id.desc())
            )
            .scalars()
            .first()
        )
        assert row is not None
        assert row.entity_type == 'user'
        assert row.user_id == sa.id
