"""
LabWorkflowService — lab order lifecycle
"""
from datetime import datetime, timezone
from typing import Optional
from app.extensions import db
from app.shared.enums import LabOrderStatus


class LabWorkflowService:
    VALID_TRANSITIONS = {
        LabOrderStatus.ORDERED: {LabOrderStatus.SAMPLE_COLLECTED, LabOrderStatus.CANCELLED},
        LabOrderStatus.SAMPLE_COLLECTED: {LabOrderStatus.IN_PROGRESS, LabOrderStatus.CANCELLED},
        LabOrderStatus.IN_PROGRESS: {LabOrderStatus.RESULTS_ENTERED},
        LabOrderStatus.RESULTS_ENTERED: {LabOrderStatus.APPROVED, LabOrderStatus.IN_PROGRESS},
        LabOrderStatus.APPROVED: {LabOrderStatus.DELIVERED},
        LabOrderStatus.DELIVERED: set(),
        LabOrderStatus.CANCELLED: set(),
    }

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        return target in LabWorkflowService.VALID_TRANSITIONS.get(LabOrderStatus(current), set())

    @staticmethod
    def transition(lab_request, new_status: str, performed_by: Optional[int] = None) -> None:
        current = lab_request.status or LabOrderStatus.ORDERED
        if not LabWorkflowService.can_transition(current, new_status):
            raise ValueError(f"Invalid lab transition from {current} to {new_status}")

        lab_request.status = new_status
        lab_request.updated_at = datetime.now(timezone.utc)
        if new_status == LabOrderStatus.APPROVED and performed_by:
            lab_request.approved_by = performed_by
            lab_request.approved_at = datetime.now(timezone.utc)
        db.session.add(lab_request)

    @staticmethod
    def enter_results(lab_result, values: dict, entered_by: int) -> None:
        for k, v in values.items():
            setattr(lab_result, k, v)
        lab_result.entered_by = entered_by
        lab_result.entered_at = datetime.now(timezone.utc)
        db.session.add(lab_result)
