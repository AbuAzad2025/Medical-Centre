"""Batch 2: WorkflowOrchestrator + VisitWorkflowService alignment with VSM/Gatekeeper."""

import uuid
from unittest.mock import patch

import pytest

from app.extensions import db
from app.shared.enums import VisitState, VisitArchiveStatus, VisitWorkflowStatus
from app.modules.workflows.visit import VisitWorkflowService
from models.patient import Patient
from models.visit import Visit
from services.workflow_orchestrator import WorkflowOrchestrator
from services.visit_state_machine_service import VisitStateMachineService


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *a, **k: None,
    )


@pytest.fixture
def wf_visit(rollback_db):
    p = Patient(first_name='و', last_name='س', phone='050' + format(uuid.uuid4().int % 10**7, '07d'))
    rollback_db.session.add(p)
    rollback_db.session.commit()
    v = Visit(patient_id=p.id, status=VisitState.OPEN)
    rollback_db.session.add(v)
    rollback_db.session.commit()
    return v


class TestWorkflowOrchestrator:
    def test_clinical_transition_via_vsm(self, wf_visit):
        assert WorkflowOrchestrator.transition(wf_visit, VisitState.CHECKED_IN) is True
        assert wf_visit.status == VisitState.CHECKED_IN

    def test_invalid_transition_rejected(self, wf_visit):
        assert WorkflowOrchestrator.transition(wf_visit, VisitState.COMPLETED) is False

    def test_archive_delegates_to_gatekeeper(self, wf_visit):
        wf_visit.status = VisitState.COMPLETED
        with patch('services.gatekeeper_service.GatekeeperService.archive_visit', return_value=(True, 'ok')) as arch:
            ok = WorkflowOrchestrator.transition(wf_visit, VisitArchiveStatus.ARCHIVED, user_id=1)
        assert ok is True
        arch.assert_called_once_with(wf_visit.id, 1)

    def test_create_case_initializes_open(self, wf_visit):
        wf_visit.status = None
        WorkflowOrchestrator.create_case(wf_visit, VisitState.OPEN)
        assert wf_visit.status == VisitState.OPEN

    def test_valid_transitions_from_open(self):
        assert VisitState.CHECKED_IN in WorkflowOrchestrator.valid_transitions(VisitState.OPEN)


class TestVisitWorkflowService:
    def test_transition_to_in_progress(self, wf_visit):
        VisitWorkflowService.transition(wf_visit, VisitWorkflowStatus.IN_PROGRESS)
        assert wf_visit.status == VisitState.IN_PROGRESS

    def test_archive_via_gatekeeper(self, wf_visit):
        wf_visit.status = VisitState.COMPLETED
        wf_visit.payment_status = 'PAID'
        with patch('services.gatekeeper_service.GatekeeperService.archive_visit', return_value=(True, 'ok')) as arch:
            VisitWorkflowService.transition(wf_visit, VisitWorkflowStatus.ARCHIVED, performed_by=1)
        arch.assert_called_once_with(wf_visit.id, 1)

    def test_assign_to_doctor(self, wf_visit):
        VisitWorkflowService.assign_to_doctor(wf_visit, doctor_id=99)
        assert wf_visit.doctor_id == 99
        assert wf_visit.status == VisitState.IN_PROGRESS

    def test_invalid_transition_raises(self, wf_visit):
        with pytest.raises(ValueError):
            VisitWorkflowService.transition(wf_visit, VisitWorkflowStatus.COMPLETED)

    def test_vsm_try_transition_helper(self, wf_visit):
        assert VisitStateMachineService.try_transition(wf_visit, VisitState.CHECKED_IN) is True
