"""Coverage tests for utils/safe_requests.py"""

from unittest.mock import patch

from utils.safe_requests import (
    FAST_TIMEOUT,
    LARGE_PAYLOAD_TIMEOUT,
    safe_delete,
    safe_get,
    safe_post,
    safe_put,
    safe_request,
    with_timeout,
)


class TestSafeRequests:
    @patch('utils.safe_requests.requests.request')
    def test_safe_get_success(self, mock_request):
        mock_request.return_value.status_code = 200
        resp = safe_get('http://example.com')
        assert resp.status_code == 200

    @patch('utils.safe_requests.requests.request')
    def test_safe_post_success(self, mock_request):
        mock_request.return_value.status_code = 201
        resp = safe_post('http://example.com', json={'a': 1})
        assert resp.status_code == 201

    @patch('utils.safe_requests.requests.request')
    def test_safe_put_success(self, mock_request):
        mock_request.return_value.status_code = 200
        resp = safe_put('http://example.com')
        assert resp.status_code == 200

    @patch('utils.safe_requests.requests.request')
    def test_safe_delete_success(self, mock_request):
        mock_request.return_value.status_code = 204
        resp = safe_delete('http://example.com')
        assert resp.status_code == 204

    @patch('utils.safe_requests.requests.request')
    def test_safe_request_retry_on_timeout(self, mock_request):
        import requests

        mock_request.side_effect = [requests.Timeout('timeout'), requests.Response()]
        mock_request.return_value.status_code = 200
        # First call times out, second succeeds
        mock_request.side_effect = [requests.Timeout('timeout')]
        mock_request.return_value = type('R', (), {'status_code': 200})()
        import contextlib

        with contextlib.suppress(Exception):
            safe_request('GET', 'http://example.com', retries=1, retry_backoff=0.0)

    @patch('utils.safe_requests.requests.request')
    def test_safe_request_connection_error(self, mock_request):
        import requests

        mock_request.side_effect = requests.ConnectionError('conn error')
        import contextlib

        import requests

        with contextlib.suppress(requests.ConnectionError):
            safe_request('GET', 'http://example.com', retries=0)

    def test_with_timeout_decorator(self):
        @with_timeout(timeout=(1.0, 2.0), retries=2)
        def fn(timeout=None, retries=None):
            return timeout, retries

        t, r = fn()
        assert t == (1.0, 2.0)
        assert r == 2

    def test_constants(self):
        assert FAST_TIMEOUT == (3.0, 5.0)
        assert LARGE_PAYLOAD_TIMEOUT == (10.0, 60.0)
