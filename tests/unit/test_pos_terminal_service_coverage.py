"""Coverage tests for services.pos_terminal_service.py.

The POS terminal service is deliberately dependency-free: it reads its
configuration from the environment and talks to the terminal over plain
``urllib``. That makes it fully testable without a database, a Flask app or a
network -- the terminal is replaced by a fake ``urlopen`` that records the
request the service built and replays a canned response.

The tests assert the observable contract of the service:

* which environment values turn the terminal on and which URL it is pointed at;
* the exact request the service sends (URL, method, headers, JSON body,
  timeout);
* the exact response mapping the service produces for a successful charge,
  for a terminal that declined the card, for an HTTP error, for an
  unreachable device and for a malformed answer.

Every failure branch is asserted on the machine-readable ``code`` field, not
only on the Arabic prose: ``app/shared/pos_charge.py`` maps those codes onto
HTTP statuses (503/502/402), so the code is the part of the contract other
modules depend on.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from urllib import error, request

import pytest

from services import pos_terminal_service as pos_module
from services.pos_terminal_service import PosTerminalService

# The exact strings the service returns, copied from the module so a change
# in the user-facing wording is caught here rather than silently shipped.
MSG_NOT_ENABLED = 'خدمة الدفع الإلكتروني غير مفعلة حالياً (not enabled)'
MSG_HTTP_ERROR = 'تعذر تنفيذ عملية الدفع عبر الجهاز حالياً'
MSG_UNREACHABLE = 'تعذر الاتصال بجهاز الدفع حالياً (conn)'
MSG_GENERIC_ERROR = 'تعذر تنفيذ عملية الدفع حالياً'


class _FakeResponse:
    """Minimal stand-in for the object ``urllib.request.urlopen`` returns."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _RecordingUrlopen:
    """Fake ``urlopen`` that records every call and replays a fixed outcome."""

    def __init__(self, body: bytes = b'', exc: Exception | None = None):
        self._body = body
        self._exc = exc
        self.calls: list[dict] = []

    def __call__(self, req, timeout=None):
        self.calls.append({'request': req, 'timeout': timeout})
        if self._exc is not None:
            raise self._exc
        return _FakeResponse(self._body)

    @property
    def last_request(self):
        assert self.calls, 'urlopen was never called'
        return self.calls[-1]['request']


@pytest.fixture
def fake_urlopen(monkeypatch):
    """Install a fake ``urlopen`` in the service module.

    Only the ``request`` name inside ``services.pos_terminal_service`` is
    replaced, and the real ``urllib.request.Request`` class is kept, so the
    test can inspect the request the service actually built. The ``error``
    name is deliberately left alone: the service must catch the genuine
    ``urllib.error`` exception types.
    """

    def _install(body: bytes = b'', exc: Exception | None = None) -> _RecordingUrlopen:
        fake = _RecordingUrlopen(body=body, exc=exc)
        monkeypatch.setattr(
            pos_module,
            'request',
            SimpleNamespace(Request=request.Request, urlopen=fake),
        )
        return fake

    return _install


@pytest.fixture(autouse=True)
def _clean_pos_env(monkeypatch):
    """Start every test from a known POS environment.

    ``POS_ENABLED`` and ``POS_BASE_URL`` are read straight from
    ``os.environ`` on every call, so a developer's ``.env`` (or a previous
    test) would otherwise decide whether the terminal is enabled.
    """
    monkeypatch.delenv('POS_ENABLED', raising=False)
    monkeypatch.delenv('POS_BASE_URL', raising=False)


@pytest.fixture
def enabled(monkeypatch):
    """Turn the terminal on and point it at a local device."""
    monkeypatch.setenv('POS_ENABLED', '1')
    monkeypatch.setenv('POS_BASE_URL', 'http://127.0.0.1:9100/api/pos')


class TestIsEnabled:
    """``is_enabled`` decides whether the terminal may be used at all."""

    @pytest.mark.parametrize('value', ['1', 'true', 'TRUE', 'yes', 'YES', 'on', 'ON'])
    def test_truthy_flags_enable_the_terminal(self, monkeypatch, value):
        monkeypatch.setenv('POS_ENABLED', value)
        assert PosTerminalService.is_enabled() is True

    def test_whitespace_around_the_flag_is_ignored(self, monkeypatch):
        monkeypatch.setenv('POS_ENABLED', '  true  ')
        assert PosTerminalService.is_enabled() is True

    @pytest.mark.parametrize('value', ['0', 'false', 'FALSE', 'no', 'off', 'maybe', ''])
    def test_falsy_flags_leave_the_terminal_disabled(self, monkeypatch, value):
        monkeypatch.setenv('POS_ENABLED', value)
        assert PosTerminalService.is_enabled() is False

    def test_absent_flag_leaves_the_terminal_disabled(self):
        assert PosTerminalService.is_enabled() is False

    def test_a_configured_base_url_enables_the_terminal(self, monkeypatch):
        """A deployment that points at a terminal has implicitly opted in."""
        monkeypatch.setenv('POS_BASE_URL', 'http://127.0.0.1:9100/api/pos')
        assert PosTerminalService.is_enabled() is True

    def test_an_explicitly_disabled_terminal_stays_disabled(self, monkeypatch):
        """An explicit ``POS_ENABLED=false`` wins over a configured base URL.

        The flag used to be OR-ed with "is a base URL configured", so an
        operator who disabled the feature still got a live terminal as long as
        ``POS_BASE_URL`` was in the environment.
        """
        monkeypatch.setenv('POS_ENABLED', 'false')
        monkeypatch.setenv('POS_BASE_URL', 'http://127.0.0.1:9100/api/pos')
        assert PosTerminalService.is_enabled() is False


