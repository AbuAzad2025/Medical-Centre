"""
RadiologyWorkflowService — radiology order lifecycle
"""

from datetime import UTC, datetime

from app.extensions import db
from app.shared.enums import RadiologyOrderStatus


class RadiologyWorkflowService:
    VALID_TRANSITIONS = {
        RadiologyOrderStatus.ORDERED: {
            RadiologyOrderStatus.SCHEDULED,
            RadiologyOrderStatus.CANCELLED,
        },
        RadiologyOrderStatus.SCHEDULED: {
            RadiologyOrderStatus.IN_PROGRESS,
            RadiologyOrderStatus.CANCELLED,
        },
        RadiologyOrderStatus.IN_PROGRESS: {RadiologyOrderStatus.IMAGES_CAPTURED},
        RadiologyOrderStatus.IMAGES_CAPTURED: {RadiologyOrderStatus.REPORTED},
        RadiologyOrderStatus.REPORTED: {
            RadiologyOrderStatus.APPROVED,
            RadiologyOrderStatus.REPORTED,
        },
        RadiologyOrderStatus.APPROVED: {RadiologyOrderStatus.DELIVERED},
        RadiologyOrderStatus.DELIVERED: set(),
        RadiologyOrderStatus.CANCELLED: set(),
    }

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        return target in RadiologyWorkflowService.VALID_TRANSITIONS.get(
            RadiologyOrderStatus(current), set()
        )

    @staticmethod
    def transition(rad_request, new_status: str, performed_by: int | None = None) -> None:
        current = rad_request.status or RadiologyOrderStatus.ORDERED
        if not RadiologyWorkflowService.can_transition(current, new_status):
            raise ValueError(f'Invalid radiology transition from {current} to {new_status}')

        rad_request.status = new_status
        rad_request.updated_at = datetime.now(UTC)
        if new_status == RadiologyOrderStatus.APPROVED and performed_by:
            rad_request.approved_by = performed_by
            rad_request.approved_at = datetime.now(UTC)
        db.session.add(rad_request)
