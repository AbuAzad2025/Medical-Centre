"""Coverage tests for utils.background_worker_safety.py.

The wrapper is a daemon loop: on an error it logs, alerts and calls the
function again, forever. A test that lets it swallow an exception therefore
never returns, so the loop is stopped with an exception that is not an
``Exception`` -- the wrapper only catches ``Exception``, so a ``BaseException``
passes straight through.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from utils.background_worker_safety import (
    background_worker_wrapper,
    safe_background_loop,
)


class _StopLoop(BaseException):
    """Breaks out of the wrapper's retry loop."""


class TestSafeBackgroundLoop:
    def test_success(self):
        def my_func():
            return 'done'

        result = safe_background_loop(my_func)
        assert result == 'done'

    def test_failure_re_raises(self):
        def my_func():
            raise ValueError('boom')

        with pytest.raises(ValueError):
            safe_background_loop(my_func, sleep_on_error=0)

    def test_with_args_kwargs(self):
        def my_func(a, b, c=None):
            return f'{a}-{b}-{c}'

        result = safe_background_loop(my_func, 'x', 'y', c='z')
        assert result == 'x-y-z'

    def test_with_alert_sinks(self):
        calls = []

        def sink(level, context):
            calls.append((level, context))

        def my_func():
            raise RuntimeError('test error')

        with pytest.raises(RuntimeError):
            safe_background_loop(
                my_func, error_message='test error', alert_sinks=[sink], sleep_on_error=0
            )

        assert len(calls) == 1
        assert calls[0][0] == 'CRITICAL'
        assert 'test error' in calls[0][1]['message']
        assert calls[0][1]['consecutive_errors'] == 1

    def test_a_failing_alert_sink_does_not_hide_the_error(self):
        def sink(level, context):
            raise RuntimeError('the alert sink is broken too')

        def my_func():
            raise RuntimeError('test error')

        with pytest.raises(RuntimeError, match='test error'):
            safe_background_loop(
                my_func, error_message='test error', alert_sinks=[sink], sleep_on_error=0
            )

    def test_max_consecutive_errors(self):
        call_count = [0]

        def my_func():
            call_count[0] += 1
            raise ValueError('boom')

        with pytest.raises(ValueError):
            safe_background_loop(my_func, max_consecutive_errors=1, sleep_on_error=0)
        assert call_count[0] == 1


class TestBackgroundWorkerWrapper:
    def test_wrapper_calls_func(self):
        call_count = [0]

        @background_worker_wrapper(error_message='test')
        def my_func():
            call_count[0] += 1
            return 'wrapped'

        result = my_func()
        assert result == 'wrapped'
        assert call_count[0] == 1

    def test_wrapper_retries_after_an_error(self):
        call_count = [0]

        @background_worker_wrapper(error_message='test', log_traceback=False)
        def my_func():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError('first attempt failed')
            return 'recovered'

        result = my_func()
        assert result == 'recovered'
        assert call_count[0] == 2

    def test_wrapper_logs_the_traceback_when_asked_to(self):
        call_count = [0]

        @background_worker_wrapper(error_message='test')
        def my_func():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError('first attempt failed')
            return 'recovered'

        result = my_func()
        assert result == 'recovered'
        assert call_count[0] == 2

    def test_a_non_exception_stops_the_loop(self):
        call_count = [0]

        @background_worker_wrapper(error_message='test')
        def my_func():
            call_count[0] += 1
            raise _StopLoop('stop the loop')

        with pytest.raises(_StopLoop):
            my_func()
        assert call_count[0] == 1

    def test_wrapper_alerts_the_configured_sinks(self):
        calls = []
        call_count = [0]

        def sink(level, context):
            calls.append((level, context))

        @background_worker_wrapper(error_message='test', log_traceback=False)
        def my_func():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError('first attempt failed')
            return 'recovered'

        with patch('app_factory._ALERT_SINKS', [sink]):
            result = my_func()

        assert result == 'recovered'
        assert calls
        assert calls[0][0] == 'CRITICAL'
        assert 'test' in calls[0][1]['message']

    def test_an_unreachable_alert_registry_does_not_stop_the_worker(self):
        import sys
        import types

        call_count = [0]
        empty_factory = types.ModuleType('app_factory')

        @background_worker_wrapper(error_message='test', log_traceback=False)
        def my_func():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError('first attempt failed')
            return 'recovered'

        with patch.dict(sys.modules, {'app_factory': empty_factory}):
            result = my_func()

        assert result == 'recovered'
        assert call_count[0] == 2