class TestBaseUrl:
    """``base_url`` is where the terminal lives."""

    def test_default_points_at_the_local_terminal(self):
        assert PosTerminalService.base_url() == 'http://127.0.0.1:9100/api/pos'

    def test_environment_overrides_the_default(self, monkeypatch):
        monkeypatch.setenv('POS_BASE_URL', 'http://pos.local:9200/api/pos')
        assert PosTerminalService.base_url() == 'http://pos.local:9200/api/pos'

    def test_an_empty_base_url_falls_back_to_the_default(self, monkeypatch):
        """A variable that is set but blank is not a base URL.

        ``os.environ.get('POS_BASE_URL', default)`` returns the empty string
        when the variable exists but is blank -- the default only applies to a
        *missing* variable. The service then built the relative URL
        ``/charge``. Combined with ``POS_ENABLED=true`` that silently charged
        against no terminal at all instead of the configured default.
        """
        monkeypatch.setenv('POS_BASE_URL', '')
        assert PosTerminalService.base_url() == 'http://127.0.0.1:9100/api/pos'


class TestChargeWhenDisabled:
    """With the terminal off, ``charge`` must refuse without touching the network."""

    def test_refuses_and_reports_a_machine_readable_code(self, fake_urlopen):
        fake = fake_urlopen()

        result = PosTerminalService.charge(50.0)

        assert result == {
            'success': False,
            'code': 'pos_not_enabled',
            'message': MSG_NOT_ENABLED,
        }
        assert fake.calls == [], 'the terminal must not be contacted when disabled'

    def test_refuses_when_neither_signal_is_set(self, monkeypatch, fake_urlopen):
        """Both signals off is the only way the terminal stays unreachable."""
        monkeypatch.delenv('POS_ENABLED', raising=False)
        monkeypatch.delenv('POS_BASE_URL', raising=False)
        fake = fake_urlopen()

        result = PosTerminalService.charge(50.0)

        assert result['code'] == 'pos_not_enabled'
        assert fake.calls == []


class TestChargeSuccess:
    """A successful charge maps the terminal's answer onto the service contract."""

    def test_full_terminal_response_is_mapped_onto_the_result(self, enabled, fake_urlopen):
        body = json.dumps(
            {
                'success': True,
                'transaction_id': 'TXN-4711',
                'approval_code': 'APPROV-99',
                'card_last_digits': '4242',
                'card_holder_name': 'AHMED ALI',
                'amount': 42.5,
                'currency': 'ILS',
                'message': 'approved',
            }
        ).encode('utf-8')
        fake = fake_urlopen(body=body)

        result = PosTerminalService.charge(42.5)

        assert result == {
            'success': True,
            'transaction_id': 'TXN-4711',
            'approval_code': 'APPROV-99',
            'card_last_digits': '4242',
            'card_holder_name': 'AHMED ALI',
            'amount': 42.5,
            'currency': 'ILS',
            'message': 'approved',
        }
        assert fake.calls, 'the terminal must be contacted'

    def test_request_describes_the_charge(self, enabled, fake_urlopen):
        fake = fake_urlopen(body=json.dumps({'success': True}).encode('utf-8'))

        PosTerminalService.charge(120.75)

        req = fake.last_request
        assert req.full_url == 'http://127.0.0.1:9100/api/pos/charge'
        assert req.method == 'POST'
        assert req.get_header('Content-type') == 'application/json'
        assert req.get_header('Accept') == 'application/json'
        assert json.loads(req.data.decode('utf-8')) == {'amount': 120.75, 'currency': 'ILS'}
        assert fake.calls[-1]['timeout'] == 15

    def test_currency_defaults_to_ils(self, enabled, fake_urlopen):
        fake = fake_urlopen(body=json.dumps({'success': True}).encode('utf-8'))

        PosTerminalService.charge(10.0)

        assert json.loads(fake.last_request.data.decode('utf-8'))['currency'] == 'ILS'

    def test_an_explicit_currency_is_sent(self, enabled, fake_urlopen):
        fake = fake_urlopen(body=json.dumps({'success': True}).encode('utf-8'))

        PosTerminalService.charge(10.0, currency='USD')

        assert json.loads(fake.last_request.data.decode('utf-8')) == {
            'amount': 10.0,
            'currency': 'USD',
        }

    def test_a_trailing_slash_on_the_base_url_is_not_doubled(self, monkeypatch, fake_urlopen):
        monkeypatch.setenv('POS_ENABLED', '1')
        monkeypatch.setenv('POS_BASE_URL', 'http://127.0.0.1:9100/api/pos/')
        fake = fake_urlopen(body=json.dumps({'success': True}).encode('utf-8'))

        PosTerminalService.charge(10.0)

        assert fake.last_request.full_url == 'http://127.0.0.1:9100/api/pos/charge'

    def test_a_minimal_answer_falls_back_to_the_requested_values(self, enabled, fake_urlopen):
        """A terminal that answers ``{}`` still counts as an approval."""
        fake_urlopen(body=json.dumps({}).encode('utf-8'))

        result = PosTerminalService.charge(33.0, currency='EUR')

        assert result['success'] is True
        assert result['transaction_id'] is None
        assert result['approval_code'] is None
        assert result['card_last_digits'] is None
        assert result['card_holder_name'] is None
        assert result['message'] is None
        assert result['amount'] == 33.0
        assert result['currency'] == 'EUR'

    def test_a_declined_card_is_reported_as_a_decline(self, enabled, fake_urlopen):
        """The terminal answered 200 but declined the card.

        The result carries ``pos_declined``, which ``app/shared/pos_charge.py``
        maps to HTTP 402. Without the code the caller could not tell a decline
        from a terminal fault, and every decline was turned into a generic
        500.
        """
        body = json.dumps({'success': False, 'message': 'card declined'}).encode('utf-8')
        fake_urlopen(body=body)

        result = PosTerminalService.charge(42.5)

        assert result['success'] is False
        assert result['message'] == 'card declined'
        assert result['code'] == 'pos_declined'


