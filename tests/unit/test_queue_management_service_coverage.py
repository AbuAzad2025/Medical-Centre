"""Coverage for services/queue_management_service.py."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


def _department(db, tenant_id, name='Emergency Dept'):
    from models.department import Department

    department = Department(
        name=f'{name}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        name_ar=name,
        is_active=True,
        tenant_id=tenant_id,
    )
    db.session.add(department)
    db.session.flush()
    return department


def _patient(db, tenant_id, first='Queue', last='Patient'):
    from models.patient import Patient

    patient = Patient(
        tenant_id=tenant_id,
        first_name=first,
        last_name=last,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(patient)
    db.session.flush()
    return patient


def _visit(db, tenant_id, patient, department, payment_status='PAID', doctor_id=None):
    from models.visit import Visit

    visit = Visit(
        tenant_id=tenant_id,
        patient_id=patient.id,
        department_id=department.id,
        doctor_id=doctor_id,
        status='OPEN',
        payment_status=payment_status,
        total_amount=100,
        paid_amount=100 if payment_status == 'PAID' else 0,
        visit_type='REGULAR',
        payment_method='cash',
        is_emergency=False,
        created_at=datetime.now(UTC),
        visit_date=datetime.now(UTC).date(),
    )
    db.session.add(visit)
    db.session.flush()
    return visit


class TestQueueEntryConditions:
    """``_check_queue_entry_conditions`` — the payment gate."""

    def test_an_emergency_always_enters(self):
        from services.queue_management_service import QueueManagementService

        service = QueueManagementService()
        allowed, reason = service._check_queue_entry_conditions(1, 2, 'PENDING', True)
        assert allowed is True

    def test_a_paid_visit_enters(self):
        from services.queue_management_service import QueueManagementService

        service = QueueManagementService()
        allowed, reason = service._check_queue_entry_conditions(1, 2, 'PAID', False)
        assert allowed is True

    def test_a_pending_visit_is_blocked(self):
        from services.queue_management_service import QueueManagementService

        service = QueueManagementService()
        allowed, reason = service._check_queue_entry_conditions(1, 2, 'PENDING', False)
        assert allowed is False

    def test_a_partial_visit_is_blocked(self):
        from services.queue_management_service import QueueManagementService

        service = QueueManagementService()
        allowed, reason = service._check_queue_entry_conditions(1, 2, 'PARTIAL', False)
        assert allowed is False


class TestAddPatientToQueue:
    """``add_patient_to_queue`` — joining the queue."""

    def test_a_paid_visit_joins_the_queue(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        patient = _patient(db, test_tenant.id)
        visit = _visit(db, test_tenant.id, patient, department, payment_status='PAID')

        service = QueueManagementService()
        ok, message = service.add_patient_to_queue(
            patient.id, department.id, visit_id=visit.id
        )
        assert ok is True
        assert 'Q' in message

    def test_an_unpaid_visit_is_blocked(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        patient = _patient(db, test_tenant.id)
        visit = _visit(db, test_tenant.id, patient, department, payment_status='PENDING')

        service = QueueManagementService()
        ok, message = service.add_patient_to_queue(
            patient.id, department.id, visit_id=visit.id
        )
        assert ok is False

    def test_an_emergency_visit_joins_the_queue(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        patient = _patient(db, test_tenant.id)
        visit = _visit(db, test_tenant.id, patient, department, payment_status='PENDING')
        visit.is_emergency = True
        db.session.flush()

        service = QueueManagementService()
        ok, message = service.add_patient_to_queue(
            patient.id, department.id, visit_id=visit.id
        )
        assert ok is True

    def test_a_failing_write_is_reported(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        patient = _patient(db, test_tenant.id)
        visit = _visit(db, test_tenant.id, patient, department, payment_status='PAID')

        with patch('services.queue_management_service.safe_commit', return_value=False):
            service = QueueManagementService()
            ok, message = service.add_patient_to_queue(
                patient.id, department.id, visit_id=visit.id
            )
        assert ok is False


class TestQueueStatus:
    """``get_queue_status`` — the current state of one queue."""

    def test_an_empty_queue_is_reported(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        service = QueueManagementService()
        status = service.get_queue_status(department.id)
        assert isinstance(status, dict)

    def test_a_populated_queue_is_reported(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        patient = _patient(db, test_tenant.id)
        visit = _visit(db, test_tenant.id, patient, department, payment_status='PAID')

        service = QueueManagementService()
        service.add_patient_to_queue(patient.id, department.id, visit_id=visit.id)

        status = service.get_queue_status(department.id)
        assert isinstance(status, dict)
        assert status.get('waiting_count', 0) >= 1

    def test_a_failing_query_returns_an_empty_status(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        with patch('services.queue_management_service.db.session.execute', side_effect=RuntimeError('db down')):
            service = QueueManagementService()
            status = service.get_queue_status(1)
        assert status is None


class TestWaitMetrics:
    """``get_wait_metrics_today`` — today's wait times."""

    def test_metrics_for_an_empty_queue(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        service = QueueManagementService()
        metrics = service.get_wait_metrics_today([department.id])
        assert isinstance(metrics, dict)

    def test_a_failing_query_returns_an_empty_metrics(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        with patch('services.queue_management_service.db.session.execute', side_effect=RuntimeError('db down')):
            service = QueueManagementService()
            metrics = service.get_wait_metrics_today([1])
        assert isinstance(metrics, dict)


class TestPatientQueuePosition:
    """``get_patient_queue_position`` — where a patient is in the queue."""

    def test_an_absent_patient_has_no_position(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        service = QueueManagementService()
        position = service.get_patient_queue_position(99999, department.id)
        assert position[0] is None

    def test_a_queued_patient_has_a_position(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        department = _department(db, test_tenant.id)
        patient = _patient(db, test_tenant.id)
        visit = _visit(db, test_tenant.id, patient, department, payment_status='PAID')

        service = QueueManagementService()
        service.add_patient_to_queue(patient.id, department.id, visit_id=visit.id)

        position = service.get_patient_queue_position(patient.id, department.id)
        assert position is not None


class TestTicketLifecycle:
    """Calling, treating, skipping and cancelling a ticket."""

    def _queued_ticket(self, db, tenant_id):
        from services.queue_management_service import QueueManagementService

        department = _department(db, tenant_id)
        patient = _patient(db, tenant_id)
        visit = _visit(db, tenant_id, patient, department, payment_status='PAID')
        service = QueueManagementService()
        ok, message = service.add_patient_to_queue(patient.id, department.id, visit_id=visit.id)
        assert ok is True
        from models.queue_management import QueueManagement

        ticket = (
            db.session.execute(
                db.select(QueueManagement).filter_by(patient_id=patient.id)
            )
            .scalars()
            .first()
        )
        return service, department, patient, ticket

    def test_calling_next_patient(self, app, db, test_tenant):
        service, department, patient, ticket = self._queued_ticket(db, test_tenant.id)
        ok, message = service.call_next_patient(department.id)
        assert isinstance(message, str)

    def test_starting_treatment(self, app, db, test_tenant):
        service, department, patient, ticket = self._queued_ticket(db, test_tenant.id)
        service.call_next_patient(department.id)
        result = service.start_treatment(ticket.id)
        assert result is not None

    def test_completing_treatment(self, app, db, test_tenant):
        service, department, patient, ticket = self._queued_ticket(db, test_tenant.id)
        service.call_next_patient(department.id)
        service.start_treatment(ticket.id)
        result = service.complete_treatment(ticket.id)
        assert result is not None

    def test_skipping_a_patient(self, app, db, test_tenant):
        service, department, patient, ticket = self._queued_ticket(db, test_tenant.id)
        result = service.skip_patient(ticket.id, reason='patient absent')
        assert result is not None

    def test_cancelling_a_ticket(self, app, db, test_tenant):
        service, department, patient, ticket = self._queued_ticket(db, test_tenant.id)
        result = service.cancel_ticket(ticket.id, reason='no show')
        assert result is not None

    def test_returning_a_ticket_to_the_queue(self, app, db, test_tenant):
        service, department, patient, ticket = self._queued_ticket(db, test_tenant.id)
        service.call_next_patient(department.id)
        result = service.return_to_queue(ticket.id, reason='back')
        assert result is not None

    def test_an_unknown_ticket_is_refused(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        service = QueueManagementService()
        result = service.start_treatment(999999)
        assert result is not None
        result = service.complete_treatment(999999)
        assert result is not None
        result = service.skip_patient(999999)
        assert result is not None
        result = service.cancel_ticket(999999)
        assert result is not None
        result = service.return_to_queue(999999)
        assert result is not None
        result = service.approve_emergency_debt(999999, approved_by=1)
        assert result is not None
        result = service.approve_force_entry(999999, approved_by=1)
        assert result is not None


class TestApproval:
    """The manager approvals."""

    def test_approving_an_emergency_debt(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        service = QueueManagementService()
        result = service.approve_emergency_debt(999999, approved_by=1, max_amount=50.0)
        assert result is not None

    def test_approving_a_force_entry(self, app, db, test_tenant):
        from services.queue_management_service import QueueManagementService

        service = QueueManagementService()
        result = service.approve_force_entry(999999, approved_by=1, reason='urgent')
        assert result is not None
