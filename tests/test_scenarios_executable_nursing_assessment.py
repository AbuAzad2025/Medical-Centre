"""Execute the nursing assessment scales over HTTP.

Phase 8 continued: NURSING_ASSESSMENT_SCALES (7 scenarios, one per ward type).

Driven through:

  POST /nursing-assessment/new/<patient_id>  -- with assessment_type and subscales

What execution established:

  * The five assessment instruments are real and computed on the model:
    - Braden (6 subscales 1-4/1-3): severe ≤ 9, high 10-12, moderate 13-14, low ≥ 15
    - Glasgow (eye 1-4, verbal 1-5, motor 1-6): severe < 4, high 4-8, moderate 9-12, low ≥ 13
    - Morse Fall Risk (6 items): high ≥ 51, low < 51
    - Pain Scale (0-10): high > 6, moderate 4-6, low ≤ 3
    - Norton (5 items 1-4): high ≤ 14, moderate 15-18, low ≥ 19

  * Each assessment writes a NursingAssessment row with the correct
    assessment_type, all subscales, total_score, and risk_level.

  * The ward_type of the patient's ward (GENERAL, ICU, NICU, PICU,
    MATERNITY, SURGERY, ISOLATION) is the axis; each type is exercised
    by admitting a patient to a ward of that type.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.extensions import db
from models.bed_management import Ward
from models.nursing_assessment import NursingAssessment
from models.patient import Patient
from models.visit import Visit
from tests.scenario_execution_registry import covers
from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client


@pytest.fixture
def ward_ctx(app, test_tenant):
    """Create all 7 ward types, a nurse, a patient in each ward, and visits."""
    activate_tenant_modules(app, test_tenant, ['nurse', 'doctor', 'reception'])
    nurse_user = ensure_test_user(db, test_tenant, username='e2e_nurse_assess', role='nurse')
    nurse_client = app.test_client()
    with app.test_request_context():
        from flask import g

        g.tenant_id = test_tenant.id
        login_test_client(nurse_client, nurse_user, test_tenant)

    wards = {}
    for wt in ['GENERAL', 'ICU', 'NICU', 'PICU', 'MATERNITY', 'SURGERY', 'ISOLATION']:
        ward = Ward(
            tenant_id=test_tenant.id,
            name=f'{wt} Ward',
            name_ar=f'جناح {wt}',
            code=wt[:3].upper(),
            ward_type=wt,
            capacity=10,
            is_active=True,
        )
        db.session.add(ward)
        db.session.flush()
        wards[wt] = ward

    patients = {}
    visits = {}
    for wt, ward in wards.items():
        patient = Patient(
            tenant_id=test_tenant.id,
            first_name=f'{wt}',
            last_name='Patient',
            national_id=f'E2E-{wt}-1',
        )
        db.session.add(patient)
        db.session.flush()
        patients[wt] = patient

        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=nurse_user.id,
            visit_number=f'E2E-{wt}-VISIT-1',
            status='IN_PROGRESS',
            ward_id=ward.id,
        )
        db.session.add(visit)
        db.session.flush()
        visits[wt] = visit

    db.session.commit()

    return {
        'app': app,
        'client': nurse_client,
        'tenant': test_tenant,
        'nurse_user': nurse_user,
        'wards': wards,
        'patients': patients,
        'visits': visits,
    }


def _post_assessment(client, patient_id, visit_id, assessment_type, form_data):
    """Helper to POST an assessment and return the created object.

    The route reads assessment_type from query param 'type', not form data.
    """
    resp = client.post(
        f'/nursing-assessment/new/{patient_id}?type={assessment_type}',
        data={**form_data, 'visit_id': str(visit_id)},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302), f'{assessment_type} POST answered {resp.status_code}'
    db.session.expire_all()
    assessment = (
        db.session.execute(
            select(NursingAssessment)
            .filter_by(patient_id=patient_id, assessment_type=assessment_type)
            .order_by(NursingAssessment.created_at.desc())
        )
        .scalars()
        .first()
    )
    assert assessment is not None, f'{assessment_type} assessment not created'
    return assessment


@covers('NURSING_ASSESSMENT_SCALES')
class TestNursingAssessmentScales:
    """Each ward type exercises all five assessment instruments."""

    def test_braden_scale_computes_correct_risk(self, ward_ctx):
        """Braden: severe ≤ 9, high 10-12, moderate 13-14, low ≥ 15."""
        for wt in ['GENERAL', 'ICU', 'NICU', 'PICU', 'MATERNITY', 'SURGERY', 'ISOLATION']:
            visit = ward_ctx['visits'][wt]
            patient = ward_ctx['patients'][wt]
            client = ward_ctx['client']

            # Score = 1+1+1+1+1+1 = 6 -> severe
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'braden',
                {
                    'sensory': 1,
                    'moisture': 1,
                    'activity': 1,
                    'mobility': 1,
                    'nutrition': 1,
                    'friction': 1,
                },
            )
            assert a.assessment_type == 'braden'
            assert a.total_score == 6
            assert a.risk_level == 'severe'
            assert all(
                getattr(a, f'braden_{sub}') == 1
                for sub in [
                    'sensory_perception',
                    'moisture',
                    'activity',
                    'mobility',
                    'nutrition',
                    'friction_shear',
                ]
            )

            # Score = 2+2+2+2+2+2 = 12 -> high
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'braden',
                {
                    'sensory': 2,
                    'moisture': 2,
                    'activity': 2,
                    'mobility': 2,
                    'nutrition': 2,
                    'friction': 2,
                },
            )
            assert a.total_score == 12
            assert a.risk_level == 'high'

            # Score = 3+3+3+3+3+3 = 18 -> low
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'braden',
                {
                    'sensory': 3,
                    'moisture': 3,
                    'activity': 3,
                    'mobility': 3,
                    'nutrition': 3,
                    'friction': 3,
                },
            )
            assert a.total_score == 18
            assert a.risk_level == 'low'

    def test_glasgow_scale_computes_correct_risk(self, ward_ctx):
        """Glasgow: severe < 4, high 4-8, moderate 9-12, low ≥ 13."""
        for wt in ['GENERAL', 'ICU', 'NICU', 'PICU', 'MATERNITY', 'SURGERY', 'ISOLATION']:
            visit = ward_ctx['visits'][wt]
            patient = ward_ctx['patients'][wt]
            client = ward_ctx['client']

            # 1+1+1 = 3 -> severe
            a = _post_assessment(
                client, patient.id, visit.id, 'glasgow', {'eye': 1, 'verbal': 1, 'motor': 1}
            )
            assert a.assessment_type == 'glasgow'
            assert a.total_score == 3
            assert a.risk_level == 'severe'
            assert a.glasgow_eye == 1 and a.glasgow_verbal == 1 and a.glasgow_motor == 1

            # 2+2+2 = 6 -> high
            a = _post_assessment(
                client, patient.id, visit.id, 'glasgow', {'eye': 2, 'verbal': 2, 'motor': 2}
            )
            assert a.total_score == 6
            assert a.risk_level == 'high'

            # 4+5+6 = 15 -> low
            a = _post_assessment(
                client, patient.id, visit.id, 'glasgow', {'eye': 4, 'verbal': 5, 'motor': 6}
            )
            assert a.total_score == 15
            assert a.risk_level == 'low'

    def test_morse_fall_risk_computes_correct_risk(self, ward_ctx):
        """Morse Fall Risk: high ≥ 51, low < 51."""
        for wt in ['GENERAL', 'ICU', 'NICU', 'PICU', 'MATERNITY', 'SURGERY', 'ISOLATION']:
            visit = ward_ctx['visits'][wt]
            patient = ward_ctx['patients'][wt]
            client = ward_ctx['client']

            # Max Morse = 25+15+30+20+20+15 = 125 -> high
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'fall_risk',
                {'history': 25, 'diagnosis': 15, 'aid': 30, 'iv': 20, 'gait': 20, 'mental': 15},
            )
            assert a.assessment_type == 'fall_risk'
            assert a.total_score == 125
            assert a.risk_level == 'high'

            # Low risk
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'fall_risk',
                {'history': 0, 'diagnosis': 0, 'aid': 0, 'iv': 0, 'gait': 0, 'mental': 0},
            )
            assert a.total_score == 0
            assert a.risk_level == 'low'

    def test_pain_scale_computes_correct_risk(self, ward_ctx):
        """Pain Scale: high > 6, moderate 4-6, low ≤ 3."""
        for wt in ['GENERAL', 'ICU', 'NICU', 'PICU', 'MATERNITY', 'SURGERY', 'ISOLATION']:
            visit = ward_ctx['visits'][wt]
            patient = ward_ctx['patients'][wt]
            client = ward_ctx['client']

            # Pain = 2 -> low
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'pain_scale',
                {'pain_score': 2, 'pain_location': 'chest', 'pain_character': 'sharp'},
            )
            assert a.assessment_type == 'pain_scale'
            assert a.total_score == 2
            assert a.risk_level == 'low'
            assert a.pain_location == 'chest'
            assert a.pain_character == 'sharp'

            # Pain = 5 -> moderate
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'pain_scale',
                {'pain_score': 5, 'pain_location': 'abdomen', 'pain_character': 'dull'},
            )
            assert a.total_score == 5
            assert a.risk_level == 'moderate'

            # Pain = 8 -> high
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'pain_scale',
                {'pain_score': 8, 'pain_location': 'head', 'pain_character': 'throbbing'},
            )
            assert a.total_score == 8
            assert a.risk_level == 'high'

    def test_norton_scale_computes_correct_risk(self, ward_ctx):
        """Norton: high ≤ 14, moderate 15-18, low ≥ 19."""
        for wt in ['GENERAL', 'ICU', 'NICU', 'PICU', 'MATERNITY', 'SURGERY', 'ISOLATION']:
            visit = ward_ctx['visits'][wt]
            patient = ward_ctx['patients'][wt]
            client = ward_ctx['client']

            # All 1s = 5 -> high
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'norton',
                {'physical': 1, 'mental': 1, 'activity': 1, 'mobility': 1, 'incontinence': 1},
            )
            assert a.assessment_type == 'norton'
            assert a.total_score == 5
            assert a.risk_level == 'high'

            # All 3s = 15 -> moderate
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'norton',
                {'physical': 3, 'mental': 3, 'activity': 3, 'mobility': 3, 'incontinence': 3},
            )
            assert a.total_score == 15
            assert a.risk_level == 'moderate'

            # All 4s = 20 -> low
            a = _post_assessment(
                client,
                patient.id,
                visit.id,
                'norton',
                {'physical': 4, 'mental': 4, 'activity': 4, 'mobility': 4, 'incontinence': 4},
            )
            assert a.total_score == 20
            assert a.risk_level == 'low'
