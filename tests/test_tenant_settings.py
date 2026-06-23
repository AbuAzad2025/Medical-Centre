import pytest
from unittest.mock import patch, MagicMock


class TestTenantSettingsModel:
    def test_tenant_has_settings_column(self, app, test_tenant):
        assert hasattr(test_tenant, 'settings')
        assert test_tenant.settings is None or isinstance(test_tenant.settings, dict)

    def test_tenant_settings_save_and_retrieve(self, app, test_tenant):
        from app_factory import db
        test_tenant.settings = {
            'general': {'language': 'en', 'timezone': 'UTC'},
            'sms': {'enabled': True, 'provider': 'log'}
        }
        db.session.commit()

        # Re-fetch from DB
        from app.core.tenant.models import Tenant
        db.session.expire_all()
        tenant2 = Tenant.query.get(test_tenant.id)
        assert tenant2.settings['general']['language'] == 'en'
        assert tenant2.settings['sms']['enabled'] is True

        # Cleanup
        test_tenant.settings = None
        db.session.commit()


class TestGetSMSProviderWithTenant:
    def test_returns_log_provider_when_tenant_sms_disabled(self, app, test_tenant):
        test_tenant.settings = {'sms': {'enabled': False, 'provider': 'log'}}
        from app.integrations.sms import get_sms_provider, LogSMSProvider
        provider = get_sms_provider(tenant=test_tenant)
        assert isinstance(provider, LogSMSProvider)

    def test_returns_log_provider_when_tenant_sms_enabled_log(self, app, test_tenant):
        test_tenant.settings = {'sms': {'enabled': True, 'provider': 'log'}}
        from app.integrations.sms import get_sms_provider, LogSMSProvider
        provider = get_sms_provider(tenant=test_tenant)
        assert isinstance(provider, LogSMSProvider)

    def test_returns_log_when_twilio_config_incomplete(self, app, test_tenant):
        test_tenant.settings = {
            'sms': {'enabled': True, 'provider': 'twilio', 'twilio_account_sid': '', 'twilio_auth_token': '', 'twilio_phone_number': ''}
        }
        from app.integrations.sms import get_sms_provider, LogSMSProvider
        provider = get_sms_provider(tenant=test_tenant)
        assert isinstance(provider, LogSMSProvider)

    def test_returns_twilio_when_config_complete(self, app, test_tenant):
        test_tenant.settings = {
            'sms': {
                'enabled': True, 'provider': 'twilio',
                'twilio_account_sid': 'AC123', 'twilio_auth_token': 'token123',
                'twilio_phone_number': '+12025551234'
            }
        }
        from app.integrations.sms import get_sms_provider, TwilioSMSProvider
        with patch('app.integrations.sms.provider.TwilioSMSProvider._get_client'):
            provider = get_sms_provider(tenant=test_tenant)
            assert isinstance(provider, TwilioSMSProvider)
            assert provider.account_sid == 'AC123'

    def test_fallsback_to_global_when_no_tenant(self, app):
        from app.integrations.sms import get_sms_provider, LogSMSProvider
        provider = get_sms_provider(tenant=None)
        assert isinstance(provider, LogSMSProvider)


class TestSMSServiceWithTenant:
    def test_send_sms_with_tenant(self, app, test_tenant):
        from services.sms_service import SMSService
        with patch('services.sms_service.get_sms_provider') as mock_factory:
            mock_provider = MagicMock()
            mock_provider.send.return_value = {'success': True, 'message': 'OK'}
            mock_factory.return_value = mock_provider
            result = SMSService.send_sms(phone='+970599123456', message='Hello', tenant=test_tenant)
            assert result['success'] is True
            mock_factory.assert_called_once_with(tenant=test_tenant)
            mock_provider.send.assert_called_once_with('+970599123456', 'Hello')


class TestManagerSettingsRoute:
    def test_settings_page_loads(self, client, manager_auth_client):
        resp = client.get('/manager/settings')
        assert resp.status_code in (200, 302)

    def test_settings_page_authenticated(self, client, manager_auth_client, test_tenant):
        resp = client.get('/manager/settings')
        assert resp.status_code == 200

    def test_save_settings(self, client, manager_auth_client, test_tenant):
        from app_factory import db
        resp = client.post('/manager/settings', json={
            'general': {'language': 'en', 'timezone': 'UTC', 'currency': 'USD', 'date_format': 'yyyy-mm-dd'},
            'sms': {'enabled': True, 'provider': 'log'}
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

        db.session.expire_all()
        from app.core.tenant.models import Tenant
        tenant = Tenant.query.get(test_tenant.id)
        assert tenant.settings['general']['language'] == 'en'
        assert tenant.settings['sms']['enabled'] is True

    def test_save_lab_settings(self, client, manager_auth_client, test_tenant):
        from app_factory import db
        resp = client.post('/manager/settings', json={
            'lab': {
                'auto_generate_request_number': True,
                'request_number_prefix': 'CBC-',
                'result_decimal_places': 3,
                'default_result_status': 'READY',
                'critical_result_notification': True,
                'critical_result_sms': True,
            }
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

        db.session.expire_all()
        from app.core.tenant.models import Tenant
        tenant = Tenant.query.get(test_tenant.id)
        assert tenant.settings['lab']['auto_generate_request_number'] is True
        assert tenant.settings['lab']['request_number_prefix'] == 'CBC-'
        assert tenant.settings['lab']['result_decimal_places'] == 3

    def test_save_radiology_settings(self, client, manager_auth_client, test_tenant):
        from app_factory import db
        resp = client.post('/manager/settings', json={
            'radiology': {
                'auto_generate_request_number': False,
                'request_number_prefix': 'MRI-',
                'default_modality': 'MRI',
                'pacs_enabled': True,
                'pacs_server_url': 'http://pacs.local:8042',
                'dicom_aetitle': 'TEST_AE',
            }
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

        db.session.expire_all()
        from app.core.tenant.models import Tenant
        tenant = Tenant.query.get(test_tenant.id)
        assert tenant.settings['radiology']['pacs_enabled'] is True
        assert tenant.settings['radiology']['pacs_server_url'] == 'http://pacs.local:8042'
        assert tenant.settings['radiology']['dicom_aetitle'] == 'TEST_AE'

    def test_save_all_sections_together(self, client, manager_auth_client, test_tenant):
        from app_factory import db
        resp = client.post('/manager/settings', json={
            'general': {'language': 'ar', 'timezone': 'Asia/Gaza', 'currency': 'ILS', 'date_format': 'dd/mm/yyyy'},
            'sms': {'enabled': False, 'provider': 'log'},
            'lab': {'auto_generate_request_number': True, 'request_number_prefix': 'LAB-', 'result_decimal_places': 2, 'default_result_status': 'PENDING', 'critical_result_notification': True, 'critical_result_sms': False},
            'radiology': {'auto_generate_request_number': True, 'request_number_prefix': 'RAD-', 'default_modality': 'CT', 'pacs_enabled': False, 'pacs_server_url': '', 'dicom_aetitle': 'MED_SYS'},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

        db.session.expire_all()
        from app.core.tenant.models import Tenant
        tenant = Tenant.query.get(test_tenant.id)
        assert tenant.settings['general']['language'] == 'ar'
        assert tenant.settings['sms']['enabled'] is False
        assert tenant.settings['lab']['auto_generate_request_number'] is True
        assert tenant.settings['radiology']['default_modality'] == 'CT'
