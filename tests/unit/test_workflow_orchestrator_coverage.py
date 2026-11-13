"""Coverage tests for services/workflow_orchestrator.py"""

from app.shared.enums import VisitState
from services.workflow_orchestrator import WorkflowOrchestrator, QueueService


class TestWorkflowOrchestrator:
    def test_valid_transitions(self):
        result = WorkflowOrchestrator.valid_transitions('open')
        assert isinstance(result, list)

    def test_can_transition(self):
        result = WorkflowOrchestrator.can_transition('open', 'in_progress')
        assert isinstance(result, bool)

    def test_can_transition_invalid(self):
        result = WorkflowOrchestrator.can_transition('open', 'bogus')
        assert result is False

    def test_can_transition_archived(self):
        result = WorkflowOrchestrator.can_transition('completed', 'archived')
        assert isinstance(result, bool)
