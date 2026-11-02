"""Tests for app.modules.workflows.notifications_integration module - 100% coverage target."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.modules.workflows.notifications_integration import (
    notify_on_visit_status_change,
    notify_on_lab_approved,
    notify_on_invoice_posted,
    notify_on_prescription_dispensed,
)


class TestNotifyOnVisitStatusChange:
    """Tests for notify_on_visit_status_change function."""

    def test_notify_on_visit_status_change_completed(self):
        """Test notification when visit status changes to completed."""
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = 'John Doe'
        mock_visit.patient = mock_patient
        mock_visit.visit_number = 'VN12345'

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_visit_status_change(mock_visit, 'in_progress', 'completed')

            mock_dispatcher_class.assert_called_once_with(None)
            mock_dispatcher.notify_lab_results_ready.assert_called_once_with(
                phone='1234567890',
                patient_name='John Doe',
                visit_number='VN12345',
            )

    def test_notify_on_visit_status_change_not_completed(self):
        """Test no notification when status is not completed."""
        mock_visit = MagicMock()

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_visit_status_change(mock_visit, 'in_progress', 'cancelled')
            notify_on_visit_status_change(mock_visit, 'pending', 'in_progress')

            # Dispatcher is created but notify_lab_results_ready should not be called
            mock_dispatcher.notify_lab_results_ready.assert_not_called()

    def test_notify_on_visit_status_change_no_patient(self):
        """Test no notification when visit has no patient."""
        mock_visit = MagicMock()
        mock_visit.patient = None

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_visit_status_change(mock_visit, 'in_progress', 'completed')

            mock_dispatcher.notify_lab_results_ready.assert_not_called()

    def test_notify_on_visit_status_change_patient_no_phone(self):
        """Test no notification when patient has no phone."""
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = None
        mock_patient.full_name = 'John Doe'
        mock_visit.patient = mock_patient

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_visit_status_change(mock_visit, 'in_progress', 'completed')

            mock_dispatcher.notify_lab_results_ready.assert_not_called()

    def test_notify_on_visit_status_change_with_tenant(self):
        """Test notification with tenant parameter."""
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = 'John Doe'
        mock_visit.patient = mock_patient
        mock_visit.visit_number = 'VN12345'
        mock_tenant = MagicMock()

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_visit_status_change(mock_visit, 'in_progress', 'completed', tenant=mock_tenant)

            mock_dispatcher_class.assert_called_once_with(mock_tenant)
            mock_dispatcher.notify_lab_results_ready.assert_called_once_with(
                phone='1234567890',
                patient_name='John Doe',
                visit_number='VN12345',
            )


class TestNotifyOnLabApproved:
    """Tests for notify_on_lab_approved function."""

    def test_notify_on_lab_approved_with_patient(self):
        """Test notification when lab order is approved and patient has phone."""
        mock_lab_order = MagicMock()
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = 'John Doe'
        mock_visit.patient = mock_patient
        mock_visit.visit_number = 'VN12345'
        mock_lab_order.visit = mock_visit

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_lab_approved(mock_lab_order)

            mock_dispatcher_class.assert_called_once_with(None)
            mock_dispatcher.notify_lab_results_ready.assert_called_once_with(
                phone='1234567890',
                patient_name='John Doe',
                visit_number='VN12345',
            )

    def test_notify_on_lab_approved_with_tenant(self):
        """Test notification with tenant parameter."""
        mock_lab_order = MagicMock()
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = 'John Doe'
        mock_visit.patient = mock_patient
        mock_visit.visit_number = 'VN12345'
        mock_lab_order.visit = mock_visit
        mock_tenant = MagicMock()

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_lab_approved(mock_lab_order, tenant=mock_tenant)

            mock_dispatcher_class.assert_called_once_with(mock_tenant)

    def test_notify_on_lab_approved_no_visit(self):
        """Test no notification when lab_order has no visit."""
        mock_lab_order = MagicMock()
        mock_lab_order.visit = None

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_lab_approved(mock_lab_order)

            mock_dispatcher.notify_lab_results_ready.assert_not_called()

    def test_notify_on_lab_approved_no_patient(self):
        """Test no notification when visit has no patient."""
        mock_lab_order = MagicMock()
        mock_visit = MagicMock()
        mock_visit.patient = None
        mock_lab_order.visit = mock_visit

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_lab_approved(mock_lab_order)

            mock_dispatcher.notify_lab_results_ready.assert_not_called()

    def test_notify_on_lab_approved_patient_no_phone(self):
        """Test no notification when patient has no phone."""
        mock_lab_order = MagicMock()
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = None
        mock_visit.patient = mock_patient
        mock_lab_order.visit = mock_visit

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_lab_approved(mock_lab_order)

            mock_dispatcher.notify_lab_results_ready.assert_not_called()


class TestNotifyOnInvoicePosted:
    """Tests for notify_on_invoice_posted function."""

    def test_notify_on_invoice_posted_with_patient(self):
        """Test notification when invoice is posted and patient has phone."""
        mock_invoice = MagicMock()
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = 'John Doe'
        mock_visit.patient = mock_patient
        mock_invoice.visit = mock_visit
        mock_invoice.total_amount = 1000.50

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_invoice_posted(mock_invoice)

            mock_dispatcher_class.assert_called_once_with(None)
            mock_dispatcher.notify_invoice_generated.assert_called_once_with(
                phone='1234567890',
                patient_name='John Doe',
                amount='1000.5',
            )

    def test_notify_on_invoice_posted_with_tenant(self):
        """Test notification with tenant parameter."""
        mock_invoice = MagicMock()
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = 'John Doe'
        mock_visit.patient = mock_patient
        mock_invoice.visit = mock_visit
        mock_invoice.total_amount = 500.0
        mock_tenant = MagicMock()

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_invoice_posted(mock_invoice, tenant=mock_tenant)

            mock_dispatcher_class.assert_called_once_with(mock_tenant)

    def test_notify_on_invoice_posted_no_visit(self):
        """Test no notification when invoice has no visit."""
        mock_invoice = MagicMock()
        mock_invoice.visit = None

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_invoice_posted(mock_invoice)

            mock_dispatcher.notify_invoice_generated.assert_not_called()

    def test_notify_on_invoice_posted_no_patient(self):
        """Test no notification when visit has no patient."""
        mock_invoice = MagicMock()
        mock_visit = MagicMock()
        mock_visit.patient = None
        mock_invoice.visit = mock_visit

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_invoice_posted(mock_invoice)

            mock_dispatcher.notify_invoice_generated.assert_not_called()

    def test_notify_on_invoice_posted_patient_no_phone(self):
        """Test no notification when patient has no phone."""
        mock_invoice = MagicMock()
        mock_visit = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = None
        mock_visit.patient = mock_patient
        mock_invoice.visit = mock_visit

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_invoice_posted(mock_invoice)

            mock_dispatcher.notify_invoice_generated.assert_not_called()


class TestNotifyOnPrescriptionDispensed:
    """Tests for notify_on_prescription_dispensed function."""

    def test_notify_on_prescription_dispensed_with_patient(self):
        """Test notification when prescription is dispensed and patient has phone."""
        mock_prescription = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = 'John Doe'
        mock_prescription.patient = mock_patient
        mock_item = MagicMock()
        mock_medication = MagicMock()
        mock_medication.trade_name = 'Paracetamol'
        mock_item.medication = mock_medication
        mock_item.dosage = '500mg'
        mock_prescription.items = [mock_item]

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_prescription_dispensed(mock_prescription)

            mock_dispatcher_class.assert_called_once_with(None)
            mock_dispatcher.notify_medication_dispensed.assert_called_once_with(
                phone='1234567890',
                patient_name='John Doe',
                medication_name='Paracetamol',
                dosage='500mg',
            )

    def test_notify_on_prescription_dispensed_with_tenant(self):
        """Test notification with tenant parameter."""
        mock_prescription = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = 'John Doe'
        mock_prescription.patient = mock_patient
        mock_item = MagicMock()
        mock_medication = MagicMock()
        mock_medication.trade_name = 'Paracetamol'
        mock_item.medication = mock_medication
        mock_item.dosage = '500mg'
        mock_prescription.items = [mock_item]
        mock_tenant = MagicMock()

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_prescription_dispensed(mock_prescription, tenant=mock_tenant)

            mock_dispatcher_class.assert_called_once_with(mock_tenant)

    def test_notify_on_prescription_dispensed_no_patient(self):
        """Test no notification when prescription has no patient."""
        mock_prescription = MagicMock()
        mock_prescription.patient = None

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_prescription_dispensed(mock_prescription)

            mock_dispatcher.notify_medication_dispensed.assert_not_called()

    def test_notify_on_prescription_dispensed_patient_no_phone(self):
        """Test no notification when patient has no phone."""
        mock_prescription = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = None
        mock_prescription.patient = mock_patient

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_prescription_dispensed(mock_prescription)

            mock_dispatcher.notify_medication_dispensed.assert_not_called()

    def test_notify_on_prescription_dispensed_no_items(self):
        """Test no notification when prescription has no items."""
        mock_prescription = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_prescription.patient = mock_patient
        mock_prescription.items = []

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_prescription_dispensed(mock_prescription)

            mock_dispatcher.notify_medication_dispensed.assert_not_called()

    def test_notify_on_prescription_dispensed_no_medication(self):
        """Test notification when item has no medication - still sends with empty name."""
        mock_prescription = MagicMock()
        mock_patient = MagicMock()
        mock_patient.phone = '1234567890'
        mock_patient.full_name = ''
        mock_prescription.patient = mock_patient
        mock_item = MagicMock()
        mock_item.medication = None
        mock_item.dosage = '500mg'
        mock_prescription.items = [mock_item]

        with patch('app.modules.workflows.notifications_integration.NotificationDispatcher') as mock_dispatcher_class:
            mock_dispatcher = MagicMock()
            mock_dispatcher_class.return_value = mock_dispatcher

            notify_on_prescription_dispensed(mock_prescription)

            # Function still calls notify with empty medication name
            mock_dispatcher.notify_medication_dispensed.assert_called_once_with(
                phone='1234567890',
                patient_name='',
                medication_name='',
                dosage='500mg',
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])