"""Tests for services.notification_service.NotificationService.

Covers the deterministic CRUD/query surface (send, bulk, read-state, counts,
templates, cleanup, queue, whatsapp/email) plus smoke-coverage of the cron-style
aggregators (debt/insurance/appointment/booking reminders, manager summary,
alerts) to ensure they never raise against the live schema. ``rollback_db``.
"""
import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from services.notification_service import NotificationService as NF
from models.notification import (Notification, NotificationTemplate,
                                 WhatsAppNotificationMessage, EmailMessage)
from models.user import User


@pytest.fixture
def fx(rollback_db):
    db = rollback_db

    def user(role='doctor'):
        un = 'nf_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='u', role=role, is_active=True)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def notif(recipient_id, urgent=False, read=False, expires_at=None, ntype='info'):
        n = Notification(title='t', message='m', notification_type=ntype,
                         recipient_id=recipient_id, is_urgent=urgent, is_read=read,
                         expires_at=expires_at, sent_at=datetime.now(timezone.utc))
        db.session.add(n)
        db.session.commit()
        return n

    return types.SimpleNamespace(db=db, user=user, notif=notif)


class TestSend:
    def test_basic_send(self, fx):
        u = fx.user()
        res = NF.send_notification(recipient_id=u.id, title='hi', message='body',
                                   notification_type='info')
        assert res['success'] is True
        assert res['notification_id']
        assert Notification.query.get(res['notification_id']).recipient_id == u.id

    def test_send_unknown_template(self, fx):
        res = NF.send_notification(recipient_id=None, template_name='no_such_tpl_xyz')
        assert res['success'] is False

    def test_send_with_template(self, fx):
        name = 'tpl_' + uuid.uuid4().hex[:6]
        NF.create_notification_template(name=name, title_template='Hi {who}',
                                        message_template='Msg {who}', notification_type='info')
        res = NF.send_notification(recipient_id=None, template_name=name,
                                   template_variables={'who': 'Sara'})
        assert res['success'] is True


class TestBulk:
    def test_bulk_by_ids_roles_depts(self, fx):
        u1, u2 = fx.user(), fx.user()
        res = NF.send_bulk_notification(recipient_ids=[u1.id, u2.id],
                                        recipient_roles=['nurse'],
                                        title='t', message='m')
        assert res['success'] is True
        assert '3' in res['message']


class TestQueryReadState:
    def test_get_user_notifications(self, fx):
        u = fx.user()
        fx.notif(u.id)
        fx.notif(u.id, urgent=True)
        res = NF.get_user_notifications(u.id)
        assert res['success'] is True
        assert res['total_count'] >= 2

    def test_excludes_expired(self, fx):
        u = fx.user()
        fx.notif(u.id, expires_at=datetime.now(timezone.utc) - timedelta(days=1))
        res = NF.get_user_notifications(u.id)
        assert res['total_count'] == 0

    def test_unread_and_urgent_filters(self, fx):
        u = fx.user()
        fx.notif(u.id, read=True)
        fx.notif(u.id, urgent=True)
        assert NF.get_user_notifications(u.id, unread_only=True)['total_count'] == 1
        assert NF.get_user_notifications(u.id, urgent_only=True)['total_count'] == 1

    def test_limit(self, fx):
        u = fx.user()
        for _ in range(3):
            fx.notif(u.id)
        assert NF.get_user_notifications(u.id, limit=2)['total_count'] == 2

    def test_mark_as_read(self, fx):
        u = fx.user()
        n = fx.notif(u.id)
        assert NF.mark_as_read(n.id, u.id)['success'] is True
        assert Notification.query.get(n.id).is_read is True

    def test_mark_as_read_not_found(self, fx):
        u = fx.user()
        assert NF.mark_as_read(99999999, u.id)['success'] is False

    def test_mark_all_as_read(self, fx):
        u = fx.user()
        fx.notif(u.id)
        fx.notif(u.id)
        res = NF.mark_all_as_read(u.id)
        assert res['success'] is True
        assert NF.get_user_notifications(u.id, unread_only=True)['total_count'] == 0

    def test_get_notification_count(self, fx):
        u = fx.user()
        fx.notif(u.id)
        fx.notif(u.id, urgent=True)
        res = NF.get_notification_count(u.id)
        assert res['unread_count'] >= 2
        assert res['urgent_count'] >= 1


