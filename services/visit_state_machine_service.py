"""Visit lifecycle state machine.

P1-001 introduces a canonical state machine for Visit.status while keeping
legacy direct reads/writes operational during the dual-read migration window.

Rules:
- The service is the authoritative source for transition validity.
- Legacy code may still read visit.status directly; this service provides a
  dual-read helper that returns the canonical enum value.
- Routes being migrated should call transition() instead of mutating status.
"""
from __future__ import annotations

from typing import Optional

from app.shared.enums import VisitState


class VisitStateMachineService:
    """Canonical visit lifecycle transitions."""

    TRANSITIONS: dict[VisitState, set[VisitState]] = {
        # Clinical lifecycle ends at COMPLETED. Archival is an administrative
        # action tracked by Visit.archive_status (GatekeeperService), not by
        # Visit.status. See P1-002 decision.
        VisitState.OPEN: {VisitState.CHECKED_IN, VisitState.CANCELLED, VisitState.NO_SHOW},
        VisitState.CHECKED_IN: {VisitState.IN_PROGRESS, VisitState.CANCELLED, VisitState.NO_SHOW},
        VisitState.IN_PROGRESS: {VisitState.COMPLETED, VisitState.CANCELLED, VisitState.CHECKED_IN},
        VisitState.COMPLETED: set(),
        VisitState.ARCHIVED: set(),
        VisitState.CANCELLED: set(),
        VisitState.NO_SHOW: set(),
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
        visit.status = target_state.value
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
            visit.status = VisitState.OPEN.value

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
