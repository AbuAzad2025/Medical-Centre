"""
مستمعات الموديلات — Model Event Listeners
Emits signals automatically on status changes and critical updates.
"""
import logging
from sqlalchemy import event, inspect

logger = logging.getLogger(__name__)

_ACTIVE = False


def _safe_emit(signal, **kwargs):
    try:
        signal.send(**kwargs)
    except Exception as exc:
        logger.warning("Signal emit failed: %s", exc)


def register_model_listeners():
    """Register all SQLAlchemy ORM event listeners for models."""
    global _ACTIVE
    if _ACTIVE:
        return
    _ACTIVE = True

    from app.shared.signals import (
        visit_status_changed, visit_completed,
        lab_result_ready, lab_result_validated,
        radiology_result_ready, radiology_report_approved,
        emergency_status_changed,
    )
    from models.visit import Visit
    from models.lab_request import LabResult
    from models.radiology_result import RadiologyResult
    from models.emergency import EmergencyCase

    # ── Visit: emit on status change ──
    @event.listens_for(Visit, 'after_update')
    def _visit_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.status.history.has_changes():
                old = insp.attrs.status.history.deleted[0] if insp.attrs.status.history.deleted else None
                new = target.status
                _safe_emit(visit_status_changed, visit_id=target.id,
                           patient_id=target.patient_id, old_status=old, new_status=new)
                if new in ('COMPLETED', 'completed', 'ARCHIVED', 'archived'):
                    _safe_emit(visit_completed, visit_id=target.id, patient_id=target.patient_id)
        except Exception as exc:
            logger.debug("Visit after_update listener: %s", exc)

    # ── LabResult: emit when status → READY or VALIDATED ──
    @event.listens_for(LabResult, 'after_update')
    def _lab_result_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.status.history.has_changes():
                new = target.status
                if new == 'READY':
                    _safe_emit(lab_result_ready, result_id=target.id,
                               request_id=target.request_id, patient_id=target.patient_id)
                elif new == 'VALIDATED':
                    _safe_emit(lab_result_validated, result_id=target.id,
                               request_id=target.request_id, patient_id=target.patient_id)
        except Exception as exc:
            logger.debug("LabResult after_update listener: %s", exc)

    # ── RadiologyResult: emit when status → READY or APPROVED ──
    @event.listens_for(RadiologyResult, 'after_update')
    def _rad_result_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.status.history.has_changes():
                new = target.status
                if new == 'READY':
                    _safe_emit(radiology_result_ready, result_id=target.id,
                               request_id=target.request_id, patient_id=target.patient_id)
                elif new == 'APPROVED':
                    _safe_emit(radiology_report_approved, result_id=target.id,
                               request_id=target.request_id, patient_id=target.patient_id)
        except Exception as exc:
            logger.debug("RadiologyResult after_update listener: %s", exc)

    # ── EmergencyCase: emit on status change ──
    @event.listens_for(EmergencyCase, 'after_update')
    def _emergency_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.status.history.has_changes():
                old = insp.attrs.status.history.deleted[0] if insp.attrs.status.history.deleted else None
                _safe_emit(emergency_status_changed, case_id=target.id,
                           patient_id=target.patient_id, old_status=old, new_status=target.status)
        except Exception as exc:
            logger.debug("EmergencyCase after_update listener: %s", exc)

    logger.info("Model event listeners registered (visit, lab, radiology, emergency)")
