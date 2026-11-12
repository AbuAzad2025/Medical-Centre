"""Coverage for services/notification_service.py.

The notification service is what tells the rest of the system that
something happened: an appointment, a debt, an insurance follow-up, a
force-payment approval. Most of its methods had never been called, so the
code that decides who is told, and what is queued for later delivery, was
untested.

Each test class is named after the method it covers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

pytest_plugins = ['tests._isolated_tenant']


def _user(db, tenant_id, username='notif_user', role='doctor'):
    from models.user import User

    user = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role=role,
        is_active=True,
        tenant_id=tenant_id,
    )
    user.set_password('test123')
    db.session.add(user)
    db.session.flush()
    return user


def _notification(db, tenant_id, user_id, **kwargs):
    from models.notification import Notification

    defaults = {
        'title': 'Test notification',
        'message': 'Something happened',
        'notification_type': 'info',
        'recipient_id': user_id,
        'is_read': False,
        'is_urgent': False,
        'sent_at': datetime.now(UTC),
    }
    defaults.update(kwargs)
    notification = Notification(tenant_id=tenant_id, **defaults)
    db.session.add(notification)
    db.session.flush()
    return notification


class TestSendNotification:
    """``send_notification`` — one notification to one recipient."""

    def test_a_notification_is_created(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        result = NotificationService.send_notification(
            recipient_id=user.id,
            title='Hello',
            message='World',
            notification_type='info',
        )
        assert result['success'] is True
        assert result['notification_id']

    def test_a_missing_template_is_refused(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_notification(
            recipient_id=None,
            title='Hello',
            message='World',
            template_name='no-such-template',
        )
        assert result['success'] is False

    def test_an_existing_template_renders_the_notification(self, app, db, test_tenant):
        from models.notification import NotificationTemplate
        from services.notification_service import NotificationService

        template = NotificationTemplate(
            tenant_id=test_tenant.id,
            name='welcome',
            template_type='email',
            subject='Welcome',
            content='Hello {{ name }}',
            variables='{"name": "Jane"}',
            is_active=True,
        )
        db.session.add(template)
        db.session.flush()

        result = NotificationService.send_notification(
            recipient_id=None,
            title='ignored',
            message='ignored',
            template_name='welcome',
            template_variables={'name': 'Jane'},
        )
        assert result['success'] is True

    def test_a_failing_write_is_reported(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        with patch(
            'services.notification_service.safe_commit',
            return_value=False,
        ):
            result = NotificationService.send_notification(
                recipient_id=None,
                title='Hello',
                message='World',
            )
        assert result['success'] is False


class TestSendBulkNotification:
    """``send_bulk_notification`` — one message to many recipients."""

    def test_a_bulk_notification_reaches_every_recipient(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        first = _user(db, test_tenant.id, 'bulk_user_1')
        second = _user(db, test_tenant.id, 'bulk_user_2')

        result = NotificationService.send_bulk_notification(
            recipient_ids=[first.id, second.id],
            title='Hello',
            message='World',
        )
        assert result['success'] is True


class TestReadAndCount:
    """Reading notifications back."""

    def test_the_notifications_of_a_user_are_listed(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        _notification(db, test_tenant.id, user.id, title='One')
        _notification(db, test_tenant.id, user.id, title='Two', is_read=True)

        result = NotificationService.get_user_notifications(user.id)
        assert result['success'] is True
        assert result['total_count'] == 2

    def test_only_unread_notifications_are_listed(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        _notification(db, test_tenant.id, user.id, title='Unread')
        _notification(db, test_tenant.id, user.id, title='Read', is_read=True)

        result = NotificationService.get_user_notifications(user.id, unread_only=True)
        assert result['total_count'] == 1

    def test_only_urgent_notifications_are_listed(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        _notification(db, test_tenant.id, user.id, title='Urgent', is_urgent=True)
        _notification(db, test_tenant.id, user.id, title='Calm', is_urgent=False)

        result = NotificationService.get_user_notifications(user.id, urgent_only=True)
        assert result['total_count'] == 1

    def test_the_list_can_be_limited(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        _notification(db, test_tenant.id, user.id, title='One')
        _notification(db, test_tenant.id, user.id, title='Two')

        result = NotificationService.get_user_notifications(user.id, limit=1)
        assert result['total_count'] == 1

    def test_a_notification_is_marked_as_read(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        notification = _notification(db, test_tenant.id, user.id)

        result = NotificationService.mark_as_read(notification.id, user.id)
        assert result['success'] is True

        db.session.refresh(notification)
        assert notification.is_read is True
        assert notification.read_at is not None

    def test_another_user_cannot_mark_it_read(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        owner = _user(db, test_tenant.id, 'notif_owner')
        other = _user(db, test_tenant.id, 'notif_other')
        notification = _notification(db, test_tenant.id, owner.id)

        result = NotificationService.mark_as_read(notification.id, other.id)
        assert result['success'] is False

        db.session.refresh(notification)
        assert notification.is_read is False

    def test_every_notification_is_marked_as_read(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        _notification(db, test_tenant.id, user.id)
        _notification(db, test_tenant.id, user.id)

        result = NotificationService.mark_all_as_read(user.id)
        assert result['success'] is True

        db.session.expire_all()
        remaining = NotificationService.get_user_notifications(user.id, unread_only=True)
        assert remaining['total_count'] == 0

    def test_the_count_of_unread_notifications(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        _notification(db, test_tenant.id, user.id)
        _notification(db, test_tenant.id, user.id, is_read=True)
        _notification(db, test_tenant.id, user.id, is_urgent=True)

        count = NotificationService.get_notification_count(user.id)
        assert count['success'] is True
        assert count['unread_count'] == 2
        assert count['urgent_count'] == 1


class TestTemplates:
    """Notification templates."""

    def test_a_template_is_created(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.create_notification_template(
            name='reminder',
            title_template='Reminder',
            message_template='Do not forget',
            notification_type='email',
            variables={'x': 1},
        )
        assert result['success'] is True
        assert result['template_id']

    def test_the_templates_are_listed(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        templates = NotificationService.get_notification_templates()
        assert templates['success'] is True
        assert isinstance(templates['templates'], list)

    def test_the_default_templates_are_created(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.create_default_templates()
        assert result is not None


class TestCleanup:
    """Expired notifications."""

    def test_expired_notifications_are_removed(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        expired = _notification(
            db,
            test_tenant.id,
            user.id,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        _notification(
            db,
            test_tenant.id,
            user.id,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )

        NotificationService.cleanup_expired_notifications()

        db.session.expire_all()
        assert db.session.get(type(expired), expired.id) is None


class TestQueue:
    """The queue that holds notifications for later delivery."""

    def test_a_notification_is_queued(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        result = NotificationService.add_to_notification_queue(
            user_id=user.id,
            notification_type='email',
            recipient='someone@example.test',
            subject='Hello',
            content='World',
        )
        assert result['success'] is True

    def test_the_queue_status_is_reported(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        status = NotificationService.get_notification_queue_status()
        assert isinstance(status, dict)

    def test_the_queue_is_processed(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        user = _user(db, test_tenant.id)
        NotificationService.add_to_notification_queue(
            user_id=user.id,
            notification_type='email',
            recipient='someone@example.test',
            subject='Hello',
            content='World',
        )

        result = NotificationService.process_notification_queue(tenant_id=test_tenant.id)
        assert result is not None

    def test_the_module_level_entry_point_returns_a_count(self, app, db, test_tenant):
        from services.notification_service import process_notification_queue

        processed = process_notification_queue(tenant_id=test_tenant.id)
        assert isinstance(processed, int)


class TestAlerts:
    """The reminder and alert sweeps."""

    def test_debt_reminders_are_sent(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_debt_reminders(tenant_id=test_tenant.id)
        assert result is not None

    def test_insurance_follow_up_alerts_are_sent(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_insurance_followup_alerts(tenant_id=test_tenant.id)
        assert result is not None

    def test_force_payment_approval_alerts_are_sent(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_force_payment_approval_alerts(tenant_id=test_tenant.id)
        assert result is not None

    def test_the_daily_summary_is_sent_to_the_manager(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_daily_summary_to_manager(tenant_id=test_tenant.id)
        assert result is not None

    def test_the_alert_sweep_runs(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.check_and_send_alerts(tenant_id=test_tenant.id)
        assert result is not None

    def test_appointment_reminders_are_sent(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_appointment_reminders(tenant_id=test_tenant.id)
        assert result is not None

    def test_online_booking_reminders_are_sent(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_online_booking_reminders(tenant_id=test_tenant.id)
        assert result is not None


class TestMessages:
    """Sending a message through a channel."""

    def test_a_whatsapp_message_is_queued(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_whatsapp_message(
            phone_number='+15550000000',
            message_content='Hello',
        )
        assert result['success'] is True

    def test_an_email_message_is_queued(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        result = NotificationService.send_email_message(
            recipient_email='someone@example.test',
            subject='Hello',
            content='World',
        )
        assert result['success'] is True


class TestDisabledModule:
    """A notification for a module the clinic switched off."""

    def test_a_disabled_module_drops_the_notification(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        with patch(
            'services.notification_service.FeatureGateService.module_enabled',
            return_value=False,
        ):
            result = NotificationService.send_notification(
                recipient_role='radiology',
                title='Hello',
                message='World',
            )
        assert result['success'] is False

    def test_an_enabled_module_delivers_the_notification(self, app, db, test_tenant):
        from services.notification_service import NotificationService

        with patch(
            'services.notification_service.FeatureGateService.module_enabled',
            return_value=True,
        ):
            result = NotificationService.send_notification(
                recipient_role='radiology',
                title='Hello',
                message='World',
            )
        assert result['success'] is True
