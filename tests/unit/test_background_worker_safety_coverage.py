"""Coverage tests for utils.background_worker_safety.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from utils.background_worker_safety import (
    background_worker_wrapper,
    safe_background_loop,
)


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
            safe_background_loop(my_func)

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
                my_func, error_message='test error', alert_sinks=[sink]
            )

        assert len(calls) == 1
        assert calls[0][0] == 'CRITICAL'
        assert 'test error' in calls[0][1]['message']

    def test_max_consecutive_errors(self):
        call_count = [0]

        def my_func():
            call_count[0] += 1
            raise ValueError('boom')

        with pytest.raises(ValueError):
            safe_background_loop(
                my_func, max_consecutive_errors=1, sleep_on_error=0
            )
        assert call_count[0] == 1


class TestBackgroundWorkerWrapper:
    def test_wrapper_calls_func(self):
        call_count = [0]

        @background_worker_wrapper(error_message='test')
        def my_func():
            call_count[0] += 1
            if call_count[0] >= 1:
                return 'wrapped'

        result = my_func()
        assert result == 'wrapped'
        assert call_count[0] == 1

    def test_wrapper_log_traceback_false(self):
        call_count = [0]

        @background_worker_wrapper(error_message='test')
        def my_func():
            call_count[0] += 1
            if call_count[0] >= 1:
                raise ValueError('no traceback')

        with pytest.raises(ValueError):
            my_func()
        assert call_count[0] == 1
