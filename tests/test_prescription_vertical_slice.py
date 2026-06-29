"""Tests for P2-002: Prescription Vertical Slice."""

import pytest

from app_factory import db as _db
from models.medication import Medication, Prescription, PrescriptionItem
from models.patient import Patient
from models.user import User
from models.visit import Visit
from services.prescription_service import PrescriptionService


@pytest.fixture(scope='function')
def rx_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Rx',
        last_name='Patient',
        phone='0500000020',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def rx_doctor(app, test_tenant):
    u = User.query.filter_by(username='rx_doctor').first()
    if not u:
        u = User(
            username='rx_doctor',
            email='rx_doc@example.com',
            full_name='Dr. Rx',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def rx_visit(app, test_tenant, rx_patient, rx_doctor):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=rx_patient.id,
        doctor_id=rx_doctor.id,
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


@pytest.fixture(scope='function')
def rx_medications(app, test_tenant):
    meds = []
    for trade, price in [('RxAmoxicillin', 15), ('RxParacetamol', 5)]:
        m = Medication.query.filter_by(tenant_id=test_tenant.id, trade_name=trade).first()
        if not m:
            m = Medication(
                tenant_id=test_tenant.id,
                trade_name=trade,
                scientific_name=trade.lower(),
                dosage_form='tablet',
                strength='500mg',
                price=price,
                stock_quantity=100,
                minimum_stock=10,
                category='general',
            )
            _db.session.add(m)
        meds.append(m)
    _db.session.commit()
    return meds


class TestPrescriptionServiceCreatePrescription:
    def test_creates_prescription_with_items(self, rx_visit, rx_doctor, rx_medications, test_tenant):
        items = [
            {
                'medication_id': rx_medications[0].id,
                'dosage': '1 tablet | 3 times daily',
                'quantity': 2,
                'duration_days': 7,
                'instructions': 'After food',
            }
        ]
        ok, result = PrescriptionService.create_prescription(
            patient_id=rx_visit.patient_id,
            doctor_id=rx_doctor.id,
            visit_id=rx_visit.id,
            tenant_id=test_tenant.id,
            items=items,
            notes='Test prescription',
        )
        assert ok is True
        prescription = result
        assert prescription.patient_id == rx_visit.patient_id
        assert prescription.doctor_id == rx_doctor.id
        assert prescription.visit_id == rx_visit.id
        assert prescription.tenant_id == test_tenant.id
        assert prescription.status == 'active'

        item = PrescriptionItem.query.filter_by(prescription_id=prescription.id).first()
        assert item is not None
        assert item.medication_id == rx_medications[0].id
        assert item.quantity == 2
        assert item.duration_days == 7
        assert item.unit_price == 15
        assert item.total_price == 30
        assert item.tenant_id == test_tenant.id
        assert prescription.total_cost == 30

    def test_computes_total_for_multiple_items(self, rx_visit, rx_doctor, rx_medications, test_tenant):
        items = [
            {'medication_id': rx_medications[0].id, 'dosage': '1', 'quantity': 1, 'duration_days': 5},
            {'medication_id': rx_medications[1].id, 'dosage': '1', 'quantity': 2, 'duration_days': 3},
        ]
        ok, result = PrescriptionService.create_prescription(
            patient_id=rx_visit.patient_id,
            doctor_id=rx_doctor.id,
            visit_id=rx_visit.id,
            tenant_id=test_tenant.id,
            items=items,
        )
        assert ok is True
        assert result.total_cost == 25  # 15 + 2*5

    def test_rejects_unknown_medication(self, rx_visit, rx_doctor, test_tenant):
        items = [{'medication_id': 999999, 'dosage': '1', 'quantity': 1, 'duration_days': 5}]
        ok, result = PrescriptionService.create_prescription(
            patient_id=rx_visit.patient_id,
            doctor_id=rx_doctor.id,
            visit_id=rx_visit.id,
            tenant_id=test_tenant.id,
            items=items,
        )
        assert ok is False
        assert 'not found' in result


class TestDoctorPrescriptionRoute:
    def test_creates_prescription_via_route(self, app, client, rx_visit, rx_doctor, rx_medications, test_tenant):
        from tests.tenant_context import login_test_client

        login_test_client(client, rx_doctor, test_tenant)
        resp = client.post(f'/doctor/prescription/{rx_visit.id}', data={
            'item_medication_id[]': [str(rx_medications[0].id)],
            'item_dosage[]': ['1 tablet'],
            'item_frequency[]': ['3 times daily'],
            'item_duration_days[]': ['7'],
            'item_quantity[]': ['2'],
            'item_instructions[]': ['After food'],
        })
        assert resp.status_code in (200, 302)

        prescription = Prescription.query.filter_by(visit_id=rx_visit.id).first()
        assert prescription is not None
        assert prescription.tenant_id == test_tenant.id
        items = PrescriptionItem.query.filter_by(prescription_id=prescription.id).all()
        assert len(items) == 1
        assert items[0].total_price == 30

    def test_legacy_single_medication_form(self, app, client, rx_visit, rx_doctor, rx_medications, test_tenant):
        from tests.tenant_context import login_test_client

        login_test_client(client, rx_doctor, test_tenant)
        resp = client.post(f'/doctor/prescription/{rx_visit.id}', data={
            'medication_name': rx_medications[1].trade_name,
            'dosage': '1 tablet',
            'frequency': 'twice daily',
            'duration': '5 days',
            'instructions': 'With water',
        })
        assert resp.status_code in (200, 302)
        prescription = Prescription.query.filter_by(visit_id=rx_visit.id).first()
        assert prescription is not None
        items = PrescriptionItem.query.filter_by(prescription_id=prescription.id).all()
        assert len(items) == 1
        assert items[0].medication_id in {m.id for m in rx_medications}
