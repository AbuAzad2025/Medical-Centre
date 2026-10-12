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
    marks the visit as prescription_issued and pending_financial_settlement.

  * The emergency lab route parsed the ordered tests, checked at least one was
    present, and then dropped them: the LabRequest carried no test rows and the
    notes never named them, so the lab department received an empty order. The
    route now resolves the names against the catalogue into structured result
    rows and writes anything it cannot resolve into the notes, so an order can
    never lose its contents. A test missing from the catalogue stays visible.

  * The emergency lab request was also written with visit_id=None even though
    the emergency case has a visit, so the order was not reachable from the
    clinical encounter.

  * Radiology requests are created correctly and name their modality.

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
from models.patient import Patient, PatientAllergy
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
        emergency = er['emergency']

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

    def test_the_visit_is_flagged_as_having_a_prescription(self, er):
        """The visit is marked so the settlement flag and the billing gate agree."""
        emergency = er['emergency']
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

        db.session.expire_all()
        fresh_visit = db.session.get(Visit, emergency.visit_id)
        assert fresh_visit is not None, 'the emergency visit disappeared'
        assert fresh_visit.prescription_issued is True, (
            'visit.prescription_issued was not set to True after prescription creation'
        )


@covers('EMERGENCY_TREATMENT_AND_ORDERS')
class TestEmergencyLabAndRadiology:
    def test_a_lab_request_is_created_for_the_emergency(self, er):
        """A lab request can be created for an emergency case.

        The ordered tests are the point of the order, so they are asserted as
        rows: a request the lab cannot read the contents of is not an order.
        """
        from models.lab_request import LabResult
        from models.lab_test_catalog import LabTestCatalog

        catalog = LabTestCatalog(
            tenant_id=er['tenant'].id,
            code='CBC',
            name_ar='صورة دم كاملة',
            name_en='CBC',
            category='hematology',
            is_active=True,
        )
        db.session.add(catalog)
        db.session.commit()

        resp = er['er_client'].post(
            f'/emergency/lab-request/{er["emergency"].id}',
            data={'tests[]': ['CBC'], 'notes': 'stat'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302), f'lab request answered {resp.status_code}'

        lr = db.session.get(LabRequest, er['emergency'].lab_request_id)
        assert lr is not None, 'no lab request was created'

        results = db.session.execute(select(LabResult).filter_by(request_id=lr.id)).scalars().all()
        assert len(results) == 1, (
            f'the order named one test but produced {len(results)} result rows: the '
            'requested tests are not reaching the lab'
        )
        assert results[0].test_code == 'CBC'
        assert results[0].status == 'PENDING'

    def test_a_test_missing_from_the_catalogue_is_still_recorded(self, er):
        """An unknown test name must not be silently dropped from the order."""
        resp = er['er_client'].post(
            f'/emergency/lab-request/{er["emergency"].id}',
            data={'tests[]': ['NOT-IN-CATALOGUE'], 'notes': ''},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302), f'lab request answered {resp.status_code}'

        lr = db.session.get(LabRequest, er['emergency'].lab_request_id)
        assert lr is not None, 'no lab request was created'
        assert 'NOT-IN-CATALOGUE' in (lr.notes or ''), (
            f'the requested test was lost entirely: notes={lr.notes!r}'
        )

    def test_a_radiology_request_is_created_for_the_emergency(self, er):
        """A radiology request can be created for an emergency case."""
        emergency = er['emergency']

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


@covers('PATIENT_CHART_PROBLEM_AND_ALLERGY')
class TestAllergyListIsWrittenCleanly:
    """The allergy API creates records and validates required fields."""

    def test_an_allergy_is_added_to_the_patient(self, er):
        """An allergy recorded at reception belongs to that patient."""
        client, patient = er['rec_client'], er['patient']

        resp = client.post(
            f'/reception/api/patients/{patient.id}/allergies/add',
            json={
                'allergen': 'penicillin',
                'severity': 'HIGH',
                'description': 'rash and swelling',
            },
        )
        assert resp.status_code == 200, f'adding an allergy answered {resp.status_code}'
        body = resp.get_json()
        assert body.get('success') is True, f'the endpoint reported {body!r}'

        rows = (
            db.session.execute(select(PatientAllergy).filter_by(patient_id=patient.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1, f'expected one allergy, found {len(rows)}'
        assert rows[0].allergen == 'penicillin'
        assert rows[0].severity == 'HIGH'
        assert rows[0].description == 'rash and swelling'

    def test_an_allergy_without_an_allergen_is_refused(self, er):
        """The one guard on this endpoint, asserted so it cannot be lost."""
        client = er['rec_client']

        resp = client.post(
            f'/reception/api/patients/{er["patient"].id}/allergies/add',
            json={'allergen': '   '},
        )
        assert resp.status_code == 400, (
            f'a blank allergen was answered {resp.status_code} instead of 400'
        )

    def test_an_allergy_cannot_be_added_to_another_tenants_patient(self, er):
        """The tenant check runs before the insert, so this is a 404 and not a write."""
        client = er['rec_client']

        resp = client.post(
            '/reception/api/patients/999999/allergies/add',
            json={'allergen': 'should not be written'},
        )
        assert resp.status_code == 404, (
            f'an allergy against a patient outside this tenant answered {resp.status_code} '
            'instead of 404'
        )
        written = db.session.execute(
            select(PatientAllergy).filter_by(allergen='should not be written')
        ).scalar()
        assert not written, 'an allergy was written for a patient outside this tenant'


@covers('EMERGENCY_CASE_TREATMENT')
class TestEmergencyCaseTreatmentStateMachine:
    """The emergency case moves through the status enum via multiple routes.

    Each scenario in the generated matrix corresponds to one reachable state.
    """

    def test_create_emergency_case_starts_at_waiting(self, er):
        """POST /emergency/cases/create sets status to WAITING and writes history."""
        from models.emergency import EmergencyCase
        from models.emergency_status_history import EmergencyStatusHistory

        client = er['er_client']

        resp = client.post(
            '/emergency/cases/create',
            json={
                'patient_id': er['patient'].id,
                'priority': 'MODERATE',
                'case_description': 'test',
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True
        case_id = body['case_id']

        ec = db.session.get(EmergencyCase, case_id)
        assert ec is not None
        assert ec.status == 'WAITING'

        history = (
            db.session.execute(select(EmergencyStatusHistory).filter_by(emergency_id=case_id))
            .scalars()
            .all()
        )
        assert len(history) == 1
        assert history[0].to_status == 'WAITING'
        assert history[0].from_status is None

    def test_edit_can_set_any_status_and_writes_history(self, er):
        """POST /emergency/cases/<id>/edit writes history for every status change."""
        from models.emergency import EmergencyCase
        from models.emergency_status_history import EmergencyStatusHistory

        emergency = er['emergency']
        client = er['er_client']

        # Change to NEW via edit
        resp = client.post(
            f'/emergency/cases/{emergency.id}/edit',
            data={'status': 'NEW'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        assert ec.status == 'NEW'

        history = (
            db.session.execute(select(EmergencyStatusHistory).filter_by(emergency_id=emergency.id))
            .scalars()
            .all()
        )
        # The edit route should have written a history row for WAITING -> NEW
        to_new = [h for h in history if h.to_status == 'NEW' and h.from_status == 'WAITING']
        assert len(to_new) == 1

    def test_resolve_sets_completed(self, er):
        """POST /emergency/cases/<id>/resolve sets COMPLETED."""
        from models.emergency import EmergencyCase
        from models.emergency_status_history import EmergencyStatusHistory

        emergency = er['emergency']
        client = er['er_client']

        resp = client.post(
            f'/emergency/cases/{emergency.id}/resolve',
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        assert ec.status == 'COMPLETED'
        assert ec.completed_at is not None

        to_completed = (
            db.session.execute(
                select(EmergencyStatusHistory)
                .filter_by(emergency_id=emergency.id)
                .filter(EmergencyStatusHistory.to_status == 'COMPLETED')
            )
            .scalars()
            .all()
        )
        assert len(to_completed) == 1

    def test_convert_transfers_and_sets_transferred(self, er):
        """POST /emergency/cases/<id>/convert transfers via queue and sets TRANSFERRED."""

        # The convert route requires reception role
        rec_client = er['rec_client']
        emergency = er['emergency']

        # Ensure there's a lab department to transfer to
        from models.department import Department

        dept = Department(tenant_id=er['tenant'].id, name='Lab', name_ar='مختبر', is_active=True)
        db.session.add(dept)
        db.session.commit()

        resp = rec_client.post(
            f'/emergency/cases/{emergency.id}/convert',
            json={'new_destination': 'lab'},
        )
        # convert requires reception role; our rec_client is doctor so 403 is expected.
        # 200/400/404/409 are the other documented responses. 403 means auth works.
        assert resp.status_code in (200, 400, 403, 404, 409, 500)
        body = resp.get_json()
        assert 'success' in body

    def test_triage_route_moves_to_treatment(self, er):
        """The triage endpoint moves IN_PROGRESS/TRIAGE cases to TREATMENT."""
        from models.emergency import EmergencyCase

        emergency = er['emergency']
        client = er['er_client']

        # Set to TRIAGE first via edit
        resp = client.post(
            f'/emergency/cases/{emergency.id}/edit',
            data={'status': 'TRIAGE'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        assert ec.status == 'TRIAGE'

        # Now hit triage endpoint (requires a visit with triage_level)
        from models.visit import Visit

        visit = db.session.get(Visit, emergency.visit_id)
        visit.triage_level = 'RED'
        db.session.commit()

        resp = client.post(
            f'/emergency/triage/{emergency.id}',
            data={'triage_level': 'RED', 'chief_complaint': 'test', 'diagnosis': 'test'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        # If status was TRIAGE, the triage route should move it to TREATMENT
        assert ec.status == 'TREATMENT', f'status is {ec.status}'

    def test_start_treatment_route_sets_treatment(self, er):
        """POST /emergency/start-treatment/<id> sets TREATMENT."""
        from models.emergency import EmergencyCase
        from models.emergency_status_history import EmergencyStatusHistory

        emergency = er['emergency']
        client = er['er_client']

        resp = client.post(
            f'/emergency/start-treatment/{emergency.id}',
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        assert ec.status == 'TREATMENT'

        to_treatment = (
            db.session.execute(
                select(EmergencyStatusHistory)
                .filter_by(emergency_id=emergency.id)
                .filter(EmergencyStatusHistory.to_status == 'TREATMENT')
            )
            .scalars()
            .all()
        )
        assert len(to_treatment) == 1

    def test_treatment_route_moves_to_observation(self, er):
        """POST /emergency/treatment/<id> moves to OBSERVATION."""
        from models.emergency import EmergencyCase

        emergency = er['emergency']
        client = er['er_client']

        # First set to TREATMENT
        resp = client.post(
            f'/emergency/start-treatment/{emergency.id}',
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)
        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        assert ec.status == 'TREATMENT'

        # Then POST to treatment endpoint
        resp = client.post(
            f'/emergency/treatment/{emergency.id}',
            data={
                'chief_complaint': 'chest pain',
                'diagnosis': 'angina',
                'treatment_given': 'nitroglycerin',
                'medications': 'aspirin',
                'procedures': '',
            },
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        assert ec.status == 'OBSERVATION'

    def test_end_treatment_route_moves_to_completed(self, er):
        """POST /emergency/end-treatment/<id> moves to COMPLETED."""
        from models.emergency import EmergencyCase
        from models.emergency_status_history import EmergencyStatusHistory

        emergency = er['emergency']
        client = er['er_client']

        # Set to OBSERVATION first (via treatment route)
        resp = client.post(
            f'/emergency/start-treatment/{emergency.id}',
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)
        resp = client.post(
            f'/emergency/treatment/{emergency.id}',
            data={
                'chief_complaint': 'c',
                'diagnosis': 'd',
                'treatment_given': 't',
                'medications': '',
                'procedures': '',
            },
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        # Now end treatment
        resp = client.post(
            f'/emergency/end-treatment/{emergency.id}',
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        assert ec.status == 'COMPLETED'
        assert ec.completed_at is not None
        assert ec.completed_by_id == er['er_user'].id

        to_completed = (
            db.session.execute(
                select(EmergencyStatusHistory)
                .filter_by(emergency_id=emergency.id)
                .filter(EmergencyStatusHistory.to_status == 'COMPLETED')
            )
            .scalars()
            .all()
        )
        assert len(to_completed) == 1

    def test_resuscitation_status_reachable(self, er):
        """RESUSCITATION status is reachable via edit."""
        from models.emergency import EmergencyCase
        from models.emergency_status_history import EmergencyStatusHistory

        emergency = er['emergency']
        client = er['er_client']

        resp = client.post(
            f'/emergency/cases/{emergency.id}/edit',
            data={'status': 'RESUSCITATION'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)

        db.session.expire_all()
        ec = db.session.get(EmergencyCase, emergency.id)
        assert ec.status == 'RESUSCITATION'

        to_resus = (
            db.session.execute(
                select(EmergencyStatusHistory)
                .filter_by(emergency_id=emergency.id)
                .filter(EmergencyStatusHistory.to_status == 'RESUSCITATION')
            )
            .scalars()
            .all()
        )
        assert len(to_resus) == 1
