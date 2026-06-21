import logging
from app.integrations.sms import get_sms_provider

logger = logging.getLogger(__name__)


class SMSService:
    @staticmethod
    def send_sms(phone: str, message: str, tenant=None) -> dict:
        if not phone or not message:
            return {'success': False, 'message': 'رقم الهاتف أو النص فارغ'}
        provider = get_sms_provider(tenant=tenant)
        result = provider.send(phone, message)
        return result

    @staticmethod
    def send_appointment_reminder(patient_name: str, patient_phone: str, doctor_name: str, dept_name: str,
                                  appointment_date: str, appointment_time: str, tenant=None) -> dict:
        message = (
            f"عزيزي {patient_name}، لديك موعد "
            f"{'مع الدكتور ' + doctor_name if doctor_name else ''} "
            f"في {dept_name} بتاريخ {appointment_date} الساعة {appointment_time}."
        )
        return SMSService.send_sms(patient_phone, message, tenant=tenant)

    @staticmethod
    def send_lab_result_notification(patient_name: str, patient_phone: str, test_name: str) -> dict:
        message = f"عزيزي {patient_name}، نتيجة فحص {test_name} جاهزة. يمكنك الاطلاع عليها من خلال بوابة المريض."
        return SMSService.send_sms(patient_phone, message)

    @staticmethod
    def send_custom_notification(phone: str, message: str) -> dict:
        return SMSService.send_sms(phone, message)