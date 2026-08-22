"""Tests for app.integrations.whatsapp modules.

Covers WhatsAppNotificationService and WhatsAppClient.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.integrations.whatsapp.service import WhatsAppNotificationService
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp import WhatsAppNotificationService as ServiceFromPackage


@pytest.fixture
def mock_client():
    """Provide a mock WhatsAppClient."""
    return MagicMock()


class TestWhatsAppNotificationService:
    """Tests for WhatsAppNotificationService class."""

    @patch('app.integrations.whatsapp.service.WhatsAppClient')
    def test_init_with_mocked_client(self, mock_client_cls):
        """Test init with mocked client class."""
        mock_client_cls.return_value = MagicMock()
        service = WhatsAppNotificationService()
        mock_client_cls.assert_called_once()
        assert isinstance(service.client, MagicMock)

    def test_init_with_explicit_client(self, mock_client):
        """Test init with explicit client."""
        service = WhatsAppNotificationService(client=mock_client)
        assert service.client is mock_client

    def test_send_appointment_reminder(self, mock_client):
        """Test sending appointment reminder."""
        service = WhatsAppNotificationService(client=mock_client)
        mock_client.send_text.return_value = {'success': True}

        result = service.send_appointment_reminder(
            phone='+123456789',
            patient_name='John Doe',
            date_str='2024-01-15',
            time_str='10:30',
            doctor_name='Dr. Smith',
        )

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert call_args[1]['to'] == '+123456789'
        assert 'John Doe' in call_args[1]['body']
        assert '2024-01-15' in call_args[1]['body']
        assert '10:30' in call_args[1]['body']
        assert 'Dr. Smith' in call_args[1]['body']
        assert '15 دقيقة' in call_args[1]['body']
        assert result == {'success': True}

    def test_send_lab_results_ready_with_link(self, mock_client):
        """Test sending lab results with login link."""
        service = WhatsAppNotificationService(client=mock_client)

        service.send_lab_results_ready(
            phone='+123456789',
            patient_name='Jane Doe',
            visit_number='V123',
            login_link='https://example.com/login',
        )

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert 'Jane Doe' in call_args[1]['body']
        assert 'V123' in call_args[1]['body']
        assert 'https://example.com/login' in call_args[1]['body']

    def test_send_lab_results_ready_without_link(self, mock_client):
        """Test sending lab results without login link."""
        service = WhatsAppNotificationService(client=mock_client)

        service.send_lab_results_ready(
            phone='+123456789',
            patient_name='Jane Doe',
            visit_number='V123',
        )

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert 'Jane Doe' in call_args[1]['body']
        assert 'V123' in call_args[1]['body']
        assert 'login_link' not in call_args[1]['body']

    def test_send_invoice_with_receipt_link(self, mock_client):
        """Test sending invoice with receipt link."""
        service = WhatsAppNotificationService(client=mock_client)

        service.send_invoice(
            phone='+123456789',
            patient_name='John Doe',
            amount='150.00',
            receipt_link='https://example.com/receipt/123',
        )

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert 'John Doe' in call_args[1]['body']
        assert '150.00' in call_args[1]['body']
        assert 'https://example.com/receipt/123' in call_args[1]['body']

    def test_send_invoice_without_receipt_link(self, mock_client):
        """Test sending invoice without receipt link."""
        service = WhatsAppNotificationService(client=mock_client)

        service.send_invoice(
            phone='+123456789',
            patient_name='John Doe',
            amount='150.00',
        )

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert 'John Doe' in call_args[1]['body']
        assert '150.00' in call_args[1]['body']
        assert 'receipt_link' not in call_args[1]['body']

    def test_send_medication_reminder(self, mock_client):
        """Test sending medication reminder."""
        service = WhatsAppNotificationService(client=mock_client)

        service.send_medication_reminder(
            phone='+123456789',
            patient_name='John Doe',
            medication_name='Aspirin',
            dosage='100mg',
        )

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert 'John Doe' in call_args[1]['body']
        assert 'Aspirin' in call_args[1]['body']
        assert '100mg' in call_args[1]['body']
        assert 'شفاك الله' in call_args[1]['body']


class TestWhatsAppClient:
    """Tests for WhatsAppClient class."""

    def test_init_with_explicit_params(self):
        """Test init with explicit API token and phone number ID."""
        client = WhatsAppClient(
            api_token='test-token',
            phone_number_id='test-phone-id',
        )
        assert client.api_token == 'test-token'
        assert client.phone_number_id == 'test-phone-id'

    def test_init_from_environment(self, monkeypatch):
        """Test init from environment variables."""
        monkeypatch.setenv('WHATSAPP_API_TOKEN', 'env-token')
        monkeypatch.setenv('WHATSAPP_PHONE_NUMBER_ID', 'env-phone-id')
        client = WhatsAppClient()
        assert client.api_token == 'env-token'
        assert client.phone_number_id == 'env-phone-id'
        monkeypatch.delenv('WHATSAPP_API_TOKEN', raising=False)
        monkeypatch.delenv('WHATSAPP_PHONE_NUMBER_ID', raising=False)

    def test_init_raises_without_credentials(self):
        """Test init raises RuntimeError when credentials missing."""
        with patch.dict('os.environ', {}, clear=False):
            with patch('os.environ.get', return_value=None):
                with pytest.raises(RuntimeError, match='are required'):
                    WhatsAppClient()

    def test_init_raises_with_partial_credentials(self):
        """Test init raises when only token is provided but not phone_id."""
        env = {'WHATSAPP_API_TOKEN': 'partial-token'}
        with patch.dict('os.environ', env, clear=True):
            with pytest.raises(RuntimeError, match='are required'):
                WhatsAppClient()

    def test_init_with_only_token_provided(self):
        """Test init raises when only api_token is provided."""
        with patch(
            'os.environ.get',
            side_effect=lambda key, default=None: 'token' if key == 'WHATSAPP_API_TOKEN' else None,
        ):
            with pytest.raises(RuntimeError, match='are required'):
                WhatsAppClient()

    def test_url_method(self):
        """Test _url generates correct URL."""
        client = WhatsAppClient(api_token='token', phone_number_id='phone-id')
        url = client._url('messages')
        assert url == 'https://graph.facebook.com/v18.0/phone-id/messages'

    def test_headers_method(self):
        """Test _headers generates correct headers."""
        client = WhatsAppClient(api_token='test-token', phone_number_id='phone-id')
        headers = client._headers()
        assert headers['Authorization'] == 'Bearer test-token'
        assert headers['Content-Type'] == 'application/json'

    @patch('app.integrations.whatsapp.client.requests')
    def test_send_text(self, mock_requests):
        """Test send_text method."""
        client = WhatsAppClient(api_token='token', phone_number_id='phone-id')
        mock_response = MagicMock()
        mock_response.json.return_value = {'messages': [{'id': 'msg123'}]}
        mock_requests.post.return_value = mock_response

        result = client.send_text(to='+123456789', body='Hello')

        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert 'messages' in call_args[0][0]
        assert call_args[1]['headers']['Authorization'] == 'Bearer token'
        assert call_args[1]['json']['to'] == '+123456789'
        assert call_args[1]['json']['type'] == 'text'
        assert call_args[1]['json']['text']['body'] == 'Hello'
        assert result == {'messages': [{'id': 'msg123'}]}

    @patch('app.integrations.whatsapp.client.requests')
    def test_send_text_with_preview_url(self, mock_requests):
        """Test send_text with preview_url enabled."""
        client = WhatsAppClient(api_token='token', phone_number_id='phone-id')
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True}
        mock_requests.post.return_value = mock_response

        client.send_text(to='+123', body='Check this', preview_url=True)
        call_args = mock_requests.post.call_args
        assert call_args[1]['json']['text']['preview_url'] is True

    @patch('app.integrations.whatsapp.client.requests')
    def test_send_template(self, mock_requests):
        """Test send_template method."""
        client = WhatsAppClient(api_token='token', phone_number_id='phone-id')
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True}
        mock_requests.post.return_value = mock_response

        client.send_template(to='+123', template_name='welcome')

        call_args = mock_requests.post.call_args
        assert call_args[1]['json']['type'] == 'template'
        assert call_args[1]['json']['template']['name'] == 'welcome'
        assert call_args[1]['json']['template']['language']['code'] == 'ar'

    @patch('app.integrations.whatsapp.client.requests')
    def test_send_template_with_components(self, mock_requests):
        """Test send_template with components."""
        client = WhatsAppClient(api_token='token', phone_number_id='phone-id')
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True}
        mock_requests.post.return_value = mock_response

        components = [{'type': 'body', 'parameters': [{'type': 'text', 'text': 'test'}]}]
        client.send_template(to='+123', template_name='order', components=components)

        call_args = mock_requests.post.call_args
        assert call_args[1]['json']['template']['components'] == components

    @patch('app.integrations.whatsapp.client.requests')
    def test_send_template_custom_language(self, mock_requests):
        """Test send_template with custom language."""
        client = WhatsAppClient(api_token='token', phone_number_id='phone-id')
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True}
        mock_requests.post.return_value = mock_response

        client.send_template(to='+123', template_name='welcome', language_code='en')

        call_args = mock_requests.post.call_args
        assert call_args[1]['json']['template']['language']['code'] == 'en'

    @patch('app.integrations.whatsapp.client.requests')
    def test_send_document(self, mock_requests):
        """Test send_document method."""
        client = WhatsAppClient(api_token='token', phone_number_id='phone-id')
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True}
        mock_requests.post.return_value = mock_response

        client.send_document(
            to='+123', document_url='https://example.com/doc.pdf', caption='Invoice'
        )

        call_args = mock_requests.post.call_args
        assert call_args[1]['json']['type'] == 'document'
        assert call_args[1]['json']['document']['link'] == 'https://example.com/doc.pdf'
        assert call_args[1]['json']['document']['caption'] == 'Invoice'

    @patch('app.integrations.whatsapp.client.requests')
    def test_send_document_without_caption(self, mock_requests):
        """Test send_document without caption."""
        client = WhatsAppClient(api_token='token', phone_number_id='phone-id')
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True}
        mock_requests.post.return_value = mock_response

        client.send_document(to='+123', document_url='https://example.com/doc.pdf')

        call_args = mock_requests.post.call_args
        assert call_args[1]['json']['document']['caption'] == ''

    def test_base_url(self):
        """Test BASE_URL class attribute."""
        assert WhatsAppClient.BASE_URL == 'https://graph.facebook.com/v18.0'

    def test_service_importable_from_package(self):
        """Test service is importable from whatsapp package."""
        assert ServiceFromPackage is WhatsAppNotificationService


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
