"""
Tests for Workflow Services (visit, lab, radiology, pharmacy, billing)
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app, db
from app.modules.workflows.visit import VisitWorkflowService, VisitStatus
from app.modules.workflows.lab import LabWorkflowService, LabOrderStatus
from app.modules.workflows.radiology import RadiologyWorkflowService, RadiologyOrderStatus
from app.modules.workflows.pharmacy import PharmacyStockService
from app.modules.workflows.billing import _BillingServiceDeprecated as BillingService, InvoiceStatus
from app.modules.workflows.appointment import AppointmentService, AppointmentStatus
from models.visit import Visit
from models.patient import Patient
from models.user import User
from models.medication import Medication


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.rollback()
        db.session.remove()
        db.engine.dispose()
        db.session.rollback()
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            db.session.execute(db.text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE"))
        db.session.commit()


class TestVisitWorkflow:
    def test_valid_transitions(self, app):
        assert VisitWorkflowService.can_transition("registered", "waiting") is True
        assert VisitWorkflowService.can_transition("waiting", "in_progress") is True
        assert VisitWorkflowService.can_transition("in_progress", "completed") is True
        assert VisitWorkflowService.can_transition("completed", "archived") is True

    def test_invalid_transitions(self, app):
        assert VisitWorkflowService.can_transition("registered", "archived") is False
        assert VisitWorkflowService.can_transition("archived", "registered") is False
        assert VisitWorkflowService.can_transition("cancelled", "in_progress") is False

    def test_allowed_actions(self, app):
        actions = VisitWorkflowService.get_allowed_actions(type('V', (), {'status': 'registered'})())
        assert 'waiting' in actions
        assert 'in_progress' in actions
        assert 'cancelled' in actions
        assert 'archived' not in actions


class TestLabWorkflow:
    def test_lab_transitions(self, app):
        assert LabWorkflowService.can_transition("ordered", "sample_collected") is True
        assert LabWorkflowService.can_transition("sample_collected", "in_progress") is True
        assert LabWorkflowService.can_transition("in_progress", "results_entered") is True
        assert LabWorkflowService.can_transition("results_entered", "approved") is True

    def test_lab_invalid_transitions(self, app):
        assert LabWorkflowService.can_transition("ordered", "approved") is False
        assert LabWorkflowService.can_transition("approved", "sample_collected") is False


class TestRadiologyWorkflow:
    def test_radiology_transitions(self, app):
        assert RadiologyWorkflowService.can_transition("ordered", "scheduled") is True
        assert RadiologyWorkflowService.can_transition("in_progress", "images_captured") is True
        assert RadiologyWorkflowService.can_transition("reported", "approved") is True

    def test_radiology_invalid(self, app):
        assert RadiologyWorkflowService.can_transition("ordered", "delivered") is False


class TestPharmacyStock:
    def test_stock_adjustment(self, app):
        with app.app_context():
            user = User(username='pharm_user1', email='p1@test.com', full_name='Pharm User', role='pharmacy')
            user.set_password('p')
            db.session.add(user)
            db.session.commit()

            med = Medication(trade_name="Paracetamol", scientific_name="Paracetamol", dosage_form="tablet", strength="500mg", stock_quantity=50, price=10.0)
            db.session.add(med)
            db.session.commit()

            PharmacyStockService.adjust_stock(
                medication_id=med.id,
                quantity_change=20,
                movement_type="purchase",
                performed_by=user.id,
            )
            db.session.commit()

            assert med.stock_quantity == 70

    def test_stock_sale(self, app):
        with app.app_context():
            user = User(username='pharm_user2', email='p2@test.com', full_name='Pharm User', role='pharmacy')
            user.set_password('p')
            db.session.add(user)
            db.session.commit()

            med = Medication(trade_name="Ibuprofen", scientific_name="Ibuprofen", dosage_form="tablet", strength="400mg", stock_quantity=30, price=15.0)
            db.session.add(med)
            db.session.commit()

            PharmacyStockService.adjust_stock(
                medication_id=med.id,
                quantity_change=-5,
                movement_type="sale",
                performed_by=user.id,
            )
            db.session.commit()

            assert med.stock_quantity == 25

    def test_insufficient_stock_raises(self, app):
        with app.app_context():
            user = User(username='pharm_user3', email='p3@test.com', full_name='Pharm User', role='pharmacy')
            user.set_password('p')
            db.session.add(user)
            db.session.commit()

            med = Medication(trade_name="Aspirin", scientific_name="Aspirin", dosage_form="tablet", strength="100mg", stock_quantity=3, price=5.0)
            db.session.add(med)
            db.session.commit()

            with pytest.raises(ValueError):
                PharmacyStockService.adjust_stock(
                    medication_id=med.id,
                    quantity_change=-10,
                    movement_type="sale",
                    performed_by=user.id,
                )


class TestBillingService:
    def test_invoice_posting(self, app):
        with app.app_context():
            from models.invoice import Invoice
            inv = Invoice(status=InvoiceStatus.DRAFT, total_amount=100, paid_amount=0)
            BillingService.post_invoice(inv, 1)
            db.session.commit()
            assert inv.status == InvoiceStatus.POSTED
            assert inv.posted_at is not None

    def test_cannot_post_non_draft(self, app):
        with app.app_context():
            from models.invoice import Invoice
            inv = Invoice(status=InvoiceStatus.PAID, total_amount=100, paid_amount=0)
            db.session.add(inv)
            db.session.commit()
            with pytest.raises(ValueError):
                BillingService.post_invoice(inv, 1)


class TestAppointmentService:
    def test_double_booking_check(self, app):
        with app.app_context():
            from datetime import datetime, timezone
            start = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
            end = datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc)
            # No appointments exist yet
            assert AppointmentService.check_double_booking(1, start, end, exclude_id=None) is False

    def test_appointment_transitions(self, app):
        assert AppointmentService.can_transition("scheduled", "confirmed") is True
        assert AppointmentService.can_transition("confirmed", "checked_in") is True
        assert AppointmentService.can_transition("done", "cancelled") is False
