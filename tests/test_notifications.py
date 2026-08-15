"""Tests for app.core.notifications module.

Covers the NotificationDispatcher class.
"""

import pytest
from unittest.mock import MagicMock

from app.core.notifications import NotificationDispatcher, logger


@pytest.fixture
def mock_whatsapp(monkeypatch):
    """Mock WhatsAppNotificationService to avoid env dependencies."""
    mock_service = MagicMock()
    monkeypatch.setattr(
        'app.core.notifications.WhatsAppNotificationService',
        lambda: mock_service,
    )
    return mock_service


class TestNotificationDispatcherInit:
    """Tests for NotificationDispatcher.__init__."""

    def test_default_initialization(self, mock_whatsapp):
        """Test default initialization without tenant."""
        dispatcher = NotificationDispatcher()
        assert dispatcher.tenant is None
        assert dispatcher.whatsapp is mock_whatsapp

    def test_initialization_with_tenant(self, mock_whatsapp):
        """Test initialization with a tenant."""
        mock_tenant = MagicMock()
        dispatcher = NotificationDispatcher(tenant=mock_tenant)
        assert dispatcher.tenant is mock_tenant
        assert dispatcher.whatsapp is mock_whatsapp


class TestShouldSend:
    """Tests for _should_send method."""

    def test_returns_true_when_no_tenant(self, mock_whatsapp):
        """Test that it returns True when tenant is None."""
        dispatcher = NotificationDispatcher(tenant=None)
        assert dispatcher._should_send('whatsapp') is True
        assert dispatcher._should_send('email') is True
        assert dispatcher._should_send('sms') is True

    def test_returns_true_when_tenant_exists(self, mock_whatsapp):
        """Test that it returns True when tenant exists (TODO: read preferences)."""
        mock_tenant = MagicMock()
        dispatcher = NotificationDispatcher(tenant=mock_tenant)
        assert dispatcher._should_send('whatsapp') is True


class TestNotifyAppointmentConfirmed:
    """Tests for notify_appointment_confirmed method."""

    def test_calls_whatsapp_send_reminder(self, mock_whatsapp):
        """Test that WhatsApp appointment reminder is sent."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_appointment_reminder = MagicMock()

        dispatcher.notify_appointment_confirmed(
            phone='+123456789',
            patient_name='John Doe',
            date_str='2024-01-15',
            time_str='10:30',
            doctor_name='Dr. Smith',
        )

        mock_whatsapp.send_appointment_reminder.assert_called_once_with(
            '+123456789', 'John Doe', '2024-01-15', '10:30', 'Dr. Smith'
        )

    def test_handles_whatsapp_failure(self, mock_whatsapp):
        """Test that WhatsApp failure is caught and logged."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_appointment_reminder = MagicMock(
            side_effect=Exception('API error')
        )

        # Should not raise
        dispatcher.notify_appointment_confirmed(
            phone='+123456789',
            patient_name='John Doe',
            date_str='2024-01-15',
            time_str='10:30',
            doctor_name='Dr. Smith',
        )


class TestNotifyLabResultsReady:
    """Tests for notify_lab_results_ready method."""

    def test_calls_whatsapp_send_results(self, mock_whatsapp):
        """Test that WhatsApp lab results ready is sent."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_lab_results_ready = MagicMock()

        dispatcher.notify_lab_results_ready(
            phone='+123456789',
            patient_name='Jane Doe',
            visit_number='V123',
            login_link='https://example.com/login',
        )

        mock_whatsapp.send_lab_results_ready.assert_called_once_with(
            '+123456789', 'Jane Doe', 'V123', 'https://example.com/login'
        )

    def test_handles_none_login_link(self, mock_whatsapp):
        """Test with None login link."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_lab_results_ready = MagicMock()

        dispatcher.notify_lab_results_ready(
            phone='+123456789',
            patient_name='Jane Doe',
            visit_number='V123',
        )

        mock_whatsapp.send_lab_results_ready.assert_called_once_with('+123456789', 'Jane Doe', 'V123', None)

    def test_handles_whatsapp_failure(self, mock_whatsapp):
        """Test that WhatsApp failure is caught and logged."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_lab_results_ready = MagicMock(
            side_effect=Exception('API error')
        )

        # Should not raise
        dispatcher.notify_lab_results_ready(
            phone='+123456789',
            patient_name='Jane Doe',
            visit_number='V123',
        )


class TestNotifyInvoiceGenerated:
    """Tests for notify_invoice_generated method."""

    def test_calls_whatsapp_send_invoice(self, mock_whatsapp):
        """Test that WhatsApp invoice is sent."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_invoice = MagicMock()

        dispatcher.notify_invoice_generated(
            phone='+123456789',
            patient_name='John Doe',
            amount='150.00',
            receipt_link='https://example.com/receipt/123',
        )

        mock_whatsapp.send_invoice.assert_called_once_with(
            '+123456789', 'John Doe', '150.00', 'https://example.com/receipt/123'
        )

    def test_handles_none_receipt_link(self, mock_whatsapp):
        """Test with None receipt link."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_invoice = MagicMock()

        dispatcher.notify_invoice_generated(
            phone='+123456789',
            patient_name='John Doe',
            amount='150.00',
        )

        mock_whatsapp.send_invoice.assert_called_once_with('+123456789', 'John Doe', '150.00', None)

    def test_handles_whatsapp_failure(self, mock_whatsapp):
        """Test that WhatsApp failure is caught and logged."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_invoice = MagicMock(
            side_effect=Exception('API error')
        )

        # Should not raise
        dispatcher.notify_invoice_generated(
            phone='+123456789',
            patient_name='John Doe',
            amount='150.00',
        )


class TestNotifyMedicationDispensed:
    """Tests for notify_medication_dispensed method."""

    def test_calls_whatsapp_send_medication_reminder(self, mock_whatsapp):
        """Test that WhatsApp medication reminder is sent."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_medication_reminder = MagicMock()

        dispatcher.notify_medication_dispensed(
            phone='+123456789',
            patient_name='John Doe',
            medication_name='Aspirin',
            dosage='100mg',
        )

        mock_whatsapp.send_medication_reminder.assert_called_once_with(
            '+123456789', 'John Doe', 'Aspirin', '100mg'
        )

    def test_handles_whatsapp_failure(self, mock_whatsapp):
        """Test that WhatsApp failure is caught and logged."""
        dispatcher = NotificationDispatcher()
        mock_whatsapp.send_medication_reminder = MagicMock(
            side_effect=Exception('API error')
        )

        # Should not raise
        dispatcher.notify_medication_dispensed(
            phone='+123456789',
            patient_name='John Doe',
            medication_name='Aspirin',
            dosage='100mg',
        )


class TestLogger:
    """Tests for module-level logger."""

    def test_logger_exists(self):
        """Test that module-level logger exists."""
        assert logger is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
