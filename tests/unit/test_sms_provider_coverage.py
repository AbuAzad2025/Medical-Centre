"""Coverage tests for app/integrations/sms/provider.py"""

from unittest.mock import patch

from app.integrations.sms.provider import (
    LogSMSProvider,
    SMSProvider,
    TwilioSMSProvider,
    UnconfiguredSMSProvider,
    get_sms_provider,
)


class TestSMSProvider:
    def test_log_provider_send(self):
        p = LogSMSProvider()
        result = p.send('1234567890', 'Hello')
        assert result['success'] is True
        assert result['provider'] == 'log'
        assert result['delivered'] is False

    def test_unconfigured_provider_send(self):
        p = UnconfiguredSMSProvider()
        result = p.send('1234567890', 'Hello')
        assert result['success'] is False
        assert result['provider'] == 'unconfigured'

    def test_twilio_provider_init(self):
        p = TwilioSMSProvider('sid', 'token', 'from_num')
        assert p.account_sid == 'sid'
        assert p.auth_token == 'token'
        assert p.from_number == 'from_num'

    def test_twilio_send_success(self):
        with patch.object(TwilioSMSProvider, '_get_client') as mock_client:
            mock_msg = type('Msg', (), {'sid': 'SM123'})()
            mock_client.return_value.messages.create.return_value = mock_msg
            p = TwilioSMSProvider('sid', 'token', 'from_num')
            result = p.send('1234567890', 'Hello')
            assert result['success'] is True
            assert result['provider'] == 'twilio'

    def test_twilio_send_failure(self):
        with patch.object(TwilioSMSProvider, '_get_client') as mock_client:
            mock_client.return_value.messages.create.side_effect = Exception('Twilio error')
            p = TwilioSMSProvider('sid', 'token', 'from_num')
            result = p.send('1234567890', 'Hello')
            assert result['success'] is False
            assert result['provider'] == 'twilio'

    def test_get_sms_provider_no_tenant_disabled(self, app, db):
        provider = get_sms_provider()
        assert provider is not None

    def test_get_sms_provider_tenant_disabled(self, app, db, test_tenant):
        tenant = type('Tenant', (), {'settings': {'sms': {'enabled': False}}})()
        provider = get_sms_provider(tenant=tenant)
        assert isinstance(provider, LogSMSProvider)

    def test_get_sms_provider_tenant_twilio_complete(self, app, db, test_tenant):
        tenant = type('Tenant', (), {'settings': {'sms': {'enabled': True, 'provider': 'twilio', 'twilio_account_sid': 'sid', 'twilio_auth_token': 'token', 'twilio_phone_number': 'num'}}})()
        provider = get_sms_provider(tenant=tenant)
        assert isinstance(provider, TwilioSMSProvider)

    def test_get_sms_provider_tenant_twilio_incomplete(self, app, db, test_tenant):
        tenant = type('Tenant', (), {'settings': {'sms': {'enabled': True, 'provider': 'twilio'}}})()
        provider = get_sms_provider(tenant=tenant)
        assert isinstance(provider, UnconfiguredSMSProvider)

    def test_get_sms_provider_tenant_log(self, app, db, test_tenant):
        tenant = type('Tenant', (), {'settings': {'sms': {'enabled': True, 'provider': 'log'}}})()
        provider = get_sms_provider(tenant=tenant)
        assert isinstance(provider, LogSMSProvider)

    def test_get_sms_provider_no_enabled_config(self, app, db):
        provider = get_sms_provider()
        assert provider is not None

    def test_sms_provider_base(self):
        p = SMSProvider()
        try:
            p.send('123', 'msg')
        except NotImplementedError:
            pass
