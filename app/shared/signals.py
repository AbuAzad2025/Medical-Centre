"""
إشارات النظام — System-wide Signals for decoupled event handling
All medical center events flow through these signals.
"""
from blinker import Namespace

_signals = Namespace()

# Patient events
patient_created = _signals.signal('patient-created')
patient_updated = _signals.signal('patient-updated')
patient_merged = _signals.signal('patient-merged')

# Visit events
visit_created = _signals.signal('visit-created')
visit_status_changed = _signals.signal('visit-status-changed')
visit_completed = _signals.signal('visit-completed')

# Appointment events
appointment_created = _signals.signal('appointment-created')
appointment_status_changed = _signals.signal('appointment-status-changed')
appointment_converted = _signals.signal('appointment-converted')

# Lab events
lab_order_created = _signals.signal('lab-order-created')
lab_result_ready = _signals.signal('lab-result-ready')
lab_result_validated = _signals.signal('lab-result-validated')

# Radiology events
radiology_order_created = _signals.signal('radiology-order-created')
radiology_result_ready = _signals.signal('radiology-result-ready')
radiology_report_approved = _signals.signal('radiology-report-approved')

# Prescription & Pharmacy events
prescription_issued = _signals.signal('prescription-issued')
prescription_dispensed = _signals.signal('prescription-dispensed')
stock_low_alert = _signals.signal('stock-low-alert')
stock_movement_recorded = _signals.signal('stock-movement-recorded')

# Billing events
invoice_created = _signals.signal('invoice-created')
invoice_paid = _signals.signal('invoice-paid')
invoice_voided = _signals.signal('invoice-voided')
payment_received = _signals.signal('payment-received')

# Emergency events
emergency_case_created = _signals.signal('emergency-case-created')
emergency_status_changed = _signals.signal('emergency-status-changed')

# User & Security events
user_created = _signals.signal('user-created')
user_login = _signals.signal('user-login')
user_logout = _signals.signal('user-logout')
security_event = _signals.signal('security-event')
