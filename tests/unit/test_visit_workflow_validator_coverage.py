"""Coverage tests for services/visit_workflow_validator.py"""

from services.visit_workflow_validator import VisitStage, VisitWorkflowValidator, resolve_visit_status_badge_class


class TestVisitWorkflowValidator:
    def test_stage_order(self):
        order = VisitStage.stage_order()
        assert isinstance(order, dict)
        assert len(order) > 0

    def test_stage_label_ar(self):
        label = VisitStage.stage_label_ar(VisitStage.REGISTERED)
        assert isinstance(label, str)

    def test_stage_icon(self):
        icon = VisitStage.stage_icon(VisitStage.REGISTERED)
        assert isinstance(icon, str)

    def test_can_transition(self):
        result = VisitWorkflowValidator.can_transition(VisitStage.REGISTERED, VisitStage.TRIAGED)
        assert isinstance(result, bool)

    def test_get_available_transitions(self):
        result = VisitWorkflowValidator.get_available_transitions(VisitStage.REGISTERED)
        assert isinstance(result, list)

    def test_get_journey_stage_number(self):
        result = VisitWorkflowValidator.get_journey_stage_number(VisitStage.REGISTERED)
        assert isinstance(result, int)

    def test_resolve_visit_status_badge_class(self):
        result = resolve_visit_status_badge_class('COMPLETED')
        assert isinstance(result, str)
