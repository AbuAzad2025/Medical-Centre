"""
VisitWorkflowService — state machine for visit lifecycle
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from app.extensions import db

class VisitStatus(str, Enum):
    REGISTERED = "registered"
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class VisitWorkflowService:
    """Encapsulates all visit state transitions and business rules."""

    VALID_TRANSITIONS = {
        VisitStatus.REGISTERED: {VisitStatus.WAITING, VisitStatus.IN_PROGRESS, VisitStatus.CANCELLED},
        VisitStatus.WAITING: {VisitStatus.IN_PROGRESS, VisitStatus.CANCELLED},
        VisitStatus.IN_PROGRESS: {VisitStatus.COMPLETED, VisitStatus.WAITING},
        VisitStatus.COMPLETED: {VisitStatus.ARCHIVED},
        VisitStatus.ARCHIVED: set(),
        VisitStatus.CANCELLED: set(),
    }

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        return target in VisitWorkflowService.VALID_TRANSITIONS.get(VisitStatus(current), set())

    @staticmethod
    def transition(visit, new_status: str, performed_by: Optional[int] = None, reason: Optional[str] = None) -> None:
        from models.visit import Visit
        if not isinstance(visit, Visit):
            raise TypeError("Expected Visit model instance")

        current = visit.status or VisitStatus.REGISTERED
        if not VisitWorkflowService.can_transition(current, new_status):
            raise ValueError(f"Invalid transition from {current} to {new_status}")

        # Archive rule: must be fully paid or force-approved
        if new_status == VisitStatus.ARCHIVED:
            if not visit.can_be_archived():
                raise PermissionError("Visit cannot be archived: payments pending or not approved.")

        visit.status = new_status
        visit.updated_at = datetime.now(timezone.utc)
        db.session.add(visit)

    @staticmethod
    def get_allowed_actions(visit) -> list[str]:
        current = visit.status or VisitStatus.REGISTERED
        return list(VisitWorkflowService.VALID_TRANSITIONS.get(VisitStatus(current), []))

    @staticmethod
    def assign_to_doctor(visit, doctor_id: int) -> None:
        from models.visit import Visit
        if visit.status not in (VisitStatus.REGISTERED, VisitStatus.WAITING):
            raise ValueError("Cannot assign doctor unless visit is registered or waiting")
        visit.doctor_id = doctor_id
        visit.status = VisitStatus.IN_PROGRESS
        visit.updated_at = datetime.now(timezone.utc)
        db.session.add(visit)
