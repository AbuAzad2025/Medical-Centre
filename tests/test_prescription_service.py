"""Exhaustive tests for services.prescription_service.PrescriptionService.

Includes coverage of three latent bugs fixed in this change:
  - check_patient_allergies (used a non-existent allergen_name/medication_id)
  - create_supply_request (wrote to non-existent columns)
  - log_action (wrong AuditTrail field names / missing required fields)
All DB work runs under ``rollback_db`` isolation.
"""
import uuid
import types

import pytest

from services.prescription_service import PrescriptionService as RX
from models.medication import Medication, PrescriptionItem
from models.drug_interaction import DrugInteraction
from models.patient import Patient, PatientAllergy
from models.user import User


@pytest.fixture
def rxfx(rollback_db):
    db = rollback_db

    def patient():
        p = Patient(first_name='ز', last_name='ت')
        db.session.add(p)
        db.session.commit()
        return p

    def doctor():
        un = 'zz_rx_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='د', role='doctor', is_active=True)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def med(trade='ZZTrade', sci='ZZSci', price=10, stock=100, min_stock=10):
        m = Medication(trade_name=trade + uuid.uuid4().hex[:4], scientific_name=sci,
                       dosage_form='tablet', strength='500mg', price=price,
                       stock_quantity=stock, minimum_stock=min_stock, category='general')
        db.session.add(m)
        db.session.commit()
        return m

    def allergy(patient_id, allergen):
        a = PatientAllergy(patient_id=patient_id, allergen=allergen, severity='high')
        db.session.add(a)
        db.session.commit()
        return a

    def interaction(a_id, b_id, severity='HIGH'):
        lo, hi = min(a_id, b_id), max(a_id, b_id)
        di = DrugInteraction(medication_a_id=lo, medication_b_id=hi, is_active=True,
                             severity=severity, description='تفاعل خطير')
        db.session.add(di)
        db.session.commit()
        return di

    return types.SimpleNamespace(db=db, patient=patient, doctor=doctor, med=med,
                                 allergy=allergy, interaction=interaction)


# ───────────────────────── interactions / allergies ─────────────────────────

class TestCheckInteractions:
    def test_empty_returns_empty(self, rxfx):
        assert RX.check_interactions([]) == []

    def test_no_interaction_rows(self, rxfx):
        m1, m2 = rxfx.med(), rxfx.med()
        assert RX.check_interactions([m1.id, m2.id]) == []

    def test_detects_interaction(self, rxfx):
        m1, m2 = rxfx.med(), rxfx.med()
        rxfx.interaction(m1.id, m2.id)
        warnings = RX.check_interactions([m1.id, m2.id])
        assert len(warnings) == 1
        assert warnings[0]['severity'] == 'HIGH'
        assert warnings[0]['a_name'] and warnings[0]['b_name']

    def test_ignores_falsy_ids(self, rxfx):
        assert RX.check_interactions([None, 0]) == []


class TestCheckPatientAllergies:
    def test_no_allergies(self, rxfx):
        p = rxfx.patient()
        m = rxfx.med()
        assert RX.check_patient_allergies(p.id, [m.id]) == []

    def test_detects_conflict_by_name(self, rxfx):
        p = rxfx.patient()
        m = rxfx.med(trade='Amoxil', sci='Amoxicillin')
        rxfx.allergy(p.id, 'Amoxicillin')
        conflicts = RX.check_patient_allergies(p.id, [m.id])
        assert len(conflicts) == 1
        assert conflicts[0]['allergen'] == 'Amoxicillin'
        assert conflicts[0]['medication_id'] == m.id

    def test_no_conflict_when_unrelated(self, rxfx):
        p = rxfx.patient()
        m = rxfx.med(trade='Panadol', sci='Paracetamol')
        rxfx.allergy(p.id, 'Penicillin')
        assert RX.check_patient_allergies(p.id, [m.id]) == []


# ───────────────────────── prescription creation ─────────────────────────

