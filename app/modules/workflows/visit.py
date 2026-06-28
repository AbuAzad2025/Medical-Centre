"""
VisitWorkflowService — facade over VisitStateMachineService + GatekeeperService.

Maps legacy workflow status strings to canonical VisitState values and routes
all mutations through validated services (no direct visit.status writes).
"""
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.shared.enums import VisitState, VisitArchiveStatus, VisitWorkflowStatus as VisitStatus
from services.visit_state_machine_service import VisitStateMachineService


_WORKFLOW_TO_VISIT: dict[str, VisitState] = {
    VisitStatus.REGISTERED: VisitState.OPEN,
    VisitStatus.WAITING: VisitState.CHECKED_IN,
    VisitStatus.IN_PROGRESS: VisitState.IN_PROGRESS,
    VisitStatus.COMPLETED: VisitState.COMPLETED,
    VisitStatus.CANCELLED: VisitState.CANCELLED,
}

_VISIT_TO_WORKFLOW: dict[VisitState, str] = {
    VisitState.OPEN: VisitStatus.REGISTERED,
    VisitState.CHECKED_IN: VisitStatus.WAITING,
    VisitState.IN_PROGRESS: VisitStatus.IN_PROGRESS,
    VisitState.COMPLETED: VisitStatus.COMPLETED,
    VisitState.CANCELLED: VisitStatus.CANCELLED,
}


class VisitWorkflowService:
    """Encapsulates visit state transitions via the canonical state machine."""

    @staticmethod
    def _resolve_current(visit) -> VisitState:
        clinical = VisitStateMachineService.get_status(visit)
        if clinical is not None:
            return clinical
        raw = visit.status or VisitStatus.REGISTERED
        try:
            wf = VisitStatus(raw)
        except ValueError:
            wf = VisitStatus.REGISTERED
        return _WORKFLOW_TO_VISIT.get(wf, VisitState.OPEN)

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        try:
            wf_target = VisitStatus(target)
        except ValueError:
            return False
        if wf_target == VisitStatus.ARCHIVED:
            return current in (VisitStatus.COMPLETED, VisitState.COMPLETED)
        visit_state = _WORKFLOW_TO_VISIT.get(wf_target)
        if visit_state is None:
            return False
        class _Proxy:
            status = current
        return VisitStateMachineService.can_transition(_Proxy(), visit_state)

    @staticmethod
    def transition(visit, new_status: str, performed_by: Optional[int] = None, reason: Optional[str] = None) -> None:
        from models.visit import Visit
        if not isinstance(visit, Visit):
            raise TypeError("Expected Visit model instance")

        try:
            wf_target = VisitStatus(new_status)
        except ValueError as exc:
            raise ValueError(f"Unknown workflow status: {new_status}") from exc

        if wf_target == VisitStatus.ARCHIVED:
            can, msg = visit.can_be_archived()
            if not can:
                raise PermissionError(msg or "Visit cannot be archived")
            ok, msg = VisitStateMachineService.transition_or_archive(
                visit, VisitArchiveStatus.ARCHIVED, actor=performed_by, user_id=performed_by,
            )
            if not ok:
                raise PermissionError(msg or "Archival failed")
            visit.updated_at = datetime.now(timezone.utc)
            db.session.add(visit)
            return

        target_clinical = _WORKFLOW_TO_VISIT.get(wf_target)
        if target_clinical is None:
            raise ValueError(f"Unsupported workflow transition to {new_status}")

        VisitStateMachineService._coerce_legacy_status(visit)
        if target_clinical == VisitState.IN_PROGRESS:
            VisitStateMachineService.ensure_in_progress(visit, actor=performed_by)
        else:
            VisitStateMachineService.transition(visit, target_clinical, actor=performed_by)
        visit.updated_at = datetime.now(timezone.utc)
        db.session.add(visit)

    @staticmethod
    def get_allowed_actions(visit) -> list[str]:
        current = VisitWorkflowService._resolve_current(visit)
        class _Proxy:
            status = current.value
        allowed = VisitStateMachineService.get_allowed_transitions(_Proxy())
        actions = [_VISIT_TO_WORKFLOW[s] for s in allowed if s in _VISIT_TO_WORKFLOW]
        if current == VisitState.COMPLETED:
            actions.append(VisitStatus.ARCHIVED)
        return actions

    @staticmethod
    def assign_to_doctor(visit, doctor_id: int) -> None:
        from models.visit import Visit
        current = VisitWorkflowService._resolve_current(visit)
        if current not in (VisitState.OPEN, VisitState.CHECKED_IN):
            raise ValueError("Cannot assign doctor unless visit is registered or waiting")
        visit.doctor_id = doctor_id
        VisitStateMachineService.ensure_in_progress(visit)
        visit.updated_at = datetime.now(timezone.utc)
        db.session.add(visit)
