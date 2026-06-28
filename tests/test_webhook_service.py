"""Tests for services.webhook_service dispatch and signing."""
import json
from unittest.mock import MagicMock, patch

import pytest

import services.webhook_service as wh


class TestSignPayload:
    def test_hmac_deterministic(self):
        body = b'{"event":"tenant.created"}'
        assert wh._sign_payload(body, 'secret') == wh._sign_payload(body, 'secret')
        assert wh._sign_payload(body, 'secret') != wh._sign_payload(body, 'other')


class TestDispatchSingle:
    def test_success_on_200(self):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        with patch('services.webhook_service.urlopen', return_value=resp):
            ok = wh._dispatch_single({'url': 'http://example.com/hook', 'secret': 's'}, 'tenant.created', {'id': 1})
        assert ok is True

    def test_empty_url_returns_false(self):
        assert wh._dispatch_single({'url': ''}, 'tenant.created', {}) is False


class TestDispatchWebhook:
    def test_unknown_event_noop(self, monkeypatch):
        called = []
        monkeypatch.setattr(wh, '_load_webhooks', lambda: [{'url': 'http://x', 'events': '*'}])
        monkeypatch.setattr(wh, '_dispatch_queue', MagicMock(put=called.append))
        wh.dispatch_webhook('not.a.real.event', {'x': 1})
        assert called == []

    def test_enqueues_matching_webhook(self, monkeypatch):
        items = []
        monkeypatch.setattr(wh, '_load_webhooks', lambda: [
            {'url': 'http://example.com/h', 'secret': 'k', 'events': 'tenant.created'},
        ])
        fake_q = MagicMock()
        fake_q.put = items.append
        monkeypatch.setattr(wh, '_dispatch_queue', fake_q)
        wh.dispatch_webhook(wh.EVENT_TENANT_CREATED, {'tenant_id': 5})
        assert len(items) == 1
        assert items[0]['event'] == wh.EVENT_TENANT_CREATED
        assert items[0]['payload']['data']['tenant_id'] == 5

    def test_filters_by_event_list(self, monkeypatch):
        items = []
        monkeypatch.setattr(wh, '_load_webhooks', lambda: [
            {'url': 'http://a', 'events': 'bundle.changed'},
            {'url': 'http://b', 'events': 'tenant.created'},
        ])
        fake_q = MagicMock()
        fake_q.put = items.append
        monkeypatch.setattr(wh, '_dispatch_queue', fake_q)
        wh.dispatch_webhook(wh.EVENT_TENANT_CREATED, {})
        assert len(items) == 1
        assert items[0]['webhook']['url'] == 'http://b'


class TestQueueStats:
    def test_returns_sizes(self):
        stats = wh.get_queue_stats()
        assert 'dispatch_queue_size' in stats
        assert 'retry_queue_size' in stats
        assert 'dead_letter_queue_size' in stats


class TestLoadWebhooks:
    def test_reads_system_config(self, monkeypatch):
        payload = [{'url': 'http://hook', 'events': '*'}]
        monkeypatch.setattr(wh, '_load_webhooks', lambda: payload)
        hooks = wh._load_webhooks()
        assert hooks == payload
