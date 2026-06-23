"""Tests for P0C-001 / P0C-003: background job tenant contract."""

import uuid
from unittest.mock import MagicMock

import pytest


def _unique_slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestTenantJobRunner:
    """Tenant-aware job runner must isolate tenants."""

    def test_for_each_tenant_calls_job_per_active_tenant(self, app):
        from services.tenant_job_runner import for_each_tenant
        from app.core.tenant.models import Tenant, TenantStatus
        from app.extensions import db

        with app.app_context():
            # Ensure at least two active tenants exist using unique slugs
            t1 = Tenant(slug=_unique_slug('tenant-a'), name='Tenant A', contact_email='a@example.com', status=TenantStatus.ACTIVE)
            t2 = Tenant(slug=_unique_slug('tenant-b'), name='Tenant B', contact_email='b@example.com', status=TenantStatus.ACTIVE)
            db.session.add_all([t1, t2])
            db.session.commit()

            job = MagicMock()
            for_each_tenant(app, job)

            called_ids = {call.args[0] for call in job.call_args_list}
            assert t1.id in called_ids
            assert t2.id in called_ids

    def test_for_each_tenant_skips_inactive_tenants(self, app):
        from services.tenant_job_runner import for_each_tenant
        from app.core.tenant.models import Tenant, TenantStatus
        from app.extensions import db

        with app.app_context():
            active = Tenant(slug=_unique_slug('active-tenant'), name='Active', contact_email='active@example.com', status=TenantStatus.ACTIVE)
            inactive = Tenant(slug=_unique_slug('inactive-tenant'), name='Inactive', contact_email='inactive@example.com', status=TenantStatus.SUSPENDED)
            db.session.add_all([active, inactive])
            db.session.commit()

            job = MagicMock()
            for_each_tenant(app, job)

            called_ids = {call.args[0] for call in job.call_args_list}
            assert active.id in called_ids
            assert inactive.id not in called_ids


class TestNotificationQueueTenantIsolation:
    """Notification queue processing must be scoped to a single tenant."""

    def test_process_notification_queue_filters_by_tenant(self, app):
        from services.notification_service import NotificationService
        from models.notification import NotificationQueue
        from models.user import User
        from app.core.tenant.models import Tenant
        from app.shared.enums import NotificationState
        from app.extensions import db

        with app.app_context():
            # Create real tenants and a dummy user; production DB has FK and
            # NOT NULL constraints that the ORM model doesn't reflect.
            t1 = Tenant(slug=_unique_slug('notif-t1'), name='Notif T1', contact_email='t1@example.com', status='ACTIVE')
            t2 = Tenant(slug=_unique_slug('notif-t2'), name='Notif T2', contact_email='t2@example.com', status='ACTIVE')
            db.session.add_all([t1, t2])
            db.session.commit()

            user = User(username='notif-dummy', email='notif@example.com', role='admin', password_hash='fakehash', full_name='Notif Dummy')
            db.session.add(user)
            db.session.commit()

            n1 = NotificationQueue(tenant_id=t1.id, user_id=user.id, notification_type='email', recipient='a@example.com', content='A', status=NotificationState.PENDING)
            n2 = NotificationQueue(tenant_id=t2.id, user_id=user.id, notification_type='email', recipient='b@example.com', content='B', status=NotificationState.PENDING)
            db.session.add_all([n1, n2])
            db.session.commit()

            # Suppress actual email sending by mocking the helper
            NotificationService.send_email_message = MagicMock(return_value={'success': True})

            result = NotificationService.process_notification_queue(tenant_id=t1.id)
            assert result['success'] is True

            # Only tenant 1 notification should be processed
            assert NotificationQueue.query.get(n1.id).status == NotificationState.SENT
            assert NotificationQueue.query.get(n2.id).status == NotificationState.PENDING


class TestAppointmentRemindersTenantIsolation:
    """Appointment reminder worker must be scoped to a single tenant."""

    def test_send_appointment_reminders_filters_by_tenant(self, app):
        from services.notification_service import NotificationService
        from models.appointment import Appointment
        from models.patient import Patient
        from models.user import User
        from app.core.tenant.models import Tenant
        from app.shared.enums import AppointmentState
        from app.extensions import db
        from datetime import datetime, timedelta

        with app.app_context():
            now = datetime.now()
            soon = now + timedelta(hours=12)

            # Create real tenants so the service can resolve the tenant context
            t1 = Tenant(slug=_unique_slug('appt-t1'), name='Appt T1', contact_email='t1@example.com', status='ACTIVE')
            t2 = Tenant(slug=_unique_slug('appt-t2'), name='Appt T2', contact_email='t2@example.com', status='ACTIVE')
            db.session.add_all([t1, t2])
            db.session.commit()

            patient1 = Patient(tenant_id=t1.id, first_name='P1', last_name='Test', phone='0500000001')
            patient2 = Patient(tenant_id=t2.id, first_name='P2', last_name='Test', phone='0500000002')
            doctor = User(username='doc', email='doc@example.com', role='doctor', password_hash='fakehash', full_name='Dr. Test', tenant_id=t1.id)
            db.session.add_all([patient1, patient2, doctor])
            db.session.commit()

            a1 = Appointment(tenant_id=t1.id, patient_id=patient1.id, doctor_id=doctor.id, status=AppointmentState.SCHEDULED, starts_at=soon)
            a2 = Appointment(tenant_id=t2.id, patient_id=patient2.id, doctor_id=doctor.id, status=AppointmentState.SCHEDULED, starts_at=soon)
            db.session.add_all([a1, a2])
            db.session.commit()

            NotificationService.add_to_notification_queue = MagicMock()

            result = NotificationService.send_appointment_reminders(tenant_id=t1.id)
            assert result['success'] is True
            assert result['sent'] == 1

            called_tenant_ids = {call.kwargs.get('tenant_id') for call in NotificationService.add_to_notification_queue.call_args_list}
            assert t2.id not in called_tenant_ids
