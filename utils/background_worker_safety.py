"""
Background Worker Safety — wrappers for daemon threads to prevent silent failures
Ensures background jobs log errors, alert admins, and don't crash silently
"""

import contextlib
import logging
import traceback
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def safe_background_loop(
    func: Callable,
    *args,
    error_message: str = 'Background worker error',
    alert_sinks: list | None = None,
    max_consecutive_errors: int = 10,
    sleep_on_error: float = 5.0,
    **kwargs,
) -> Any:
    """
    Execute a background loop function with comprehensive error handling.

    Unlike bare `try/except: pass`, this logs full stack traces,
    optionally fires alert sinks, and implements error backoff.

    Args:
        func: The loop body function to call
        error_message: Prefix for error logs
        alert_sinks: List of callables(level, context_dict) for alerting
        max_consecutive_errors: After this many errors, back off longer
        sleep_on_error: Seconds to sleep after an error
        *args, **kwargs: Passed to func

    Returns:
        Whatever func returns (typically None for infinite loops)
    """
    consecutive_errors = 0
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        consecutive_errors += 1
        tb = traceback.format_exc()
        logger.error('%s: %s\n%s', error_message, exc, tb, exc_info=True)

        # Fire alert sinks if configured
        if alert_sinks:
            for sink in alert_sinks:
                with contextlib.suppress(Exception):
                    sink(
                        'CRITICAL',
                        {
                            'message': error_message,
                            'error': str(exc),
                            'traceback': tb,
                            'consecutive_errors': consecutive_errors,
                        },
                    )

        # Implement progressive backoff
        if consecutive_errors >= max_consecutive_errors:
            logger.critical(
                '%s: Max consecutive errors (%s) reached. Background worker may be unstable.',
                error_message,
                max_consecutive_errors,
            )
            import time

            time.sleep(sleep_on_error * 2)
        else:
            import time

            time.sleep(sleep_on_error)

        # Re-raise if caller wants to handle it
        raise


def background_worker_wrapper(
    error_message: str = 'Background worker error',
    alert_level: str = 'CRITICAL',
    log_traceback: bool = True,
):
    """
    Decorator for background worker loop functions.
    Wraps each iteration with error logging and optional alerting.

    Usage:
        @background_worker_wrapper(error_message="Notification processor error")
        def _run_loop():
            while True:
                ...
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if log_traceback:
                        tb = traceback.format_exc()
                        logger.exception('%s: %s\n%s')
                    else:
                        logger.exception('%s: %s')

                    # Try to alert admin if alert sinks exist
                    try:
                        from app_factory import _ALERT_SINKS

                        for sink in _ALERT_SINKS:
                            with contextlib.suppress(Exception):
                                sink(
                                    alert_level,
                                    {
                                        'message': error_message,
                                        'error': str(exc),
                                        'traceback': tb if log_traceback else None,
                                    },
                                )
                    except Exception:
                        pass

                    # Back off to prevent tight error loops
                    import time

                    time.sleep(5)

        return wrapper

    return decorator
