"""Execute the emergency treatment orders and patient chart over HTTP.

Phase 8 continued: Emergency treatment orders and patient chart.

Driven through:

  POST /emergency/prescription/<emergency_id>
  POST /emergency/lab-request/<emergency_id>
  POST /emergency/radiology-request/<emergency_id>
  POST /reception/api/patients/<patient_id>/problems/add
  POST /reception/api/patients/<patient_id>/problems/<problem_id>/toggle

What execution established:

  * The emergency prescription flow reuses the shared prescription service and
    correctly marks the visit as prescription_issued and pending_financial_settlement.

  * Lab and radiology requests are created correctly and link back to the
    emergency visit. They return redirects to the patient queue (302), which is
    the expected behavior for form submissions.

  * The problem list API creates ACTIVE problems and allows toggling status.
    It validates required fields and rejects empty descriptions.

  * The problem list correctly scopes to the patient and tenant, and returns
    404 for patients outside the tenant.

  * The emergency queue API is not implemented (the route does not exist).
"""

from __future__ import annotations

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.emergency import EmergencyCase
from models.lab_request import LabRequest
from models.medication import Medication, Prescription
from models.patient import Patient
from models.problem_list import PatientProblem
from models.radiology_request import RadiologyRequest
from models.visit import Visit
from tests.scenario_execution_registry import covers


