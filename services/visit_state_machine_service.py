"""Visit lifecycle state machine.

P1-001 introduces a canonical state machine for Visit.status while keeping
legacy direct reads/writes operational during the dual-read migration window.

Rules:
- The service is the authoritative source for transition validity.
- Direct assignment to Visit.status is BLOCKED unless performed through this
  service (which sets a thread-local authorization flag).
- Routes being migrated should call transition() instead of mutating status.
"""
from __future__ import annotations

import threading
from typing import Optional

from app.shared.enums import VisitState, VisitArchiveStatus

_vsm_authorized = threading.local()


def is_vsm_authorized() -> bool:
    """Check if the current thread is in a VSM-authorized transition."""
    return getattr(_vsm_authorized, 'active', False)


def set_vsm_authorized(value: bool) -> None:
    """Explicitly set VSM authorization flag (for Visit model construction)."""
    _vsm_authorized.active = value


class VisitStateMachineService:
    """Canonical visit lifecycle transitions."""

    TRANSITIONS: dict[VisitState, set[VisitState]] = {
        # Clinical lifecycle ends at COMPLETED. Archival is an administrative
        # action tracked by Visit.archive_status (GatekeeperService), not by
        # Visit.status. See P1-002 decision.
        VisitState.OPEN: {VisitState.CHECKED_IN, VisitState.CANCELLED},
        VisitState.CHECKED_IN: {VisitState.IN_PROGRESS, VisitState.CANCELLED},
        VisitState.IN_PROGRESS: {VisitState.COMPLETED, VisitState.CANCELLED, VisitState.CHECKED_IN},
        VisitState.COMPLETED: set(),
        VisitState.CANCELLED: set(),
    }

    @classmethod
    def get_status(cls, visit) -> Optional[VisitState]:
        """Dual-read helper: parse the legacy status field into VisitState.

        Returns None if the stored value is empty or unrecognised.
        """
        raw = getattr(visit, 'status', None)
        if not raw:
            return None
        try:
            return VisitState(raw)
        except ValueError:
            return None

    @classmethod
    def can_transition(cls, visit, target_state: VisitState) -> bool:
        """Return True if the visit may move to target_state."""
        current = cls.get_status(visit)
        if current is None:
            return False
        return target_state in cls.TRANSITIONS.get(current, set())

    @classmethod
    def transition(cls, visit, target_state: VisitState, *, actor=None, context=None) -> bool:
        """Perform a validated state transition.

        Raises ValueError for invalid transitions. Callers should check
        can_transition() first when they need a soft failure.
        """
        current = cls.get_status(visit)
        if not cls.can_transition(visit, target_state):
            raise ValueError(
                f"Invalid visit transition from {current} to {target_state}"
            )
        _vsm_authorized.active = True
        try:
            visit.status = target_state.value
        finally:
            _vsm_authorized.active = False
        return True

    @classmethod
    def get_allowed_transitions(cls, visit) -> set[VisitState]:
        """Return the set of states reachable from the visit's current state."""
        current = cls.get_status(visit)
        if current is None:
            return set()
        return set(cls.TRANSITIONS.get(current, set()))

    @classmethod
    def _coerce_legacy_status(cls, visit) -> None:
        """Map pre-P1 legacy status strings into the canonical enum."""
        raw = getattr(visit, "status", None)
        if raw in ("WAITING", None, ""):
            _vsm_authorized.active = True
            try:
                visit.status = VisitState.OPEN.value
            finally:
                _vsm_authorized.active = False

    @classmethod
    def try_transition(cls, visit, target_state: VisitState, *, actor=None) -> bool:
        """Soft-failure variant of transition() for orchestrators."""
        try:
            cls.transition(visit, target_state, actor=actor)
            return True
        except ValueError:
            return False

    @classmethod
    def initialize(cls, visit, initial_state: VisitState = VisitState.OPEN) -> None:
        """Set initial clinical status on a newly created visit."""
        _vsm_authorized.active = True
        try:
            visit.status = initial_state.value
        finally:
            _vsm_authorized.active = False

    @classmethod
    def transition_or_archive(
        cls,
        visit,
        target_state: VisitState | VisitArchiveStatus,
        *,
        actor=None,
        user_id: int | None = None,
    ) -> tuple[bool, str]:
        """Clinical transitions via VSM; archival delegates to GatekeeperService."""
        if target_state == VisitArchiveStatus.ARCHIVED:
            if user_id is None:
                return False, "user_id required for archival"
            from services.gatekeeper_service import GatekeeperService
            return GatekeeperService.archive_visit(visit.id, user_id)
        if not isinstance(target_state, VisitState):
            return False, f"invalid target: {target_state}"
        try:
            cls.transition(visit, target_state, actor=actor)
            return True, ""
        except ValueError as exc:
            return False, str(exc)

    @classmethod
    def ensure_in_progress(cls, visit, *, actor=None) -> bool:
        """Transition visit to IN_PROGRESS via a valid path (handles legacy WAITING)."""
        cls._coerce_legacy_status(visit)
        if cls.get_status(visit) == VisitState.IN_PROGRESS:
            return True
        if cls.can_transition(visit, VisitState.IN_PROGRESS):
            return cls.transition(visit, VisitState.IN_PROGRESS, actor=actor)
        if cls.can_transition(visit, VisitState.CHECKED_IN):
            cls.transition(visit, VisitState.CHECKED_IN, actor=actor)
            return cls.transition(visit, VisitState.IN_PROGRESS, actor=actor)
        raise ValueError(f"Cannot move visit to IN_PROGRESS from {getattr(visit, 'status', None)}")

    @classmethod
    def ensure_completed(cls, visit, *, actor=None) -> bool:
        """Transition visit to COMPLETED when clinically finished."""
        cls._coerce_legacy_status(visit)
        if cls.get_status(visit) == VisitState.COMPLETED:
            return True
        if cls.can_transition(visit, VisitState.COMPLETED):
            return cls.transition(visit, VisitState.COMPLETED, actor=actor)
        raise ValueError(f"Cannot move visit to COMPLETED from {getattr(visit, 'status', None)}")