class TestCreatePrescription:
    def test_success_with_items(self, rxfx):
        p = rxfx.patient()
        doc = rxfx.doctor()
        m = rxfx.med(price=10)
        ok, pres = RX.create_prescription(
            p.id, doc.id, items=[{'medication_id': m.id, 'dosage': '1x2', 'quantity': 3,
                                  'duration_days': 5}])
        assert ok is True
        items = PrescriptionItem.query.filter_by(prescription_id=pres.id).all()
        assert len(items) == 1
        assert float(items[0].total_price) == 30.0

    def test_medication_not_found(self, rxfx):
        p = rxfx.patient()
        doc = rxfx.doctor()
        ok, msg = RX.create_prescription(p.id, doc.id, items=[{'medication_id': 99999999}])
        assert ok is False and 'not found' in msg

    def test_no_items_still_creates(self, rxfx):
        p = rxfx.patient()
        doc = rxfx.doctor()
        ok, pres = RX.create_prescription(p.id, doc.id)
        assert ok is True
        assert pres.prescription_number.startswith('RX-')

    def test_exception_returns_false(self, rxfx):
        p = rxfx.patient()
        doc = rxfx.doctor()
        m = rxfx.med()
        ok, msg = RX.create_prescription(
            p.id, doc.id, items=[{'medication_id': m.id, 'quantity': 'not-a-number'}])
        assert ok is False
        assert isinstance(msg, str)


class TestPrescriptionQueries:
    def test_get_active_prescriptions(self, rxfx):
        p = rxfx.patient()
        doc = rxfx.doctor()
        RX.create_prescription(p.id, doc.id)
        active = RX.get_active_prescriptions(p.id)
        assert len(active) >= 1

    def test_get_prescriptions_by_doctor(self, rxfx):
        p = rxfx.patient()
        doc = rxfx.doctor()
        RX.create_prescription(p.id, doc.id)
        assert len(RX.get_prescriptions_by_doctor(doc.id)) >= 1

    def test_get_prescription_and_medication(self, rxfx):
        p = rxfx.patient()
        doc = rxfx.doctor()
        m = rxfx.med()
        ok, pres = RX.create_prescription(p.id, doc.id)
        assert RX.get_prescription(pres.id).id == pres.id
        assert RX.get_medication(m.id).id == m.id


# ───────────────────────── inventory ─────────────────────────

class TestInventory:
    def test_low_stock(self, rxfx):
        m = rxfx.med(stock=2, min_stock=10)
        low = RX.get_low_stock_medications(limit=10000)
        assert any(x.id == m.id for x in low)

    def test_search_medications(self, rxfx):
        m = rxfx.med(trade='UniqXyz', sci='UniqSci')
        results = RX.search_medications('UniqXyz')
        assert any(x.id == m.id for x in results)

    def test_update_stock_success(self, rxfx):
        m = rxfx.med(stock=50)
        assert RX.update_stock(m.id, -5) is True
        assert float(Medication.query.get(m.id).stock_quantity) == 45.0

    def test_update_stock_not_found(self, rxfx):
        assert RX.update_stock(99999999, 5) is False


# ───────────────────────── supply requests ─────────────────────────

class TestSupplyRequests:
    def test_create_supply_request_success(self, rxfx):
        m = rxfx.med()
        doc = rxfx.doctor()
        req = RX.create_supply_request(m.id, 20, requested_by=doc.id, notes='restock')
        assert req is not None
        assert req.request_number.startswith('SR-')

    def test_create_supply_request_med_not_found(self, rxfx):
        doc = rxfx.doctor()
        assert RX.create_supply_request(99999999, 20, requested_by=doc.id) is None

    def test_get_supply_requests(self, rxfx):
        m = rxfx.med()
        doc = rxfx.doctor()
        RX.create_supply_request(m.id, 5, requested_by=doc.id)
        results = RX.get_supply_requests()
        assert isinstance(results, list) and len(results) >= 1

    def test_get_supply_requests_filtered(self, rxfx):
        results = RX.get_supply_requests(status='PENDING')
        assert all(r.status == 'PENDING' for r in results)


# ───────────────────────── misc / audit ─────────────────────────

class TestMiscAndAudit:
    def test_log_action_persists(self, rxfx):
        doc = rxfx.doctor()
        RX.log_action('prescription_created', 'some details', user_id=doc.id)
        from models.audit_trail import AuditTrail
        row = (AuditTrail.query.filter_by(user_id=doc.id)
               .order_by(AuditTrail.id.desc()).first())
        assert row is not None
        assert 'prescription_created' in row.description
        assert 'some details' in row.description

    def test_notify_pharmacy_non_catalog_no_raise(self, rxfx):
        # wrapped in try/except — must never raise regardless of notification setup
        RX.notify_pharmacy_non_catalog('SomeDrug', 'Dr X', visit_id=1)
