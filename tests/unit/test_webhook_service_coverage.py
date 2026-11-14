"""Coverage tests for services/webhook_service.py"""

import contextlib
from unittest.mock import MagicMock, patch


class TestWebhookService:
    def test_sign_payload(self):
        from services.webhook_service import _sign_payload

        result = _sign_payload(b'{"test": true}', 'secret')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_load_webhooks(self):
        from services.webhook_service import _load_webhooks

        result = _load_webhooks()
        assert isinstance(result, list)

    def test_dispatch_webhook_no_webhooks(self):
        from services.webhook_service import dispatch_webhook

        with patch('services.webhook_service._load_webhooks', return_value=[]):
            dispatch_webhook('test.event', {'key': 'value'})
            # Should not raise

    def test_get_queue_stats(self):
        from services.webhook_service import get_queue_stats

        result = get_queue_stats()
        assert isinstance(result, dict)

    def test_init_shutdown(self):
        from services.webhook_service import init_webhook_service, shutdown_webhook_service

        init_webhook_service()
        shutdown_webhook_service()

    def test_supported_events(self):
        from services.webhook_service import SUPPORTED_EVENTS

        assert isinstance(SUPPORTED_EVENTS, frozenset)
        assert len(SUPPORTED_EVENTS) > 0

    def test_enqueue_for_retry(self):
        from services.webhook_service import _enqueue_for_retry

        wh = {'url': 'http://example.com', 'secret': 's'}
        _enqueue_for_retry(wh, 'test.event', {'key': 'val'}, 0)

    def test_enqueue_to_dead_letter(self):
        from services.webhook_service import _enqueue_to_dead_letter

        wh = {'url': 'http://example.com', 'secret': 's'}
        _enqueue_to_dead_letter(wh, 'test.event', {'key': 'val'}, 'error msg')

    def test_dispatch_single_success(self):
        from services.webhook_service import _dispatch_single

        wh = {'url': 'http://example.com/hook', 'secret': 's'}
        with patch('services.webhook_service.urlopen') as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            _dispatch_single(wh, 'test.event', {'key': 'val'}, 0)

    def test_dispatch_single_http_error(self):
        from urllib.error import HTTPError

        from services.webhook_service import _dispatch_single

        wh = {'url': 'http://example.com/hook', 'secret': 's'}
        with patch(
            'services.webhook_service.urlopen', side_effect=HTTPError('url', 500, 'err', {}, None)
        ):
            with contextlib.suppress(Exception):
                _dispatch_single(wh, 'test.event', {'key': 'val'}, 0)
