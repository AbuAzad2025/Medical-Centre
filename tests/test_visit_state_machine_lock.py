"""Tests for Visit state machine lock — direct assignment blocked, VSM succeeds."""

import pytest

from app.extensions import db
from app.shared.enums import VisitState
from models.visit import Visit
from services.visit_state_machine_service import (
    VisitStateMachineService,
    set_vsm_authorized,
)


@pytest.fixture
def visit_with_patient(app, test_tenant):
    from models.patient import Patient
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Test',
        last_name='Patient',
        gender='male',
        phone='0501234567',
    )
    db.session.add(p)
    db.session.flush()

    set_vsm_authorized(True)
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=p.id,
        status='OPEN',
    )
    set_vsm_authorized(False)
    db.session.add(v)
    db.session.commit()
    return v


class TestVisitStateMachineLock:
    def test_direct_status_assignment_raises(self, app, visit_with_patient):
        """Direct assignment to visit.status raises ValueError."""
        with pytest.raises(ValueError, match="Direct Visit.status assignment is blocked"):
            visit_with_patient.status = 'IN_PROGRESS'

    def test_vsm_transition_succeeds(self, app, visit_with_patient):
        """VisitStateMachineService.transition() succeeds normally."""
        VisitStateMachineService.transition(visit_with_patient, VisitState.CHECKED_IN)
        assert visit_with_patient.status == 'CHECKED_IN'

        VisitStateMachineService.transition(visit_with_patient, VisitState.IN_PROGRESS)
        assert visit_with_patient.status == 'IN_PROGRESS'

    def test_vsm_invalid_transition_raises_value_error(self, app, visit_with_patient):
        """Invalid transitions through VSM raise ValueError about invalid transition."""
        with pytest.raises(ValueError, match="Invalid visit transition"):
            VisitStateMachineService.transition(visit_with_patient, VisitState.COMPLETED)

    def test_vsm_initialize_works(self, app, test_tenant):
        """VisitStateMachineService.initialize() sets status on new visit."""
        from models.patient import Patient
        p = Patient(
            tenant_id=test_tenant.id,
            first_name='Init',
            last_name='Patient',
            gender='female',
            phone='0509999999',
        )
        db.session.add(p)
        db.session.flush()

        v = Visit(tenant_id=test_tenant.id, patient_id=p.id)
        VisitStateMachineService.initialize(v, VisitState.CHECKED_IN)
        assert v.status == 'CHECKED_IN'

    def test_ensure_in_progress_via_vsm(self, app, visit_with_patient):
        """ensure_in_progress transitions correctly through intermediate states."""
        VisitStateMachineService.ensure_in_progress(visit_with_patient)
        assert visit_with_patient.status == 'IN_PROGRESS'
