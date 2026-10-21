import logging

from sqlalchemy import select

from app.extensions import db

logger = logging.getLogger(__name__)


class SMSProvider:
    def send(self, phone: str, message: str) -> dict:
        raise NotImplementedError


class LogSMSProvider(SMSProvider):
    """Writes the message to the log instead of sending it.

    This is the provider used when SMS is deliberately switched off, which is
    what a development or test environment wants. The message is not delivered,
    and the result says so: ``delivered`` is False. Reporting a plain success
    hides the fact from any caller that needs to know the message went
    nowhere.
    """

    def send(self, phone: str, message: str) -> dict:
        logger.info(f'[SMS] To: {phone} | Message: {message}')
        return {
            'success': True,
            'provider': 'log',
            'delivered': False,
            'message': 'تم تسجيل الرسالة في السجل',
        }


class UnconfiguredSMSProvider(SMSProvider):
    """Used when a live SMS provider was selected but its configuration is broken.

    Reporting success here is a lie with consequences: the operator asked for
    Twilio, the credentials are missing or incomplete, and every message -
    OTP codes, appointment reminders, lab-result notices - vanishes while the
    system reports it as sent. The notification queue then marks those rows
    SENT, so the record of a delivery that never happened is all that is left.
    """

    def send(self, phone: str, message: str) -> dict:
        logger.error(
            '[SMS] the configured SMS provider is incomplete; the message to %s was not delivered',
            phone,
        )
        return {
            'success': False,
            'provider': 'unconfigured',
            'delivered': False,
            'message': 'إعداد مزود الرسائل غير مكتمل، لم تُرسل الرسالة',
        }


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
            twilio_msg = client.messages.create(body=message, from_=self.from_number, to=phone)
            logger.info(f'[Twilio] Sent to {phone}, SID: {twilio_msg.sid}')
            return {
                'success': True,
                'provider': 'twilio',
                'message_id': twilio_msg.sid,
                'message': 'تم إرسال الرسالة بنجاح',
            }
        except Exception as e:
            logger.exception('[Twilio] Failed to send to %s: %s')
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
            logger.warning(
                '[SMS] Tenant Twilio config incomplete; the message will not be delivered'
            )
            return UnconfiguredSMSProvider()
        return LogSMSProvider()

    # Fallback to global SystemConfig (super-admin configured)
    from models.system_config import SystemConfig

    enabled = (
        db.session.execute(select(SystemConfig).filter_by(config_key='sms_enabled'))
        .scalars()
        .first()
    )
    if not enabled or not enabled.get_value():
        return LogSMSProvider()
    provider_name_cfg = (
        db.session.execute(select(SystemConfig).filter_by(config_key='sms_provider'))
        .scalars()
        .first()
    )
    provider_name = provider_name_cfg.get_value() if provider_name_cfg else 'log'
    if provider_name == 'twilio':
        sid = (
            db.session.execute(select(SystemConfig).filter_by(config_key='twilio_account_sid'))
            .scalars()
            .first()
        )
        token = (
            db.session.execute(select(SystemConfig).filter_by(config_key='twilio_auth_token'))
            .scalars()
            .first()
        )
        sender = (
            db.session.execute(select(SystemConfig).filter_by(config_key='twilio_phone_number'))
            .scalars()
            .first()
        )
        if (
            sid
            and token
            and sender
            and sid.get_value()
            and token.get_value()
            and sender.get_value()
        ):
            return TwilioSMSProvider(sid.get_value(), token.get_value(), sender.get_value())
        logger.warning('[SMS] Global Twilio config incomplete; the message will not be delivered')
        return UnconfiguredSMSProvider()
    return LogSMSProvider()