class TestTemplates:
    def test_create_and_list(self, fx):
        name = 'tpl_' + uuid.uuid4().hex[:6]
        res = NF.create_notification_template(name=name, title_template='S',
                                              message_template='C', notification_type='info')
        assert res['success'] is True
        listing = NF.get_notification_templates()
        assert listing['success'] is True
        assert any(t.get('name') == name for t in listing['templates'])

    def test_create_default_templates(self, fx):
        res = NF.create_default_templates()
        assert res['success'] is True
        for nm in ('new_visit', 'appointment_reminder', 'payment_required'):
            assert NotificationTemplate.query.filter_by(name=nm).first() is not None


class TestCleanupAndChannels:
    def test_cleanup_expired(self, fx):
        u = fx.user()
        n = fx.notif(u.id, expires_at=datetime.now(timezone.utc) - timedelta(days=2))
        res = NF.cleanup_expired_notifications()
        assert res['success'] is True
        assert Notification.query.get(n.id) is None

    def test_send_whatsapp(self, fx):
        res = NF.send_whatsapp_message('+970599000000', 'hello')
        assert res['success'] is True
        assert WhatsAppNotificationMessage.query.get(res['message_id']) is not None

    def test_send_email(self, fx):
        res = NF.send_email_message('a@b.com', 'subj', '<p>hi</p>')
        assert res['success'] is True

    def test_queue_add_and_status(self, fx):
        u = fx.user()
        NF.add_to_notification_queue(u.id, 'email', 'a@b.com', 'subj', 'content')
        status = NF.get_notification_queue_status()
        assert isinstance(status, dict)


class TestAggregatorsSmoke:
    """Cron-style methods must never raise against the live schema."""

    @pytest.mark.parametrize('method', [
        'send_debt_reminders',
        'send_insurance_followup_alerts',
        'send_force_payment_approval_alerts',
        'send_daily_summary_to_manager',
        'check_and_send_alerts',
        'send_appointment_reminders',
        'send_online_booking_reminders',
    ])
    def test_aggregator_no_raise(self, fx, method):
        result = getattr(NF, method)(tenant_id=None)
        assert result is None or isinstance(result, (dict, list, int))

    def test_process_notification_queue(self, fx):
        u = fx.user()
        NF.add_to_notification_queue(u.id, 'email', 'a@b.com', 'subj', 'content')
        NF.add_to_notification_queue(u.id, 'whatsapp', '+970599000111', 'subj', 'content')
        NF.add_to_notification_queue(u.id, 'inapp', None, 'subj', 'content')
        result = NF.process_notification_queue(tenant_id=None)
        assert result['success'] is True
        assert result['processed_count'] >= 3


