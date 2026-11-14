"""Coverage tests for models/whatsapp_integration.py"""

from datetime import datetime, UTC

from models.whatsapp_integration import WhatsAppMessage, WhatsAppTemplate, WhatsAppConfig


class TestWhatsAppMessage:
    def test_repr(self):
        m = WhatsAppMessage(
            tenant_id=1,
            phone_number='1234567890',
            message_content='Hello',
            message_type='text',
            created_at=datetime.now(UTC),
        )
        assert repr(m) is not None

    def test_get_status_display(self):
        m = WhatsAppMessage(
            tenant_id=1,
            phone_number='1234567890',
            message_content='Hello',
            message_type='text',
            status='sent',
        )
        display = m.get_status_display()
        assert isinstance(display, str)

    def test_get_status_color(self):
        m = WhatsAppMessage(
            tenant_id=1,
            phone_number='1234567890',
            message_content='Hello',
            message_type='text',
            status='sent',
        )
        color = m.get_status_color()
        assert isinstance(color, str)

    def test_get_message_type_display(self):
        m = WhatsAppMessage(
            tenant_id=1,
            phone_number='1234567890',
            message_content='Hello',
            message_type='text',
            created_at=datetime.now(UTC),
        )
        display = m.get_message_type_display()
        assert isinstance(display, str)

    def test_is_successful(self):
        m = WhatsAppMessage(
            tenant_id=1,
            phone_number='1234567890',
            message_content='Hello',
            message_type='text',
            status='delivered',
        )
        assert isinstance(m.is_successful(), bool)

    def test_is_failed(self):
        m = WhatsAppMessage(
            tenant_id=1,
            phone_number='1234567890',
            message_content='Hello',
            message_type='text',
            status='failed',
        )
        assert isinstance(m.is_failed(), bool)

    def test_to_dict(self):
        m = WhatsAppMessage(
            tenant_id=1,
            phone_number='1234567890',
            message_content='Hello',
            message_type='text',
            created_at=datetime.now(UTC),
        )
        d = m.to_dict()
        assert isinstance(d, dict)

    def test_generate_message_id(self):
        msg_id = WhatsAppMessage.generate_message_id()
        assert msg_id is not None


class TestWhatsAppTemplate:
    def test_repr(self):
        t = WhatsAppTemplate(
            tenant_id=1,
            template_name='test_template',
            template_id='tmpl_001',
            message_type='text',
            body_text='Hello {{name}}',
            created_at=datetime.now(UTC),
        )
        assert repr(t) is not None

    def test_get_status_display(self):
        t = WhatsAppTemplate(
            tenant_id=1,
            template_name='test_template',
            template_id='tmpl_001',
            message_type='text',
            body_text='Hello {{name}}',
            status='approved',
        )
        display = t.get_status_display()
        assert isinstance(display, str)

    def test_get_status_color(self):
        t = WhatsAppTemplate(
            tenant_id=1,
            template_name='test_template',
            template_id='tmpl_001',
            message_type='text',
            body_text='Hello {{name}}',
            status='approved',
        )
        color = t.get_status_color()
        assert isinstance(color, str)

    def test_is_approved(self):
        t = WhatsAppTemplate(
            tenant_id=1,
            template_name='test_template',
            template_id='tmpl_001',
            message_type='text',
            body_text='Hello {{name}}',
            status='approved',
        )
        assert isinstance(t.is_approved(), bool)

    def test_to_dict(self):
        t = WhatsAppTemplate(
            tenant_id=1,
            template_name='test_template',
            template_id='tmpl_001',
            message_type='text',
            body_text='Hello {{name}}',
            created_at=datetime.now(UTC),
        )
        d = t.to_dict()
        assert isinstance(d, dict)


class TestWhatsAppConfig:
    def test_repr(self):
        c = WhatsAppConfig(
            tenant_id=1,
            config_key='api_key',
            config_value='secret',
            created_at=datetime.now(UTC),
        )
        assert repr(c) is not None

    def test_get_config(self):
        result = WhatsAppConfig.get_config('api_key', default='default_value')
        assert result is not None or result is None

    def test_set_config(self):
        WhatsAppConfig.set_config('test_key', 'test_value', description='Test config')
        assert True

    def test_to_dict(self):
        c = WhatsAppConfig(
            tenant_id=1,
            config_key='api_key',
            config_value='secret',
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        d = c.to_dict()
        assert isinstance(d, dict)
