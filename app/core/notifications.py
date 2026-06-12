"""
Unified Notification Service — WhatsApp, Email, SMS, Push
Wired into workflow state transitions
"""
import logging
from typing import Optional
from app.integrations.whatsapp.service import WhatsAppNotificationService

logger = logging.getLogger(__name__)

class NotificationDispatcher:
    """Dispatches notifications across all channels based on tenant config."""

    def __init__(self, tenant=None):
        self.tenant = tenant
        self.whatsapp = WhatsAppNotificationService()

    def _should_send(self, channel: str) -> bool:
        if not self.tenant:
            return True
        # TODO: read tenant notification preferences from DB
        return True

    def notify_appointment_confirmed(self, phone: str, patient_name: str,
                                     date_str: str, time_str: str, doctor_name: str):
        if self._should_send('whatsapp'):
            try:
                self.whatsapp.send_appointment_reminder(phone, patient_name, date_str, time_str, doctor_name)
            except Exception as e:
                logger.warning(f"WhatsApp appointment reminder failed: {e}")

    def notify_lab_results_ready(self, phone: str, patient_name: str,
                                  visit_number: str, login_link: Optional[str] = None):
        if self._should_send('whatsapp'):
            try:
                self.whatsapp.send_lab_results_ready(phone, patient_name, visit_number, login_link)
            except Exception as e:
                logger.warning(f"WhatsApp lab results failed: {e}")

    def notify_invoice_generated(self, phone: str, patient_name: str,
                                  amount: str, receipt_link: Optional[str] = None):
        if self._should_send('whatsapp'):
            try:
                self.whatsapp.send_invoice(phone, patient_name, amount, receipt_link)
            except Exception as e:
                logger.warning(f"WhatsApp invoice failed: {e}")

    def notify_medication_dispensed(self, phone: str, patient_name: str,
                                     medication_name: str, dosage: str):
        if self._should_send('whatsapp'):
            try:
                self.whatsapp.send_medication_reminder(phone, patient_name, medication_name, dosage)
            except Exception as e:
                logger.warning(f"WhatsApp medication reminder failed: {e}")
