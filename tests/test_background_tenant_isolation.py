"""Tests for P0C-001 / P0C-003: background job tenant contract."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.extensions import db


def _unique_slug(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


class TestTenantJobRunner:
    """Tenant-aware job runner must isolate tenants."""

    def test_for_each_tenant_calls_job_per_active_tenant(self, app):
        from app.core.tenant.models import Tenant, TenantStatus
        from services.tenant_job_runner import for_each_tenant

        with app.app_context():
            # Ensure at least two active tenants exist using unique slugs
            t1 = Tenant(
                slug=_unique_slug('tenant-a'),
                name='Tenant A',
                contact_email='a@example.com',
                status=TenantStatus.ACTIVE,
            )
            t2 = Tenant(
                slug=_unique_slug('tenant-b'),
                name='Tenant B',
                contact_email='b@example.com',
                status=TenantStatus.ACTIVE,
            )
            db.session.add_all([t1, t2])
            db.session.commit()

            job = MagicMock()
            for_each_tenant(app, job)

            called_ids = {call.args[0] for call in job.call_args_list}
            assert t1.id in called_ids
            assert t2.id in called_ids

    def test_for_each_tenant_skips_inactive_tenants(self, app):
        from app.core.tenant.models import Tenant, TenantStatus
        from services.tenant_job_runner import for_each_tenant

        with app.app_context():
            active = Tenant(
                slug=_unique_slug('active-tenant'),
                name='Active',
                contact_email='active@example.com',
                status=TenantStatus.ACTIVE,
            )
            inactive = Tenant(
                slug=_unique_slug('inactive-tenant'),
                name='Inactive',
                contact_email='inactive@example.com',
                status=TenantStatus.SUSPENDED,
            )
            db.session.add_all([active, inactive])
            db.session.commit()

            job = MagicMock()
            for_each_tenant(app, job)

            called_ids = {call.args[0] for call in job.call_args_list}
            assert active.id in called_ids
            assert inactive.id not in called_ids

    def test_with_tenant_context_binds_tenant_id(self, app):
        from flask import g

        from app.core.tenant.models import Tenant, TenantStatus
        from services.tenant_job_runner import with_tenant_context

        with app.app_context():
            tenant = Tenant(
                slug=_unique_slug('bind-ctx'),
                name='Bind Ctx',
                contact_email='bind@example.com',
                status=TenantStatus.ACTIVE,
            )
            db.session.add(tenant)
            db.session.commit()

            captured = {}
            with_tenant_context(
                app, tenant.id, lambda: captured.update(tenant_id=g.get('tenant_id'))
            )
            assert captured['tenant_id'] == tenant.id


@pytest.mark.no_tenant_context
class TestNotificationQueueTenantIsolation:
    """Notification queue processing must be scoped to a single tenant."""

    def test_process_notification_queue_filters_by_tenant(self, app, rollback_db, monkeypatch):
        from app.core.tenant.models import Tenant
        from app.shared.enums import NotificationState
        from models.notification import NotificationQueue
        from models.user import User
        from services.notification_service import NotificationService

        with app.app_context(), app.test_request_context():
            from flask import g

            g._tenant_filter_bypass = True
            # Create real tenants; production DB has FK and NOT NULL constraints
            # that the ORM model doesn't reflect.
            t1 = Tenant(
                slug=_unique_slug('notif-t1'),
                name='Notif T1',
                contact_email='t1@example.com',
                status='ACTIVE',
            )
            t2 = Tenant(
                slug=_unique_slug('notif-t2'),
                name='Notif T2',
                contact_email='t2@example.com',
                status='ACTIVE',
            )
            db.session.add_all([t1, t2])
            db.session.commit()

            from tests.tenant_context import tenant_test_context

            with tenant_test_context(app, t1):
                user = User(
                    username='notif-dummy',
                    email='notif@example.com',
                    role='admin',
                    password_hash='fakehash',
                    full_name='Notif Dummy',
                    tenant_id=t1.id,
                )
                db.session.add(user)
                db.session.commit()
                user_id = user.id

            # `g._tenant_filter_bypass` silences the ORM filter but never
            # reaches PostgreSQL, and `notification_queue` has a WITH CHECK
            # policy. Two tenants' rows in one INSERT cannot satisfy it, so each
            # is written inside its own tenant's scope. The id is captured there
            # too, for the reason given in the reminders test below.
            with tenant_test_context(app, t1):
                n1 = NotificationQueue(
                    tenant_id=t1.id,
                    user_id=user_id,
                    notification_type='email',
                    recipient='a@example.com',
                    content='A',
                    status=NotificationState.PENDING,
                )
                db.session.add(n1)
                db.session.commit()
                n1_id = n1.id

            with tenant_test_context(app, t2):
                n2 = NotificationQueue(
                    tenant_id=t2.id,
                    user_id=user_id,
                    notification_type='email',
                    recipient='b@example.com',
                    content='B',
                    status=NotificationState.PENDING,
                )
                db.session.add(n2)
                db.session.commit()
                n2_id = n2.id

            # Suppress actual email sending; monkeypatch restores after test.
            monkeypatch.setattr(
                NotificationService,
                'send_email_message',
                MagicMock(return_value={'success': True}),
            )

            result = None
            # A real worker for tenant t1 runs inside tenant t1's scope
            # (`tenant_task` / `for_each_tenant` both bind it). The service
            # filters explicitly on tenant_id, but the ORM auto-filter still
            # narrows by the ambient tenant on top of that, so calling it while
            # some other tenant is bound finds nothing. Fail-closed, not a bug.
            with tenant_test_context(app, t1):
                result = NotificationService.process_notification_queue(tenant_id=t1.id)
                assert result['success'] is True

                # Only tenant 1 notification should be processed. Each read runs
                # in the scope that owns the row.
                assert db.session.get(NotificationQueue, n1_id).status == NotificationState.SENT
            with tenant_test_context(app, t2):
                assert db.session.get(NotificationQueue, n2_id).status == NotificationState.PENDING


@pytest.mark.no_tenant_context
class TestAppointmentRemindersTenantIsolation:
    """Appointment reminder worker must be scoped to a single tenant."""

    def test_send_appointment_reminders_filters_by_tenant(self, app, rollback_db, monkeypatch):
        from datetime import datetime, timedelta

        from app.core.tenant.models import Tenant
        from app.shared.enums import AppointmentState
        from models.appointment import Appointment
        from models.patient import Patient
        from models.user import User
        from services.notification_service import NotificationService

        with app.app_context(), app.test_request_context():
            from flask import g

            g._tenant_filter_bypass = True
            now = datetime.now()
            soon = now + timedelta(hours=12)

            # Create real tenants so the service can resolve the tenant context
            t1 = Tenant(
                slug=_unique_slug('appt-t1'),
                name='Appt T1',
                contact_email='t1@example.com',
                status='ACTIVE',
            )
            t2 = Tenant(
                slug=_unique_slug('appt-t2'),
                name='Appt T2',
                contact_email='t2@example.com',
                status='ACTIVE',
            )
            db.session.add_all([t1, t2])
            db.session.commit()

            # `g._tenant_filter_bypass` only silences the ORM filter; it never
            # reaches PostgreSQL. Patients, appointments and users all carry a
            # WITH CHECK policy, so tenant B's rows must be written while tenant
            # B is bound - otherwise one multi-row INSERT naming two different
            # tenant_ids is rejected outright, which is what
            # `InsufficientPrivilege ... table "patients"` was.
            #
            # Ids are captured inside the scope that made the row visible,
            # because afterwards the ORM filter re-asserts the other tenant and
            # an attribute read raises ObjectDeletedError on a row that exists.
            from tests.tenant_context import tenant_test_context

            with tenant_test_context(app, t1):
                doctor = User(
                    username='doc',
                    email='doc@example.com',
                    role='doctor',
                    password_hash='fakehash',
                    full_name='Dr. Test',
                    tenant_id=t1.id,
                )
                db.session.add(doctor)
                db.session.commit()
                doctor_id = doctor.id

            with tenant_test_context(app, t1):
                patient1 = Patient(
                    tenant_id=t1.id, first_name='P1', last_name='Test', phone='0500000001'
                )
                db.session.add(patient1)
                db.session.commit()
                patient1_id = patient1.id

            with tenant_test_context(app, t2):
                patient2 = Patient(
                    tenant_id=t2.id, first_name='P2', last_name='Test', phone='0500000002'
                )
                db.session.add(patient2)
                db.session.commit()

            with tenant_test_context(app, t1):
                a1 = Appointment(
                    tenant_id=t1.id,
                    patient_id=patient1_id,
                    doctor_id=doctor_id,
                    status=AppointmentState.SCHEDULED,
                    starts_at=soon,
                )
                db.session.add(a1)
                db.session.commit()

            with tenant_test_context(app, t2):
                a2 = Appointment(
                    tenant_id=t2.id,
                    patient_id=patient2.id,
                    doctor_id=doctor_id,
                    status=AppointmentState.SCHEDULED,
                    starts_at=soon,
                )
                db.session.add(a2)
                db.session.commit()
                patient2_id = patient2.id

            # get_tenant_record verifies ownership against g.tenant_id.
            g.tenant_id = t1.id

            mock_add = MagicMock()
            monkeypatch.setattr(NotificationService, 'add_to_notification_queue', mock_add)

            result = None
            # See the note in the notification-queue test: the worker runs inside
            # the tenant it serves, otherwise the ORM auto-filter narrows the
            # explicitly-scoped query to nothing.
            with tenant_test_context(app, t1):
                result = NotificationService.send_appointment_reminders(tenant_id=t1.id)
                assert result['success'] is True
                assert result['sent'] == 1

            called_tenant_ids = {call.kwargs.get('tenant_id') for call in mock_add.call_args_list}
            assert t2.id not in called_tenant_ids
            assert patient2_id != patient1_id