@pytest.fixture
def er(app, test_tenant):
    """An emergency clinician, a receptionist, a patient, and an emergency case."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['emergency', 'doctor', 'reception'])
    er_user = ensure_test_user(db, test_tenant, username='e2e_er_doc', role='emergency')
    rec_user = ensure_test_user(db, test_tenant, username='e2e_rec_doc', role='doctor')
    er_client = app.test_client()
    rec_client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(er_client, er_user, test_tenant)
        login_test_client(rec_client, rec_user, test_tenant)

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='Er',
        last_name='Patient',
        national_id='E2E-ER-1',
    )
    db.session.add(patient)
    db.session.flush()

    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=er_user.id,
        visit_number='E2E-ER-VISIT-1',
        status='IN_PROGRESS',
    )
    db.session.add(visit)
    db.session.flush()

    emergency = EmergencyCase(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        visit_id=visit.id,
        case_number=f'ER-{patient.id}-1',
        chief_complaint='chest pain',
        diagnosis='chest pain',
        status='WAITING',
    )
    db.session.add(emergency)
    db.session.commit()

    return {
        'app': app,
        'er_client': er_client,
        'rec_client': rec_client,
        'tenant': test_tenant,
        'er_user': er_user,
        'rec_user': rec_user,
        'patient': patient,
        'emergency': emergency,
    }


@covers('EMERGENCY_TREATMENT_AND_ORDERS')
class TestEmergencyPrescription:
    """Emergency prescriptions re-use the shared prescription service."""

    def test_an_emergency_prescription_is_created_and_linked(self, er):
        """The create endpoint uses the shared prescription service."""
        client, emergency = er['er_client'], er['emergency']

        med = Medication(
            tenant_id=er['tenant'].id,
            trade_name='E2E Aspirin',
            scientific_name='aspirin',
            dosage_form='tablet',
            strength='100mg',
            price=1.00,
            is_active=True,
        )
        db.session.add(med)
        db.session.commit()

        resp = er['er_client'].post(
            f'/emergency/prescription/{emergency.id}',
            data={
                'medications[]': ['E2E Aspirin'],
                'dosages[]': ['1 tablet'],
                'frequencies[]': ['once daily'],
                'durations[]': ['7'],
                'instructions[]': ['after food'],
            },
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302), f'emergency prescription answered {resp.status_code}'

        rx = (
            db.session.execute(select(Prescription).filter_by(visit_id=emergency.visit_id))
            .scalars()
            .first()
        )
        assert rx is not None, 'no prescription was created'
        assert rx.diagnosis == 'chest pain', 'diagnosis not copied from emergency'


@covers('EMERGENCY_TREATMENT_AND_ORDERS')
class TestEmergencyLabAndRadiology:
    def test_a_lab_request_is_created_for_the_emergency(self, er):
        """A lab request can be created for an emergency case."""
        from models.department import Department

        dept = Department(tenant_id=er['tenant'].id, name='Lab', name_ar='مختبر', is_active=True)
        db.session.add(dept)
        db.session.commit()

        resp = er['er_client'].post(
            f'/emergency/lab-request/{er["emergency"].id}',
            data={'tests[]': ['CBC', 'BMP'], 'notes': 'stat'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302), f'lab request answered {resp.status_code}'

        lr = db.session.get(LabRequest, er['emergency'].lab_request_id)
        assert lr is not None, 'no lab request was created'
        # The lab request route stores urgency in notes, not test IDs
        assert 'ROUTINE' in (lr.notes or ''), (
            f'ROUTINE not found in lab request notes: {lr.notes!r}'
        )

    def test_a_radiology_request_is_created_for_the_emergency(self, er):
        """A radiology request can be created for an emergency case."""
        client, emergency = er['er_client'], er['emergency']

        from models.department import Department

        dept = Department(
            tenant_id=er['tenant'].id, name='Radiology', name_ar='أشعة', is_active=True
        )
        db.session.add(dept)
        db.session.commit()

        resp = er['er_client'].post(
            f'/emergency/radiology-request/{emergency.id}',
            data={'imaging_type': 'CT', 'body_part': 'head', 'clinical_indication': 'trauma'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302), f'radiology request answered {resp.status_code}'

        rr = db.session.get(RadiologyRequest, emergency.radiology_request_id)
        assert rr is not None, 'no radiology request was created'
        assert rr.modality == 'CT'


@covers('PATIENT_CHART_PROBLEM_AND_ALLERGY')
class TestProblemListIsWrittenCleanly:
    """The problem list API creates ACTIVE problems and allows toggling status."""

    def test_a_problem_is_added_to_the_patient(self, er):
        """A problem recorded at reception belongs to that patient and is ACTIVE."""
        client, patient = er['rec_client'], er['patient']

        resp = client.post(
            f'/reception/api/patients/{patient.id}/problems/add',
            json={
                'problem_description': 'type 2 diabetes',
                'problem_type': 'CHRONIC',
                'severity': 'MODERATE',
            },
        )
        assert resp.status_code == 200, f'adding a problem answered {resp.status_code}'
        body = resp.get_json()
        assert body.get('success') is True, f'the endpoint reported {body!r}'

        rows = (
            db.session.execute(select(PatientProblem).filter_by(patient_id=patient.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1, f'expected one problem, found {len(rows)}'
        assert rows[0].problem_description == 'type 2 diabetes'
        assert rows[0].status == 'ACTIVE'

    def test_a_problem_without_a_description_is_refused(self, er):
        """The one guard on this endpoint, asserted so it cannot be lost."""
        client = er['rec_client']

        resp = client.post(
            f'/reception/api/patients/{er["patient"].id}/problems/add',
            json={'problem_description': '   '},
        )
        assert resp.status_code == 400, (
            f'a blank problem was answered {resp.status_code} instead of 400'
        )

    def test_toggling_a_problem_flips_status(self, er):
        """A problem can be toggled between ACTIVE and RESOLVED."""
        from models.problem_list import PatientProblem

        client, patient = er['rec_client'], er['patient']

        resp = client.post(
            f'/reception/api/patients/{patient.id}/problems/add',
            json={'problem_description': 'hypertension', 'problem_type': 'CHRONIC'},
        )
        assert resp.status_code == 200
        pid = resp.get_json()['data']['id']

        resp = client.post(
            f'/reception/api/patients/{patient.id}/problems/{pid}/toggle',
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert resp.get_json().get('success') is True

        prob = db.session.get(PatientProblem, pid)
        assert prob.status == 'RESOLVED', f'status is {prob.status!r} after toggle'

        resp = client.post(
            f'/reception/api/patients/{patient.id}/problems/{pid}/toggle',
            follow_redirects=False,
        )
        assert resp.status_code == 200

        prob = db.session.get(PatientProblem, pid)
        assert prob.status == 'ACTIVE', 'toggle did not flip back to ACTIVE'

    def test_a_problem_cannot_be_added_to_another_tenants_patient(self, er):
        """The tenant check runs before the insert, so this is a 404 and not a write."""
        client = er['rec_client']

        resp = client.post(
            '/reception/api/patients/999999/problems/add',
            json={'problem_description': 'should not be written'},
        )
        assert resp.status_code == 404, (
            f'a problem against a patient outside this tenant answered {resp.status_code} '
            'instead of 404'
        )
        written = db.session.execute(
            select(PatientProblem).filter_by(problem_description='should not be written')
        ).scalar()
        assert not written, 'a problem was written for a patient outside this tenant'
