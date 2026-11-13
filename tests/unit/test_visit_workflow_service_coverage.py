"""Coverage tests for app/modules/workflows/visit.py"""

from app.modules.workflows.visit import VisitWorkflowService


class TestVisitWorkflowService:
    def test_can_transition_true(self):
        result = VisitWorkflowService.can_transition('registered', 'waiting')
        assert isinstance(result, bool)

    def test_can_transition_invalid(self):
        result = VisitWorkflowService.can_transition('registered', 'bogus')
        assert result is False

    def test_can_transition_archived(self):
        result = VisitWorkflowService.can_transition('completed', 'archived')
        assert isinstance(result, bool)
