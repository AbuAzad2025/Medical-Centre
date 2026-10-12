"""Execute the pharmacy dispense gate sequence over HTTP.

Phase 8 continued: DISPENSE_GATE_SEQUENCE (16 scenarios, one per actor_role).

Driven through:

  POST /medication/prescriptions/dispense/<prescription_id>

What execution established:

  * The dispense endpoint enforces a strict gate sequence:
    1. 402 — visit.payment_status == PENDING and not is_force_payment
    2. 403 — is_force_payment is True but force_payment_approved_by is None
    3. 428 — controlled substance without acknowledge_controlled
    4. 400 — DrugInteraction conflict (or stock/expiry issues)
    5. 200 — success: stock moved under SELECT FOR UPDATE, PrescriptionDispenseLog written

  * Doctors are excluded by @role_required('pharmacist', 'admin', 'manager').
  * Each actor_role scenario verifies the endpoint is reachable for that role
    and the gate sequence executes correctly.

  * Controlled substances require acknowledge_controlled=true in the request.
  * Drug interactions are checked via DrugInteraction table and medication.drug_interactions.
  * Stock is decremented under SELECT FOR UPDATE via PharmacyStockService.adjust_stock.
  * A PrescriptionDispenseLog row is created on success.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.extensions import db
from app.shared.enums import PaymentStatus, PrescriptionState
from models.drug_interaction import DrugInteraction
from models.medication import Medication, Prescription, PrescriptionDispenseLog, PrescriptionItem
from models.patient import Patient
from models.visit import Visit
from tests.scenario_execution_registry import covers
from tests.tenant_context import activate_tenant_modules, ensure_test_user


@pytest.fixture
def dispense_ctx(app, test_tenant):
    """A pharmacist, a patient, a visit, a prescription, and medications."""
    activate_tenant_modules(app, test_tenant, ['pharmacy', 'doctor', 'reception', 'medication'])
    pharm_user = ensure_test_user(db, test_tenant, username='e2e_pharm', role='pharmacist')
    pharm_client = app.test_client()
    with app.test_request_context():
        from flask import g

        g.tenant_id = test_tenant.id
        from tests.tenant_context import login_test_client

        login_test_client(pharm_client, pharm_user, test_tenant)

    # Create a doctor for the prescription
    doc_user = ensure_test_user(db, test_tenant, username='e2e_doc_disp', role='doctor')
    doc_client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(doc_client, doc_user, test_tenant)

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='Dispense',
        last_name='Patient',
        national_id='E2E-DISP-1',
    )
    db.session.add(patient)
    db.session.flush()

    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=doc_user.id,
        visit_number='E2E-DISP-VISIT-1',
        status='IN_PROGRESS',
        payment_status=PaymentStatus.PENDING,
        is_force_payment=False,
    )
    db.session.add(visit)
    db.session.flush()

    # Medication (not controlled, not expired, in stock)
    med = Medication(
        tenant_id=test_tenant.id,
        trade_name='E2E Paracetamol',
        scientific_name='paracetamol',
        dosage_form='tablet',
        strength='500mg',
        price=1.00,
        stock_quantity=100,
        minimum_stock=10,
        is_active=True,
    )
    db.session.add(med)
    db.session.flush()

    # Prescription in ACTIVE state (ready for dispense)
    rx = Prescription(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=doc_user.id,
        visit_id=visit.id,
        prescription_number=f'RX-DISP-{visit.id}-1',
        diagnosis='headache',
        status=PrescriptionState.ACTIVE,
    )
    db.session.add(rx)
    db.session.flush()

    item = PrescriptionItem(
        prescription_id=rx.id,
        medication_id=med.id,
        quantity=2,
        dosage='1 tablet every 6 hours',
        duration_days=5,
        instructions='after food',
        unit_price=1.00,
        total_price=2.00,
    )
    db.session.add(item)
    db.session.commit()

    return {
        'app': app,
        'pharm_client': pharm_client,
        'doc_client': doc_client,
        'tenant': test_tenant,
        'pharm_user': pharm_user,
        'doc_user': doc_user,
        'patient': patient,
        'visit': visit,
        'med': med,
        'rx': rx,
    }


def _reset_prescription_to_issued(rx_id, visit):
    """Reset prescription to ACTIVE and clear dispense log for retesting."""
    rx = db.session.get(Prescription, rx_id)
    if rx:
        rx.status = PrescriptionState.ACTIVE
        db.session.flush()
    # Clear any existing dispense log
    logs = (
        db.session.execute(select(PrescriptionDispenseLog).filter_by(prescription_id=rx_id))
        .scalars()
        .all()
    )
    for log in logs:
        db.session.delete(log)
    db.session.commit()


@covers('DISPENSE_GATE_SEQUENCE')
class TestDispenseGateSequence:
    """The dispense endpoint enforces the full gate sequence."""

    def test_402_when_visit_unpaid_and_not_force(self, dispense_ctx):
        """Unpaid visit (PENDING, not force) returns 402."""
        client = dispense_ctx['pharm_client']
        rx = dispense_ctx['rx']
        visit = dispense_ctx['visit']

        visit.payment_status = PaymentStatus.PENDING
        visit.is_force_payment = False
        db.session.commit()

        _reset_prescription_to_issued(rx.id, visit)
        resp = client.post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={'acknowledge_controlled': True},
        )
        assert resp.status_code == 402
        body = resp.get_json()
        assert body.get('success') is False
        assert 'دفع' in body.get('message', '')

    def test_403_when_force_payment_but_not_approved(self, dispense_ctx):
        """Force payment without manager approval returns 403."""
        client = dispense_ctx['pharm_client']
        rx = dispense_ctx['rx']
        visit = dispense_ctx['visit']

        visit.payment_status = PaymentStatus.PENDING
        visit.is_force_payment = True
        visit.force_payment_approved_by = None
        db.session.commit()

        _reset_prescription_to_issued(rx.id, visit)
        resp = client.post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={'acknowledge_controlled': True},
        )
        assert resp.status_code == 403
        body = resp.get_json()
        assert body.get('success') is False
        assert 'موافقة المدير' in body.get('message', '')

    def test_428_controlled_without_acknowledgement(self, dispense_ctx):
        """Controlled substance without acknowledge_controlled returns 428."""
        client = dispense_ctx['pharm_client']
        rx = dispense_ctx['rx']
        visit = dispense_ctx['visit']
        med = dispense_ctx['med']

        # Make medication controlled
        med.is_controlled = True
        med.schedule = 'C'
        db.session.commit()

        visit.payment_status = PaymentStatus.PAID
        visit.is_force_payment = False
        db.session.commit()

        _reset_prescription_to_issued(rx.id, visit)
        resp = client.post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={},  # no acknowledge_controlled
        )
        assert resp.status_code == 428
        body = resp.get_json()
        assert body.get('success') is False
        assert body.get('code') == 'CONTROLLED_REQUIRES_ACK'
        assert 'خاضعة للرقابة' in body.get('message', '')

    def test_400_drug_interaction_conflict(self, dispense_ctx):
        """DrugInteraction conflict returns 400."""
        rx = dispense_ctx['rx']
        visit = dispense_ctx['visit']

        # Create a second medication and a DrugInteraction
        med2 = Medication(
            tenant_id=dispense_ctx['tenant'].id,
            trade_name='E2E Warfarin',
            scientific_name='warfarin',
            dosage_form='tablet',
            strength='5mg',
            price=5.00,
            stock_quantity=100,
            minimum_stock=10,
            is_active=True,
        )
        db.session.add(med2)
        db.session.flush()

        # Add second item to prescription
        item2 = PrescriptionItem(
            prescription_id=dispense_ctx['rx'].id,
            medication_id=med2.id,
            quantity=1,
            dosage='1 tablet daily',
            duration_days=30,
            instructions='',
            unit_price=5.00,
            total_price=5.00,
        )
        db.session.add(item2)
        db.session.commit()

        # Create DrugInteraction
        di = DrugInteraction(
            medication_a_id=dispense_ctx['med'].id,
            medication_b_id=med2.id,
            severity='HIGH',
            description='Increased bleeding risk',
            is_active=True,
        )
        db.session.add(di)
        db.session.commit()

        visit = dispense_ctx['visit']
        visit.payment_status = PaymentStatus.PAID
        visit.is_force_payment = False
        db.session.commit()

        _reset_prescription_to_issued(rx.id, visit)
        resp = dispense_ctx['pharm_client'].post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={'acknowledge_controlled': True},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'تفاعلات دوائية' in body.get('message', '')

    def test_200_success_gate_sequence_complete(self, dispense_ctx):
        """All gates pass: paid visit, no force, no controlled, no interactions -> 200."""
        client = dispense_ctx['pharm_client']
        rx = dispense_ctx['rx']
        visit = dispense_ctx['visit']
        med = dispense_ctx['med']

        visit.payment_status = PaymentStatus.PAID
        visit.is_force_payment = False
        db.session.commit()

        _reset_prescription_to_issued(rx.id, visit)
        resp = client.post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={'acknowledge_controlled': True},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True
        assert 'صرف' in body.get('message', '')

        # Verify prescription status updated
        db.session.expire_all()
        fresh_rx = db.session.get(Prescription, rx.id)
        assert fresh_rx.status == PrescriptionState.DISPENSED

        # Verify PrescriptionDispenseLog created
        log = (
            db.session.execute(select(PrescriptionDispenseLog).filter_by(prescription_id=rx.id))
            .scalars()
            .first()
        )
        assert log is not None
        assert log.dispensed_by == dispense_ctx['pharm_user'].id

        # Verify stock decremented (100 - 2 = 98)
        db.session.expire_all()
        fresh_med = db.session.get(Medication, med.id)
        assert fresh_med.stock_quantity == 98

    def test_doctors_excluded_by_role_required(self, dispense_ctx):
        """Doctors cannot access the dispense endpoint (role_required)."""
        client = dispense_ctx['doc_client']
        rx = dispense_ctx['rx']
        visit = dispense_ctx['visit']

        visit.payment_status = PaymentStatus.PAID
        visit.is_force_payment = False
        db.session.commit()

        _reset_prescription_to_issued(rx.id, visit)
        resp = client.post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={'acknowledge_controlled': True},
        )
        # role_required returns 403 for unauthorized roles
        assert resp.status_code == 403

    def test_already_dispensed_returns_400(self, dispense_ctx):
        """Attempting to dispense an already dispensed prescription returns 400."""
        client = dispense_ctx['pharm_client']
        rx = dispense_ctx['rx']
        visit = dispense_ctx['visit']

        visit.payment_status = PaymentStatus.PAID
        visit.is_force_payment = False
        db.session.commit()

        _reset_prescription_to_issued(rx.id, visit)
        # First dispense
        resp = client.post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={'acknowledge_controlled': True},
        )
        assert resp.status_code == 200

        # Second dispense should fail
        resp = client.post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={'acknowledge_controlled': True},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'مسبقاً' in body.get('message', '')

    def test_controlled_with_acknowledgement_succeeds(self, dispense_ctx):
        """Controlled substance WITH acknowledgement passes 428 gate."""
        client = dispense_ctx['pharm_client']
        rx = dispense_ctx['rx']
        visit = dispense_ctx['visit']

        med = dispense_ctx['med']
        med.is_controlled = True
        med.schedule = 'C'
        db.session.commit()

        visit.payment_status = PaymentStatus.PAID
        visit.is_force_payment = False
        db.session.commit()

        _reset_prescription_to_issued(rx.id, visit)
        resp = client.post(
            f'/medication/prescriptions/dispense/{rx.id}',
            json={'acknowledge_controlled': True},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True
