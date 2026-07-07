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
        security_event,
        # R5 signals
        payment_received,
        invoice_paid, invoice_voided,
        prescription_dispensed,
        stock_low_alert, stock_movement_recorded,
        patient_updated,
        appointment_status_changed,
    )
    from models.visit import Visit
    from models.lab_request import LabResult
    from models.radiology_result import RadiologyResult
    from models.emergency import EmergencyCase
    from models.payment import Payment
    from models.invoice import Invoice
    from models.medication import Prescription, Medication
    from models.patient import Patient
    from models.appointment import Appointment

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

    # ── Payment: emit on status change → CONFIRMED (payment received) ──
    @event.listens_for(Payment, 'after_update')
    def _payment_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.status.history.has_changes():
                new = target.status
                if new in ('CONFIRMED', 'confirmed'):
                    _safe_emit(payment_received, payment_id=target.id,
                               patient_id=target.patient_id, visit_id=target.visit_id,
                               invoice_id=target.invoice_id, amount=target.amount,
                               method=target.method)
                elif new in ('CANCELLED', 'cancelled'):
                    _safe_emit(security_event, event_type='payment_cancelled',
                               payment_id=target.id, amount=target.amount)
        except Exception as exc:
            logger.debug("Payment after_update listener: %s", exc)

    # ── Invoice: emit on status → PAID or VOID ──
    @event.listens_for(Invoice, 'after_update')
    def _invoice_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.status.history.has_changes():
                new = target.status
                if new == 'PAID':
                    _safe_emit(invoice_paid, invoice_id=target.id,
                               visit_id=target.visit_id, total_amount=target.total_amount)
                elif new == 'VOID':
                    _safe_emit(invoice_voided, invoice_id=target.id,
                               visit_id=target.visit_id, total_amount=target.total_amount)
        except Exception as exc:
            logger.debug("Invoice after_update listener: %s", exc)

    # ── Prescription: emit on status → dispensed or cancelled ──
    @event.listens_for(Prescription, 'after_update')
    def _prescription_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.status.history.has_changes():
                new = target.status
                if new in ('dispensed', 'DISPENSED'):
                    _safe_emit(prescription_dispensed, prescription_id=target.id,
                               patient_id=target.patient_id, visit_id=target.visit_id,
                               total_cost=target.total_cost)
        except Exception as exc:
            logger.debug("Prescription after_update listener: %s", exc)

    # ── Medication: emit on stock change or status change ──
    @event.listens_for(Medication, 'after_update')
    def _medication_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.stock_quantity.history.has_changes():
                old = insp.attrs.stock_quantity.history.deleted[0] if insp.attrs.stock_quantity.history.deleted else None
                new = target.stock_quantity
                _safe_emit(stock_movement_recorded, medication_id=target.id,
                           old_quantity=old, new_quantity=new,
                           trade_name=target.trade_name)
                if new <= target.minimum_stock:
                    _safe_emit(stock_low_alert, medication_id=target.id,
                               stock_quantity=new, min_stock=target.minimum_stock,
                               trade_name=target.trade_name)
            if insp.attrs.status.history.has_changes():
                _safe_emit(security_event, event_type='medication_status_changed',
                           medication_id=target.id, old_status=insp.attrs.status.history.deleted[0] if insp.attrs.status.history.deleted else None,
                           new_status=target.status)
        except Exception as exc:
            logger.debug("Medication after_update listener: %s", exc)

    # ── Patient: emit on any update ──
    @event.listens_for(Patient, 'after_update')
    def _patient_after_update(mapper, connection, target):
        try:
            _safe_emit(patient_updated, patient_id=target.id)
        except Exception as exc:
            logger.debug("Patient after_update listener: %s", exc)

    # ── Appointment: emit on status change ──
    @event.listens_for(Appointment, 'after_update')
    def _appointment_after_update(mapper, connection, target):
        try:
            insp = inspect(target)
            if insp.attrs.status.history.has_changes():
                old = insp.attrs.status.history.deleted[0] if insp.attrs.status.history.deleted else None
                _safe_emit(appointment_status_changed, appointment_id=target.id,
                           patient_id=target.patient_id, doctor_id=target.doctor_id,
                           old_status=old, new_status=target.status)
        except Exception as exc:
            logger.debug("Appointment after_update listener: %s", exc)

    logger.info("Model event listeners registered (visit, lab, radiology, emergency, payment, invoice, prescription, medication, patient, appointment)")
