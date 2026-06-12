"""
Hook notifications into workflow state transitions
"""
from app.core.notifications import NotificationDispatcher

def notify_on_visit_status_change(visit, old_status: str, new_status: str, tenant=None):
    """Send notifications when visit status changes."""
    dispatcher = NotificationDispatcher(tenant)
    if new_status == "completed":
        patient = getattr(visit, 'patient', None)
        if patient and getattr(patient, 'phone', None):
            dispatcher.notify_lab_results_ready(
                phone=patient.phone,
                patient_name=getattr(patient, 'full_name', ''),
                visit_number=str(getattr(visit, 'visit_number', visit.id)),
            )

def notify_on_lab_approved(lab_order, tenant=None):
    """Send WhatsApp when lab results are approved."""
    dispatcher = NotificationDispatcher(tenant)
    visit = getattr(lab_order, 'visit', None)
    patient = getattr(visit, 'patient', None) if visit else None
    if patient and getattr(patient, 'phone', None):
        dispatcher.notify_lab_results_ready(
            phone=patient.phone,
            patient_name=getattr(patient, 'full_name', ''),
            visit_number=str(getattr(visit, 'visit_number', getattr(visit, 'id', ''))),
        )

def notify_on_invoice_posted(invoice, tenant=None):
    """Send WhatsApp when invoice is posted."""
    dispatcher = NotificationDispatcher(tenant)
    visit = getattr(invoice, 'visit', None)
    patient = getattr(visit, 'patient', None) if visit else None
    if patient and getattr(patient, 'phone', None):
        dispatcher.notify_invoice_generated(
            phone=patient.phone,
            patient_name=getattr(patient, 'full_name', ''),
            amount=str(getattr(invoice, 'total_amount', '')),
        )

def notify_on_prescription_dispensed(prescription, tenant=None):
    """Send WhatsApp when prescription is dispensed."""
    dispatcher = NotificationDispatcher(tenant)
    patient = getattr(prescription, 'patient', None)
    if patient and getattr(patient, 'phone', None):
        items = getattr(prescription, 'items', [])
        if items:
            first = items[0]
            med_name = getattr(getattr(first, 'medication', None), 'trade_name', '')
            dosage = getattr(first, 'dosage', '')
            dispatcher.notify_medication_dispensed(
                phone=patient.phone,
                patient_name=getattr(patient, 'full_name', ''),
                medication_name=med_name,
                dosage=dosage,
            )