class TestChargeFailures:
    """Every failure mode maps onto its own machine-readable code."""

    def test_http_error_from_the_terminal(self, enabled, fake_urlopen):
        exc = error.HTTPError(
            'http://127.0.0.1:9100/api/pos/charge',
            502,
            'Bad Gateway',
            {},
            None,
        )
        fake_urlopen(exc=exc)

        result = PosTerminalService.charge(10.0)

        assert result == {
            'success': False,
            'code': 'pos_terminal_error',
            'status': 502,
            'message': MSG_HTTP_ERROR,
        }

    def test_http_error_keeps_the_upstream_status_code(self, enabled, fake_urlopen):
        exc = error.HTTPError(
            'http://127.0.0.1:9100/api/pos/charge',
            503,
            'Service Unavailable',
            {},
            None,
        )
        fake_urlopen(exc=exc)

        result = PosTerminalService.charge(10.0)

        assert result['status'] == 503

    def test_http_error_is_not_mistaken_for_an_unreachable_terminal(self, enabled, fake_urlopen):
        """``HTTPError`` subclasses ``URLError``; the order of the handlers decides."""
        exc = error.HTTPError(
            'http://127.0.0.1:9100/api/pos/charge',
            500,
            'Internal Server Error',
            {},
            None,
        )
        fake_urlopen(exc=exc)

        result = PosTerminalService.charge(10.0)

        assert result['code'] == 'pos_terminal_error'
        assert result['code'] != 'pos_terminal_unreachable'

    def test_unreachable_terminal(self, enabled, fake_urlopen):
        fake_urlopen(exc=error.URLError('connection refused'))

        result = PosTerminalService.charge(10.0)

        assert result == {
            'success': False,
            'code': 'pos_terminal_unreachable',
            'message': MSG_UNREACHABLE,
        }

    def test_socket_timeout_is_reported_as_a_terminal_error(self, enabled, fake_urlopen):
        """A read timeout is not an ``URLError``, so it lands in the generic handler.

        ``urllib`` wraps a connection timeout into ``URLError`` -- which the
        service maps to ``pos_terminal_unreachable`` -- but a timeout while
        reading the response arrives as a bare ``TimeoutError`` and is
        classified as a terminal error instead.
        """
        fake_urlopen(exc=TimeoutError('timed out'))

        result = PosTerminalService.charge(10.0)

        assert result == {
            'success': False,
            'code': 'pos_terminal_error',
            'message': MSG_GENERIC_ERROR,
        }

    def test_a_malformed_answer_is_reported_as_a_terminal_error(self, enabled, fake_urlopen):
        """The terminal answered with something that is not JSON."""
        fake_urlopen(body=b'<html>gateway timeout</html>')

        result = PosTerminalService.charge(10.0)

        assert result == {
            'success': False,
            'code': 'pos_terminal_error',
            'message': MSG_GENERIC_ERROR,
        }

    def test_an_unexpected_exception_is_reported_as_a_terminal_error(self, enabled, fake_urlopen):
        fake_urlopen(exc=RuntimeError('terminal exploded'))

        result = PosTerminalService.charge(10.0)

        assert result == {
            'success': False,
            'code': 'pos_terminal_error',
            'message': MSG_GENERIC_ERROR,
        }

    def test_the_failure_result_never_leaks_the_raw_exception(self, enabled, fake_urlopen):
        """The upstream text must not reach the patient-facing payload."""
        fake_urlopen(exc=RuntimeError('internal detail about tenant 42'))

        result = PosTerminalService.charge(10.0)

        assert 'tenant 42' not in result['message']
        assert result['success'] is False
