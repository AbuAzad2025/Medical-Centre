"""The diagnostic paths that reported success while nothing had happened.

Three of them, all measured rather than assumed:

  * the readiness endpoint answered 200 with status 'ok' while Redis was down,
    and Redis is the Celery broker and the payment idempotency lock;
  * the appointment reminder job had no time window at all, so it queued a
    fresh notification for every appointment the system had ever held, once a
    minute, forever;
  * a broken Twilio configuration fell back to the logging provider, which
    reported the message as sent, so the queue marked it SENT and the record
    of a delivery that never happened was all that was left.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from models.appointment import Appointment


@pytest.fixture
def appointment_factory(app, test_tenant):
    """An appointment in this tenant, at a chosen time and status."""

    def make(starts_at, status='SCHEDULED', reference='e2e-appt'):
        from models.patient import Patient

        patient = (
            db.session.execute(select(Patient).filter_by(tenant_id=test_tenant.id).limit(1))
            .scalars()
            .first()
        )
        if patient is None:
            patient = Patient(
                tenant_id=test_tenant.id,
                first_name='Reminder',
                last_name='Patient',
                national_id='E2E-REMINDER-1',
            )
            db.session.add(patient)
            db.session.flush()
        row = Appointment(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=None,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
            status=status,
            notes=reference,
        )
        db.session.add(row)
        db.session.commit()
        return row

    return make


def test_the_readiness_probe_fails_when_redis_is_down(app, monkeypatch):
    """Redis down means the broker and the payment lock are down.

    The endpoint used to record the failure and still answer 200 with
    status 'ok', so a load balancer or a blackbox monitor saw a healthy
    system while background jobs did not run and two concurrent payments
    could both take the same money.
    """
    import redis

    def boom(*args, **kwargs):
        raise redis.ConnectionError('redis is down')

    monkeypatch.setenv('REDIS_URL', 'redis://127.0.0.1:6399/0')
    monkeypatch.setattr(redis, 'from_url', boom)

    with app.test_client() as client:
        resp = client.get('/health')

    assert resp.status_code == 503, (
        f'/health answered {resp.status_code} with Redis down; a readiness probe '
        'that says ok while a dependency is down is worse than no probe'
    )
    body = resp.get_json()
    assert body['status'] == 'degraded'
    assert body['checks'].get('redis_degraded') is True


def test_the_reminder_job_only_looks_at_the_next_day(app, appointment_factory, monkeypatch):
    """A reminder is for an appointment in the next 24 hours.

    The window was computed and thrown away, so the query had no time bound
    and no status filter. The job runs once a minute, so every appointment
    the system had ever held - including cancelled ones and ones from last
    year - got a fresh notification row, and an SMS, every minute.
    """
    from services.notification_service import NotificationService

    now = datetime.now(UTC)
    soon = appointment_factory(now + timedelta(hours=2), status='SCHEDULED')
    far = appointment_factory(now + timedelta(days=30), status='SCHEDULED')
    past = appointment_factory(now - timedelta(days=30), status='SCHEDULED')
    cancelled = appointment_factory(now + timedelta(hours=3), status='CANCELLED')

    seen: list[str] = []
    original = NotificationService.send_notification

    def record(recipient_id=None, message=None, **kwargs):
        seen.append(message or '')
        return {'success': True}

    monkeypatch.setattr(NotificationService, 'send_notification', staticmethod(record))

    NotificationService.send_appointment_reminders()

    # Exactly one appointment is inside the window, so exactly one reminder.
    assert len(seen) == 1, (
        f'{len(seen)} reminders were queued for one appointment in the next 24 '
        'hours; the query had no time window and no status filter, so every '
        'appointment the system had ever held was reminded too'
    )
    assert soon.starts_at.strftime('%Y-%m-%d') in seen[0], (
        'the reminder that was queued was not for the appointment in the window'
    )


def test_a_broken_sms_provider_does_not_report_the_message_as_sent(app, test_tenant):
    """A configured provider that cannot send must say so.

    The Twilio configuration was incomplete, so the message fell back to the
    logging provider, which reported success. The notification queue then
    marked the row SENT, and the record of a delivery that never happened
    was all that was left.
    """
    from app.integrations.sms.provider import UnconfiguredSMSProvider, get_sms_provider

    provider = UnconfiguredSMSProvider()
    result = provider.send('+966500000000', 'a message that will not arrive')

    assert result['success'] is False, (
        'a provider that cannot deliver reported success; the notification queue '
        'marks those rows SENT'
    )
    assert result['delivered'] is False

    # And the selector has to reach that provider when the tenant asked for
    # Twilio and the credentials are incomplete.
    from app.core.tenant.models import Tenant

    tenant = db.session.execute(select(Tenant).filter_by(slug='pharmacy-shifa')).scalars().first()
    if tenant is None:
        pytest.skip('the shared test tenant is not present')

    settings = dict(tenant.settings or {})
    settings['sms'] = {
        'enabled': True,
        'provider': 'twilio',
        'twilio_account_sid': '',
        'twilio_auth_token': '',
        'twilio_phone_number': '',
    }
    tenant.settings = settings
    db.session.commit()

    chosen = get_sms_provider(tenant=tenant)
    assert isinstance(chosen, UnconfiguredSMSProvider), (
        'an incomplete Twilio configuration still fell back to the logging '
        'provider, which reports the message as sent'
    )
