"""Tests for Stripe webhook idempotency under concurrent ingestion."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.core.saas.models import StripeWebhookEvent, StripeWebhookEventStatus
from app.core.tenant.models import TenantStatus
from app.extensions import db
from services.stripe_subscription_service import StripeSubscriptionService


def _unique_event_id():
    return f'evt_test_{uuid.uuid4().hex[:12]}'


class TestStripeWebhookIdempotency:
    """Simulate concurrent webhook delivery with identical event IDs."""

    @pytest.fixture
    def mock_stripe_event(self):
        return {
            'id': _unique_event_id(),
            'type': 'invoice.paid',
            'data': {
                'object': {
                    'customer': 'cus_test_001',
                    'metadata': {'tenant_id': '1'},
                }
            },
        }

    @pytest.fixture
    def mock_payload(self, mock_stripe_event):
        import json

        return json.dumps(mock_stripe_event).encode()

    def test_ingest_webhook_creates_event_record(self, app, mock_payload, mock_stripe_event):
        with patch.object(
            StripeSubscriptionService, 'verify_signature', return_value=mock_stripe_event
        ), patch.object(StripeSubscriptionService, '_tenant_from_event', return_value=None):
            result = StripeSubscriptionService.ingest_webhook(mock_payload, 'sig_header')
            assert result.get('ignored') is True

        # Record should exist
        record = db.session.get(StripeWebhookEvent, mock_stripe_event['id'])
        assert record is not None
        assert record.status == StripeWebhookEventStatus.PROCESSED

    def test_duplicate_event_id_returns_already_processed(
        self, app, mock_payload, mock_stripe_event
    ):
        with patch.object(
            StripeSubscriptionService, 'verify_signature', return_value=mock_stripe_event
        ), patch.object(StripeSubscriptionService, '_tenant_from_event', return_value=None):
            r1 = StripeSubscriptionService.ingest_webhook(mock_payload, 'sig_header')
            r2 = StripeSubscriptionService.ingest_webhook(mock_payload, 'sig_header')

        assert r1.get('ignored') is True
        assert r2.get('already_processed') is True
        assert r2['event_id'] == mock_stripe_event['id']

    def test_concurrent_duplicate_webhooks_return_single_record_mocked(self, app):
        """Simulate lock contention: when lock is held, service returns already_processed."""
        from unittest.mock import patch

        from app.core.rate_limiter import IdempotencyLock

        event_id = _unique_event_id()
        event = {
            'id': event_id,
            'type': 'invoice.paid',
            'data': {
                'object': {
                    'customer': 'cus_test_001',
                    'metadata': {'tenant_id': '1'},
                }
            },
        }
        import json

        payload = json.dumps(event).encode()

        lock = IdempotencyLock(namespace='stripe_webhook', timeout_seconds=5)
        lock.acquire(event_id)

        try:
            # Mock an existing record that the blocked worker should find
            mock_record = MagicMock()
            mock_record.status = StripeWebhookEventStatus.PROCESSED

            with patch.object(
                StripeSubscriptionService, '_check_idempotency', return_value=mock_record
            ), patch.object(
                StripeSubscriptionService, 'verify_signature', return_value=event
            ):
                result = StripeSubscriptionService.ingest_webhook(payload, 'sig_header')
                assert result.get('already_processed') is True
                assert result['event_id'] == event_id
        finally:
            lock.release(event_id)

    def test_concurrent_distinct_events_create_multiple_records(self, app, test_tenant):
        import json
        import threading
        from unittest.mock import patch

        # Make tenant suspended so invoice.paid can reactivate without error
        tenant_id = test_tenant.id
        test_tenant.status = TenantStatus.SUSPENDED
        db.session.commit()

        results = []

        def ingest(payload):
            try:
                with app.app_context():
                    result = StripeSubscriptionService.ingest_webhook(payload, 'sig_header')
                    results.append(result)
            except Exception as e:
                results.append({'error': str(e)})

        event_ids = [f'evt_distinct_{uuid.uuid4().hex[:8]}' for _ in range(3)]
        payloads = [
            json.dumps(
                {
                    'id': eid,
                    'type': 'invoice.paid',
                    'data': {
                        'object': {
                            'customer': 'cus_test_001',
                            'metadata': {'tenant_id': str(tenant_id)},
                        }
                    },
                }
            ).encode()
            for eid in event_ids
        ]

        # Apply patches OUTSIDE the threads: patching inside each thread races
        # on the class attribute and can leave MagicMock leftovers in place,
        # poisoning every subsequent test in the process.
        with patch.object(
            StripeSubscriptionService, 'verify_signature', side_effect=lambda p, _s: json.loads(p)
        ), patch.object(StripeSubscriptionService, '_tenant_from_event', return_value=None):
            threads = [threading.Thread(target=ingest, args=(p,)) for p in payloads]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        errors = [r for r in results if r.get('error')]
        assert len(errors) == 0, f'Unexpected errors: {errors}'

        for eid in event_ids:
            count = db.session.query(StripeWebhookEvent).filter_by(event_id=eid).count()
            assert count == 1

    def test_lock_acquisition_failure_with_retry(self, app, mock_payload, mock_stripe_event):
        """If lock is held, ingest_webhook sleeps briefly then checks DB again."""
        from app.core.rate_limiter import IdempotencyLock

        lock = IdempotencyLock(namespace='stripe_webhook', timeout_seconds=5)
        lock.acquire(mock_stripe_event['id'])

        try:
            with patch.object(
                StripeSubscriptionService, 'verify_signature', return_value=mock_stripe_event
            ), patch.object(
                StripeSubscriptionService, '_tenant_from_event', return_value=None
            ):
                # Pre-seed the record so the retry finds it
                record = StripeWebhookEvent(
                    event_id=mock_stripe_event['id'],
                    status=StripeWebhookEventStatus.PROCESSED,
                    payload_hash='abc',
                    processed_at=datetime.now(UTC),
                )
                db.session.add(record)
                db.session.commit()

                result = StripeSubscriptionService.ingest_webhook(mock_payload, 'sig_header')
                assert result.get('already_processed') is True
        finally:
            lock.release(mock_stripe_event['id'])
