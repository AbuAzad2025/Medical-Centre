"""
RadiologyWorkflowService — radiology order lifecycle
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from app.extensions import db

class RadiologyOrderStatus(str, Enum):
    ORDERED = "ordered"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    IMAGES_CAPTURED = "images_captured"
    REPORTED = "reported"
    APPROVED = "approved"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class RadiologyWorkflowService:
    VALID_TRANSITIONS = {
        RadiologyOrderStatus.ORDERED: {RadiologyOrderStatus.SCHEDULED, RadiologyOrderStatus.CANCELLED},
        RadiologyOrderStatus.SCHEDULED: {RadiologyOrderStatus.IN_PROGRESS, RadiologyOrderStatus.CANCELLED},
        RadiologyOrderStatus.IN_PROGRESS: {RadiologyOrderStatus.IMAGES_CAPTURED},
        RadiologyOrderStatus.IMAGES_CAPTURED: {RadiologyOrderStatus.REPORTED},
        RadiologyOrderStatus.REPORTED: {RadiologyOrderStatus.APPROVED, RadiologyOrderStatus.REPORTED},
        RadiologyOrderStatus.APPROVED: {RadiologyOrderStatus.DELIVERED},
        RadiologyOrderStatus.DELIVERED: set(),
        RadiologyOrderStatus.CANCELLED: set(),
    }

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        return target in RadiologyWorkflowService.VALID_TRANSITIONS.get(RadiologyOrderStatus(current), set())

    @staticmethod
    def transition(rad_request, new_status: str, performed_by: Optional[int] = None) -> None:
        current = rad_request.status or RadiologyOrderStatus.ORDERED
        if not RadiologyWorkflowService.can_transition(current, new_status):
            raise ValueError(f"Invalid radiology transition from {current} to {new_status}")

        rad_request.status = new_status
        rad_request.updated_at = datetime.now(timezone.utc)
        if new_status == RadiologyOrderStatus.APPROVED and performed_by:
            rad_request.approved_by = performed_by
            rad_request.approved_at = datetime.now(timezone.utc)
        db.session.add(rad_request)
