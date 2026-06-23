"""State-machine tests for appointment & lab workflow services.

LEAN: `can_transition` is pure (no DB). Stateful methods are exercised against
the centralized FakeSession so transitions and guards are verified without an
engine.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.shared.enums import AppointmentWorkflowStatus as A, LabOrderStatus as L
from app.modules.workflows.appointment import AppointmentService
from app.modules.workflows.lab import LabWorkflowService


# ---------------------------------------------------------------------------
# Appointment transition matrix
# ---------------------------------------------------------------------------
_APPT_VALID = [
    (A.SCHEDULED, A.CONFIRMED),
    (A.SCHEDULED, A.CANCELLED),
    (A.CONFIRMED, A.CHECKED_IN),
    (A.CONFIRMED, A.CANCELLED),
    (A.CONFIRMED, A.NO_SHOW),
    (A.CHECKED_IN, A.IN_PROGRESS),
    (A.CHECKED_IN, A.CANCELLED),
    (A.IN_PROGRESS, A.DONE),
]
_APPT_INVALID = [
    (A.SCHEDULED, A.CHECKED_IN),
    (A.SCHEDULED, A.DONE),
    (A.CONFIRMED, A.DONE),
    (A.DONE, A.SCHEDULED),
    (A.CANCELLED, A.CONFIRMED),
    (A.NO_SHOW, A.CONFIRMED),
    (A.IN_PROGRESS, A.CANCELLED),
]


@pytest.mark.parametrize("current,target", _APPT_VALID)
def test_appointment_valid_transitions(current, target):
    assert AppointmentService.can_transition(current, target) is True


@pytest.mark.parametrize("current,target", _APPT_INVALID)
def test_appointment_invalid_transitions(current, target):
    assert AppointmentService.can_transition(current, target) is False


def test_appointment_transition_mutates_on_valid(patch_db_session):
    session = patch_db_session()
    appt = SimpleNamespace(status=A.SCHEDULED, updated_at=None)
    AppointmentService.transition(appt, A.CONFIRMED)
    assert appt.status == A.CONFIRMED
    assert appt.updated_at is not None
    assert appt in session.added


def test_appointment_transition_raises_on_invalid(patch_db_session):
    patch_db_session()
    appt = SimpleNamespace(status=A.DONE, updated_at=None)
    with pytest.raises(ValueError):
        AppointmentService.transition(appt, A.SCHEDULED)


@pytest.mark.parametrize("status", [A.CHECKED_IN, A.IN_PROGRESS, A.DONE])
def test_convert_to_visit_allowed_states(patch_db_session, status):
    session = patch_db_session()
    appt = SimpleNamespace(
        status=status, patient_id=1, doctor_id=2, department_id=3, id=10,
    )
    visit = AppointmentService.convert_to_visit(appt, created_by=99)
    assert visit.patient_id == 1
    assert appt.status == A.DONE
    assert visit in session.added


@pytest.mark.parametrize("status", [A.SCHEDULED, A.CONFIRMED, A.CANCELLED, A.NO_SHOW])
def test_convert_to_visit_blocked_states(patch_db_session, status):
    patch_db_session()
    appt = SimpleNamespace(status=status, patient_id=1, doctor_id=2, department_id=3, id=10)
    with pytest.raises(ValueError):
        AppointmentService.convert_to_visit(appt)


# ---------------------------------------------------------------------------
# Lab transition matrix
# ---------------------------------------------------------------------------
_LAB_VALID = [
    (L.ORDERED, L.SAMPLE_COLLECTED),
    (L.ORDERED, L.CANCELLED),
    (L.SAMPLE_COLLECTED, L.IN_PROGRESS),
    (L.SAMPLE_COLLECTED, L.CANCELLED),
    (L.IN_PROGRESS, L.RESULTS_ENTERED),
    (L.RESULTS_ENTERED, L.APPROVED),
    (L.RESULTS_ENTERED, L.IN_PROGRESS),
    (L.APPROVED, L.DELIVERED),
]
_LAB_INVALID = [
    (L.ORDERED, L.IN_PROGRESS),
    (L.ORDERED, L.APPROVED),
    (L.SAMPLE_COLLECTED, L.APPROVED),
    (L.IN_PROGRESS, L.APPROVED),
    (L.APPROVED, L.IN_PROGRESS),
    (L.DELIVERED, L.APPROVED),
    (L.CANCELLED, L.ORDERED),
]


@pytest.mark.parametrize("current,target", _LAB_VALID)
def test_lab_valid_transitions(current, target):
    assert LabWorkflowService.can_transition(current, target) is True


@pytest.mark.parametrize("current,target", _LAB_INVALID)
def test_lab_invalid_transitions(current, target):
    assert LabWorkflowService.can_transition(current, target) is False


def test_lab_transition_sets_approval_metadata(patch_db_session):
    patch_db_session()
    req = SimpleNamespace(status=L.RESULTS_ENTERED, updated_at=None,
                          approved_by=None, approved_at=None)
    LabWorkflowService.transition(req, L.APPROVED, performed_by=42)
    assert req.status == L.APPROVED
    assert req.approved_by == 42
    assert req.approved_at is not None


def test_lab_transition_raises_on_invalid(patch_db_session):
    patch_db_session()
    req = SimpleNamespace(status=L.ORDERED, updated_at=None)
    with pytest.raises(ValueError):
        LabWorkflowService.transition(req, L.APPROVED)


def test_lab_enter_results_sets_values_and_meta(patch_db_session):
    session = patch_db_session()
    result = SimpleNamespace(entered_by=None, entered_at=None)
    LabWorkflowService.enter_results(result, {"wbc": 6.2, "rbc": 4.8}, entered_by=7)
    assert result.wbc == 6.2
    assert result.rbc == 4.8
    assert result.entered_by == 7
    assert result.entered_at is not None
    assert result in session.added
