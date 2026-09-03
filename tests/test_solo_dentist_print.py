"""Solo dentist (private_doctor_clinic) self-print: bundle + own-patient only."""

from sqlalchemy import select

from app.core.tenant.models import ProductBundle
from app.extensions import db
from models.invoice import Invoice
from models.medication import Prescription
from models.patient import Patient
from models.visit import Visit


def test_private_doctor_bundle_includes_billing(app):
    with app.app_context():
        bundle = (
            db.session.execute(select(ProductBundle).filter_by(slug='private_doctor_clinic'))
            .scalars()
            .first()
        )
        assert bundle is not None
        modules = bundle.get_modules()
        assert 'doctor' in modules
        assert 'billing' in modules
        assert 'appointments' in modules


def _make_visit(app, test_tenant, doctor, patient):
    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        status='IN_PROGRESS',
        total_amount=100,
        paid_amount=100,
        payment_status='PAID',
    )
    db.session.add(visit)
    db.session.commit()
    return visit


def _make_patient(app, test_tenant, first='Solo', last='Dental'):
    patient = Patient(tenant_id=test_tenant.id, first_name=first, last_name=last)
    db.session.add(patient)
    db.session.commit()
    return patient


class TestSoloDentistPrint:
    def test_doctor_prints_own_invoice(self, app, client, test_tenant, login_as):
        from tests.tenant_context import ensure_test_user

        doctor = ensure_test_user(
            db, test_tenant, username='solo_dentist', role='doctor', password='test123'
        )
        doctor.set_password('test123')
        db.session.commit()
        patient = _make_patient(app, test_tenant)
        visit = _make_visit(app, test_tenant, doctor, patient)
        invoice = Invoice(
            tenant_id=test_tenant.id,
            visit_id=visit.id,
            invoice_number=f'INV-SOLO-{visit.id}',
            total_amount=100,
            paid_amount=100,
            status='PAID',
        )
        db.session.add(invoice)
        db.session.commit()

        login_as(client, 'solo_dentist', 'doctor')
        resp = client.get(f'/doctor/print-invoice/{invoice.id}')
        assert resp.status_code == 200

    def test_doctor_cannot_print_other_doctor_invoice(self, app, client, test_tenant, login_as):
        from tests.tenant_context import ensure_test_user

        ensure_test_user(
            db, test_tenant, username='solo_dentist_a', role='doctor', password='test123'
        )
        doctor_b = ensure_test_user(
            db, test_tenant, username='solo_dentist_b', role='doctor', password='test123'
        )
        patient = _make_patient(app, test_tenant, first='Other')
        visit = _make_visit(app, test_tenant, doctor_b, patient)
        invoice = Invoice(
            tenant_id=test_tenant.id,
            visit_id=visit.id,
            invoice_number=f'INV-OTHER-{visit.id}',
            total_amount=100,
            paid_amount=0,
            status='ISSUED',
        )
        db.session.add(invoice)
        db.session.commit()

        # Login as doctor A, try to print doctor B's invoice
        login_as(client, 'solo_dentist_a', 'doctor')
        resp = client.get(f'/doctor/print-invoice/{invoice.id}')
        assert resp.status_code in (302, 403)

    def test_doctor_prints_own_receipt(self, app, client, test_tenant, login_as):
        from tests.tenant_context import ensure_test_user

        doctor = ensure_test_user(
            db, test_tenant, username='solo_dentist_r', role='doctor', password='test123'
        )
        doctor.set_password('test123')
        db.session.commit()
        patient = _make_patient(app, test_tenant, first='Receipt')
        visit = _make_visit(app, test_tenant, doctor, patient)

        login_as(client, 'solo_dentist_r', 'doctor')
        resp = client.get(f'/doctor/print-receipt/{visit.id}')
        assert resp.status_code == 200, f'got {resp.status_code} loc={resp.location}'

    def test_doctor_prints_own_prescription(self, app, client, test_tenant, login_as):
        from tests.tenant_context import ensure_test_user

        doctor = ensure_test_user(
            db, test_tenant, username='solo_dentist_rx', role='doctor', password='test123'
        )
        doctor.set_password('test123')
        db.session.commit()
        patient = _make_patient(app, test_tenant, first='Rx')
        visit = _make_visit(app, test_tenant, doctor, patient)
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            visit_id=visit.id,
            prescription_number=f'RX-SOLO-{visit.id}',
            status='active',
        )
        db.session.add(rx)
        db.session.commit()

        login_as(client, 'solo_dentist_rx', 'doctor')
        resp = client.get(f'/doctor/print-prescription/{rx.id}')
        assert resp.status_code == 200

    def test_reception_still_prints_invoice(self, app, client, test_tenant, login_as):
        from tests.tenant_context import ensure_test_user

        doctor = ensure_test_user(
            db, test_tenant, username='solo_dentist_s', role='doctor', password='test123'
        )
        patient = _make_patient(app, test_tenant, first='Rec')
        visit = _make_visit(app, test_tenant, doctor, patient)
        invoice = Invoice(
            tenant_id=test_tenant.id,
            visit_id=visit.id,
            invoice_number=f'INV-REC-{visit.id}',
            total_amount=50,
            paid_amount=50,
            status='PAID',
        )
        db.session.add(invoice)
        db.session.commit()

        login_as(client, 'recv_solo_check', 'reception')
        resp = client.get(f'/reception/print_invoice/{invoice.id}')
        assert resp.status_code == 200
