"""Tests for P1-001: VisitStateMachineService lifecycle contract."""

import pytest

from app_factory import db as _db
from app.shared.enums import VisitState
from models.patient import Patient
from models.user import User
from models.visit import Visit
from services.visit_state_machine_service import VisitStateMachineService


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *a, **k: None,
    )


@pytest.fixture(scope='function')
def sm_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='StateMachine',
        last_name='Test',
        phone='0500000002',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def sm_doctor(app, test_tenant):
    u = User.query.filter_by(username='sm_doctor').first()
    if not u:
        u = User(
            username='sm_doctor',
            email='sm_doc@example.com',
            full_name='Dr. State Machine',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def sm_visit(app, test_tenant, sm_patient, sm_doctor):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=sm_patient.id,
        doctor_id=sm_doctor.id,
        status=VisitState.IN_PROGRESS,
    )
    _db.session.add(v)
    _db.session.commit()
    return v


class TestVisitStateMachineService:
    def test_get_status_reads_legacy_field(self, sm_visit):
        assert VisitStateMachineService.get_status(sm_visit) == VisitState.IN_PROGRESS

    def test_can_transition_allows_valid_move(self, sm_visit):
        assert VisitStateMachineService.can_transition(sm_visit, VisitState.COMPLETED)

    def test_can_transition_rejects_invalid_move(self, sm_visit):
        assert not VisitStateMachineService.can_transition(sm_visit, VisitState.OPEN)

    def test_transition_updates_status(self, sm_visit):
        VisitStateMachineService.transition(sm_visit, VisitState.COMPLETED)
        _db.session.commit()
        assert sm_visit.status == VisitState.COMPLETED

    def test_transition_raises_for_invalid_move(self, sm_visit):
        with pytest.raises(ValueError):
            VisitStateMachineService.transition(sm_visit, VisitState.ARCHIVED)

    def test_completed_visit_cannot_transition_to_archived(self, sm_visit):
        # P1-002: ARCHIVED is not part of the clinical status lifecycle.
        VisitStateMachineService.transition(sm_visit, VisitState.COMPLETED)
        _db.session.commit()
        with pytest.raises(ValueError):
            VisitStateMachineService.transition(sm_visit, VisitState.ARCHIVED)

    def test_allowed_transitions_returns_reachable_states(self, sm_visit):
        allowed = VisitStateMachineService.get_allowed_transitions(sm_visit)
        assert VisitState.COMPLETED in allowed
        assert VisitState.ARCHIVED not in allowed
        assert VisitState.OPEN not in allowed

    def test_get_status_returns_none_for_unrecognised(self, sm_visit):
        sm_visit.status = 'UNKNOWN'
        assert VisitStateMachineService.get_status(sm_visit) is None

    @pytest.mark.parametrize('start,target,ok', [
        (VisitState.OPEN, VisitState.CHECKED_IN, True),
        (VisitState.OPEN, VisitState.CANCELLED, True),
        (VisitState.CHECKED_IN, VisitState.IN_PROGRESS, True),
        (VisitState.IN_PROGRESS, VisitState.COMPLETED, True),
        (VisitState.COMPLETED, VisitState.OPEN, False),
        (VisitState.CANCELLED, VisitState.OPEN, False),
    ])
    def test_transition_matrix(self, sm_visit, start, target, ok):
        sm_visit.status = start
        assert VisitStateMachineService.can_transition(sm_visit, target) is ok


class TestDoctorEndTreatmentRoute:
    def test_end_treatment_uses_state_machine(self, app, client, sm_visit, sm_doctor, test_tenant):
        from app.core.rate_limiter import _shared_store
        _shared_store.clear()
        client.post('/auth/login', data={
            'username': 'sm_doctor',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        resp = client.post(f'/doctor/end-treatment/{sm_visit.id}')
        assert resp.status_code in (200, 302)
        _db.session.refresh(sm_visit)
        assert sm_visit.status == VisitState.COMPLETED