class TestAggregatorsWithData:
    """Seed Visits so the financial aggregators execute their inner loops."""

    def _visit(self, fx, **kw):
        from models.visit import Visit
        from models.patient import Patient
        p = Patient(first_name='a', last_name='b')
        fx.db.session.add(p)
        fx.db.session.commit()
        params = dict(patient_id=p.id, total_amount=200, paid_amount=0)
        params.update(kw)
        v = Visit(**params)
        fx.db.session.add(v)
        fx.db.session.commit()
        return v

    def test_debt_reminders_drives_loop(self, fx):
        from app.shared.enums import PaymentStatus
        old = datetime.now() - timedelta(days=70)  # >60d -> manager + urgent branches
        self._visit(fx, payment_status=PaymentStatus.DEBT, is_force_payment=True,
                    created_at=old, force_payment_reason='تأخر', total_amount=300, paid_amount=0)
        res = NF.send_debt_reminders(tenant_id=None)
        assert res['success'] is True
        assert res['debts_found'] >= 1
        assert res['reminders_sent'] >= 1

    def test_insurance_followup_drives_loop(self, fx):
        from app.shared.enums import PaymentStatus
        old = datetime.now() - timedelta(days=50)  # >45d -> urgent branch
        self._visit(fx, payment_method='insurance', payment_status=PaymentStatus.PARTIAL,
                    created_at=old, insurance_amount=120, insurance_provider='X',
                    insurance_policy_number='POL1', total_amount=200, paid_amount=80)
        res = NF.send_insurance_followup_alerts(tenant_id=None)
        assert res['success'] is True
        assert res['pending_claims'] >= 1

    def test_force_payment_alerts_drives_loop(self, fx):
        self._visit(fx, is_force_payment=True, force_payment_approved_by=None,
                    force_payment_reason='ضرورة طبية عاجلة', total_amount=150)
        res = NF.send_force_payment_approval_alerts(tenant_id=None)
        assert res['success'] is True
        assert res['pending_count'] >= 1

    def test_appointment_reminders_both_branches(self, fx):
        from models.appointment import Appointment
        from models.patient import Patient
        from app.shared.enums import AppointmentState
        soon = datetime.now() + timedelta(hours=2)
        with_phone = Patient(first_name='ذو', last_name='هاتف', phone='+970599111222')
        no_phone = Patient(first_name='بلا', last_name='هاتف')
        fx.db.session.add_all([with_phone, no_phone])
        fx.db.session.commit()
        doctor = fx.user(role='doctor')
        fx.db.session.add_all([
            Appointment(patient_id=with_phone.id, doctor_id=doctor.id,
                        starts_at=soon, status=AppointmentState.SCHEDULED),
            Appointment(patient_id=no_phone.id, starts_at=soon,
                        status=AppointmentState.SCHEDULED),
        ])
        fx.db.session.commit()
        res = NF.send_appointment_reminders(tenant_id=None)
        assert res['success'] is True
        assert res['sent'] >= 1
        assert res['fallback_notified'] >= 1

    def test_online_booking_reminders_drives_loop(self, fx):
        from models.online_booking import OnlineBooking
        from models.department import Department
        from app.shared.enums import BookingState
        dept = Department.query.first()
        if dept is None:
            dept = Department(name='General', name_ar='عيادة عامة')
            fx.db.session.add(dept)
            fx.db.session.commit()
        soon = datetime.now(timezone.utc) + timedelta(hours=2)
        with_email = OnlineBooking(
            booking_reference='BK-' + uuid.uuid4().hex[:8],
            first_name='حجز', last_name='اونلاين', phone='+970599333444',
            email='booker@x.com', appointment_date=soon.date(),
            appointment_time=soon.time(), status=BookingState.PENDING,
            department_id=dept.id,
        )
        no_email = OnlineBooking(
            booking_reference='BK-' + uuid.uuid4().hex[:8],
            first_name='بلا', last_name='بريد', phone='+970599555666',
            appointment_date=soon.date(), appointment_time=soon.time(),
            status=BookingState.CONFIRMED, department_id=dept.id,
        )
        fx.db.session.add_all([with_email, no_email])
        fx.db.session.commit()
        res = NF.send_online_booking_reminders(tenant_id=None)
        assert res['success'] is True
        assert res['sent'] >= 1
        assert res['fallback_notified'] >= 1

    def test_module_level_process_queue_entry(self, fx):
        from services.notification_service import process_notification_queue
        u = fx.user()
        NF.add_to_notification_queue(u.id, 'inapp', None, 's', 'c')
        count = process_notification_queue(tenant_id=None)
        assert isinstance(count, int)
        assert count >= 1

    def test_check_and_send_alerts_wrapper(self, fx):
        res = NF.check_and_send_alerts(tenant_id=None)
        assert res['success'] is True
        assert 'results' in res
        assert 'debt_reminders' in res['results']

    def test_daily_summary_to_manager(self, fx):
        res = NF.send_daily_summary_to_manager(tenant_id=None)
        assert isinstance(res, dict)
        assert 'success' in res
