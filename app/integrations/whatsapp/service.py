"""
WhatsAppNotificationService — high-level notification dispatcher
"""
import logging
from typing import Optional
from app.integrations.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)

class WhatsAppNotificationService:
    def __init__(self, client: Optional[WhatsAppClient] = None):
        self.client = client or WhatsAppClient()

    def send_appointment_reminder(self, phone: str, patient_name: str, date_str: str,
                                   time_str: str, doctor_name: str) -> dict:
        body = (
            f"مرحباً {patient_name}\n"
            f"تذكير بموعدك غداً {date_str} الساعة {time_str}\n"
            f"مع الدكتور {doctor_name}\n"
            f"يرجى الحضور قبل 15 دقيقة."
        )
        return self.client.send_text(to=phone, body=body)

    def send_lab_results_ready(self, phone: str, patient_name: str,
                                visit_number: str, login_link: Optional[str] = None) -> dict:
        body = (
            f"مرحباً {patient_name}\n"
            f"نتائج تحاليل زيارتك رقم {visit_number} جاهزة.\n"
        )
        if login_link:
            body += f"يمكنك الاطلاع عليها هنا: {login_link}"
        return self.client.send_text(to=phone, body=body)

    def send_invoice(self, phone: str, patient_name: str, amount: str,
                     receipt_link: Optional[str] = None) -> dict:
        body = (
            f"مرحباً {patient_name}\n"
            f"فاتورتك بمبلغ {amount} جاهزة للدفع.\n"
        )
        if receipt_link:
            body += f"رابط الفاتورة: {receipt_link}"
        return self.client.send_text(to=phone, body=body)

    def send_medication_reminder(self, phone: str, patient_name: str,
                                  medication_name: str, dosage: str) -> dict:
        body = (
            f"مرحباً {patient_name}\n"
            f"تذكير بأخذ الدواء: {medication_name}\n"
            f"الجرعة: {dosage}\n"
            f"شفاك الله."
        )
        return self.client.send_text(to=phone, body=body)
