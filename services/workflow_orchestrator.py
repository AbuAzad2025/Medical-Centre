"""
WorkflowOrchestrator — unified workflow facade over VisitStateMachineService.

Clinical visit.status transitions are validated by VisitStateMachineService.
Administrative archival is owned exclusively by GatekeeperService (P1-002).
"""
from datetime import datetime, timezone
from flask import g
from app.extensions import db
from app.shared.enums import VisitState, QueueState
from services.visit_state_machine_service import VisitStateMachineService


class WorkflowOrchestrator:
    @staticmethod
    def valid_transitions(current_state: str) -> list[str]:
        class _VisitProxy:
            status = current_state

        allowed = {s.value for s in VisitStateMachineService.get_allowed_transitions(_VisitProxy())}
        if current_state == VisitState.COMPLETED:
            allowed.add(VisitState.ARCHIVED)
        return sorted(allowed)

    @staticmethod
    def can_transition(current_state: str, next_state: str) -> bool:
        if next_state == VisitState.ARCHIVED:
            return current_state == VisitState.COMPLETED
        class _VisitProxy:
            status = current_state
        try:
            target = VisitState(next_state)
        except ValueError:
            return False
        return VisitStateMachineService.can_transition(_VisitProxy(), target)

    @staticmethod
    def transition(visit, next_state: str, user_id: int | None = None, note: str = "") -> bool:
        try:
            target = VisitState(next_state)
        except ValueError:
            return False
        old_state = visit.status
        if target == VisitState.ARCHIVED:
            ok, _ = VisitStateMachineService.transition_or_archive(
                visit, target, actor=user_id, user_id=user_id,
            )
            if ok:
                WorkflowOrchestrator._emit_event(visit, old_state, next_state, user_id, note)
            return ok
        if not VisitStateMachineService.try_transition(visit, target, actor=user_id):
            return False
        WorkflowOrchestrator._emit_event(visit, old_state, next_state, user_id, note)
        return True

    @staticmethod
    def create_case(visit, initial_state: str = VisitState.OPEN, user_id: int | None = None):
        try:
            state = VisitState(initial_state)
        except ValueError:
            state = VisitState.OPEN
        VisitStateMachineService.initialize(visit, state)
        WorkflowOrchestrator._emit_event(visit, None, state.value, user_id, "Case created")

    @staticmethod
    def next_actions(visit) -> list[str]:
        return WorkflowOrchestrator.valid_transitions(visit.status)

    @staticmethod
    def current_owner(visit) -> str | None:
        ownership_map = {
            VisitState.OPEN: "reception",
            VisitState.CHECKED_IN: "reception",
            VisitState.IN_PROGRESS: "doctor",
            VisitState.COMPLETED: None,
            VisitState.ARCHIVED: None,
            VisitState.CANCELLED: None,
        }
        return ownership_map.get(visit.status)

    @staticmethod
    def required_fields(visit) -> list[str]:
        field_map = {
            VisitState.OPEN: ["patient_id"],
            VisitState.CHECKED_IN: ["patient_id", "doctor_id"],
            VisitState.IN_PROGRESS: ["patient_id", "doctor_id", "diagnosis"],
            VisitState.COMPLETED: ["patient_id", "doctor_id"],
        }
        return field_map.get(visit.status, [])

    @staticmethod
    def _emit_event(visit, old_state, new_state, user_id, note=""):
        try:
            from models.workflow import VisitWorkflowEvent
            event = VisitWorkflowEvent(
                visit_id=visit.id,
                tenant_id=getattr(g, 'tenant_id', None) or getattr(visit, 'tenant_id', None),
                from_status=old_state,
                to_status=new_state,
                performed_by=user_id or getattr(g, 'current_user', None) and getattr(g.current_user, 'id', None),
                notes=note,
            )
            db.session.add(event)
        except Exception:
            pass


class QueueService:
    @staticmethod
    def add_to_queue(visit, station: str, tenant_id: int):
        from models.queue_management import QueueManagement
        q = QueueManagement(
            tenant_id=tenant_id,
            visit_id=visit.id,
            patient_id=visit.patient_id,
            station=station,
            status=QueueState.WAITING,
        )
        db.session.add(q)
        db.session.commit()

    @staticmethod
    def call_next(station: str, tenant_id: int):
        from models.queue_management import QueueManagement
        entry = QueueManagement.query.filter_by(
            tenant_id=tenant_id, station=station, status=QueueState.WAITING
        ).order_by(QueueManagement.id.asc()).first()
        if entry:
            entry.status = QueueState.CALLED
            db.session.commit()
        return entry

    @staticmethod
    def complete(visit, station: str, tenant_id: int):
        from models.queue_management import QueueManagement
        entry = QueueManagement.query.filter_by(
            tenant_id=tenant_id, visit_id=visit.id, station=station
        ).order_by(QueueManagement.id.desc()).first()
        if entry:
            entry.status = QueueState.COMPLETED
            db.session.commit()
