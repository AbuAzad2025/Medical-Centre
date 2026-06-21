import logging
import os

logger = logging.getLogger(__name__)


class SMSProvider:
    def send(self, phone: str, message: str) -> dict:
        raise NotImplementedError


class LogSMSProvider(SMSProvider):
    def send(self, phone: str, message: str) -> dict:
        logger.info(f"[SMS] To: {phone} | Message: {message}")
        return {'success': True, 'provider': 'log', 'message': 'تم تسجيل الرسالة في السجل'}


class TwilioSMSProvider(SMSProvider):
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self._client = None

    def _get_client(self):
        if self._client is None:
            from twilio.rest import Client
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    def send(self, phone: str, message: str) -> dict:
        try:
            client = self._get_client()
            twilio_msg = client.messages.create(
                body=message,
                from_=self.from_number,
                to=phone
            )
            logger.info(f"[Twilio] Sent to {phone}, SID: {twilio_msg.sid}")
            return {
                'success': True,
                'provider': 'twilio',
                'message_id': twilio_msg.sid,
                'message': 'تم إرسال الرسالة بنجاح'
            }
        except Exception as e:
            logger.error(f"[Twilio] Failed to send to {phone}: {e}")
            return {'success': False, 'provider': 'twilio', 'message': str(e)}


def get_sms_provider(tenant=None):
    if tenant and tenant.settings:
        sms_cfg = tenant.settings.get('sms', {})
        if not sms_cfg.get('enabled', False):
            return LogSMSProvider()
        provider = sms_cfg.get('provider', 'log')
        if provider == 'twilio':
            sid = sms_cfg.get('twilio_account_sid', '')
            token = sms_cfg.get('twilio_auth_token', '')
            sender = sms_cfg.get('twilio_phone_number', '')
            if sid and token and sender:
                return TwilioSMSProvider(sid, token, sender)
            logger.warning("[SMS] Tenant Twilio config incomplete, falling back to LogSMSProvider")
            return LogSMSProvider()
        return LogSMSProvider()

    # Fallback to global SystemConfig (super-admin configured)
    from models.system_config import SystemConfig
    enabled = SystemConfig.query.filter_by(config_key='sms_enabled').first()
    if not enabled or not enabled.get_value():
        return LogSMSProvider()
    provider_name_cfg = SystemConfig.query.filter_by(config_key='sms_provider').first()
    provider_name = provider_name_cfg.get_value() if provider_name_cfg else 'log'
    if provider_name == 'twilio':
        sid = SystemConfig.query.filter_by(config_key='twilio_account_sid').first()
        token = SystemConfig.query.filter_by(config_key='twilio_auth_token').first()
        sender = SystemConfig.query.filter_by(config_key='twilio_phone_number').first()
        if sid and token and sender and sid.get_value() and token.get_value() and sender.get_value():
            return TwilioSMSProvider(sid.get_value(), token.get_value(), sender.get_value())
        else:
            logger.warning("[SMS] Global Twilio config incomplete, falling back to LogSMSProvider")
            return LogSMSProvider()
    return LogSMSProvider()