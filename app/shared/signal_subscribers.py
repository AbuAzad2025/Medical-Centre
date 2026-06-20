"""
مشتركو الإشارات — Signal Subscribers
Connects system-wide signals to handlers (audit log, notifications, etc.)
"""
import logging

logger = logging.getLogger(__name__)


def _safe_send(signal, **kwargs):
    """Emit a signal and log errors without crashing."""
    try:
        signal.send(**kwargs)
    except Exception as exc:
        logger.warning("Signal %s failed: %s", signal.name, exc)


def connect_audit_logger(signal, entity_name):
    """Generic audit-log subscriber factory."""
    def _handler(sender, **kwargs):
        logger.info(
            "AUDIT %s | entity=%s | data=%s",
            signal.name, entity_name, {k: v for k, v in kwargs.items()
                                       if k not in ('password', 'token', 'secret')}
        )
    signal.connect(_handler, weak=False)
    return _handler


def connect_notification(signal, notification_type, title_template, message_template):
    """Generic notification subscriber factory."""
    from services.notification_service import NotificationService

    def _handler(sender, **kwargs):
        recipient_id = kwargs.get('recipient_id') or kwargs.get('user_id')
        recipient_role = kwargs.get('recipient_role')
        title = title_template.format(**kwargs)
        message = message_template.format(**kwargs)
        NotificationService.send_notification(
            recipient_id=recipient_id,
            recipient_role=recipient_role,
            title=title,
            message=message,
            notification_type=notification_type,
            related_entity_type=kwargs.get('entity_type'),
            related_entity_id=kwargs.get('entity_id'),
        )
    signal.connect(_handler, weak=False)
    return _handler


def register_all_subscribers():
    """Called once at app startup to connect all signals -> handlers."""
    from app.shared.signals import (
        patient_created, patient_updated,
        visit_created, visit_status_changed, visit_completed,
        appointment_created, appointment_status_changed,
        lab_order_created, lab_result_ready, lab_result_validated,
        radiology_order_created, radiology_result_ready, radiology_report_approved,
        prescription_issued, prescription_dispensed,
        stock_low_alert, stock_movement_recorded,
        invoice_created, invoice_paid, invoice_voided, payment_received,
        emergency_case_created, emergency_status_changed,
        user_created, user_login, user_logout, security_event,
    )
    
    # ── Audit logger for every signal ──
    _all_signals = [
        (patient_created, 'Patient'),
        (patient_updated, 'Patient'),
        (visit_created, 'Visit'),
        (visit_status_changed, 'Visit'),
        (visit_completed, 'Visit'),
        (appointment_created, 'Appointment'),
        (appointment_status_changed, 'Appointment'),
        (lab_order_created, 'LabRequest'),
        (lab_result_ready, 'LabResult'),
        (lab_result_validated, 'LabResult'),
        (radiology_order_created, 'RadiologyRequest'),
        (radiology_result_ready, 'RadiologyResult'),
        (radiology_report_approved, 'RadiologyResult'),
        (prescription_issued, 'Prescription'),
        (prescription_dispensed, 'Prescription'),
        (invoice_created, 'Invoice'),
        (invoice_paid, 'Invoice'),
        (invoice_voided, 'Invoice'),
        (payment_received, 'Payment'),
        (emergency_case_created, 'EmergencyCase'),
        (emergency_status_changed, 'EmergencyCase'),
        (user_created, 'User'),
        (user_login, 'User'),
        (user_logout, 'User'),
        (security_event, 'Security'),
    ]
    for signal, entity in _all_signals:
        connect_audit_logger(signal, entity)

    # ── Notifications ──
    connect_notification(
        lab_result_ready, 'lab',
        'نتيجة مختبر جاهزة', 'نتيجة الفحص للمريض {patient_name} جاهزة للمراجعة'
    )
    connect_notification(
        radiology_result_ready, 'radiology',
        'تقرير أشعة جاهز', 'تقرير الأشعة للمريض {patient_name} جاهز'
    )
    connect_notification(
        stock_low_alert, 'warning',
        'تنبيه: مخزون منخفض', 'الدواء {medication_name} مخزونه منخفض ({current_stock})'
    )
    connect_notification(
        emergency_case_created, 'emergency',
        'حالة طوارئ جديدة', 'حالة طوارئ جديدة للمريض {patient_name} - {severity}'
    )
    connect_notification(
        emergency_status_changed, 'emergency',
        'تحديث حالة طوارئ', 'تغيير حالة الطوارئ للمريض {patient_name} إلى {new_status}'
    )

    logger.info("All signal subscribers registered (%d signals)", len(_all_signals))
