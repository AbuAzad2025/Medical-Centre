"""
External Request Timeout Utility — enforce timeouts on all outbound HTTP calls
Prevents indefinite hangs when Stripe, Twilio, WhatsApp, or FHIR servers are slow/unreachable
"""

import logging
import time
from functools import wraps

import requests

logger = logging.getLogger(__name__)

# Default timeouts (connect, read) in seconds
DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 15.0)
# Aggressive timeouts for non-critical calls
FAST_TIMEOUT: tuple[float, float] = (3.0, 5.0)
# Lenient timeouts for large payload operations (e.g., DICOM upload)
LARGE_PAYLOAD_TIMEOUT: tuple[float, float] = (10.0, 60.0)


def safe_request(
    method: str,
    url: str,
    timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    retries: int = 1,
    retry_backoff: float = 1.0,
    **kwargs,
) -> requests.Response:
    """
    Wrapper around requests.request with mandatory timeout and basic retry logic.

    Args:
        method: HTTP method
        url: Target URL
        timeout: (connect_timeout, read_timeout) tuple
        retries: Number of retries on timeout/connection error
        retry_backoff: Seconds to wait between retries
        **kwargs: Passed to requests.request

    Returns:
        requests.Response

    Raises:
        requests.Timeout: If all retries exhausted
        requests.ConnectionError: If connection fails after retries
    """
    last_exception = None
    for attempt in range(retries + 1):
        try:
            return requests.request(method, url, timeout=timeout, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exception = exc
            if attempt < retries:
                wait = retry_backoff * (attempt + 1)
                logger.warning(
                    'Request %s %s timeout (attempt %s/%s), retrying in %ss: %s',
                    method,
                    url,
                    attempt + 1,
                    retries + 1,
                    wait,
                    exc,
                )
                time.sleep(wait)
            else:
                logger.exception(
                    'Request %s %s failed after %s attempts: %s', method, url, retries + 1, exc
                )
                raise
    raise last_exception


def safe_get(
    url: str, timeout: tuple[float, float] = DEFAULT_TIMEOUT, **kwargs
) -> requests.Response:
    """Convenience GET with safe timeout."""
    return safe_request('GET', url, timeout=timeout, **kwargs)


def safe_post(
    url: str, timeout: tuple[float, float] = DEFAULT_TIMEOUT, **kwargs
) -> requests.Response:
    """Convenience POST with safe timeout."""
    return safe_request('POST', url, timeout=timeout, **kwargs)


def safe_put(
    url: str, timeout: tuple[float, float] = DEFAULT_TIMEOUT, **kwargs
) -> requests.Response:
    """Convenience PUT with safe timeout."""
    return safe_request('PUT', url, timeout=timeout, **kwargs)


def safe_delete(
    url: str, timeout: tuple[float, float] = DEFAULT_TIMEOUT, **kwargs
) -> requests.Response:
    """Convenience DELETE with safe timeout."""
    return safe_request('DELETE', url, timeout=timeout, **kwargs)


def with_timeout(timeout: tuple[float, float] = DEFAULT_TIMEOUT, retries: int = 1):
    """
    Decorator to enforce timeout on any function that makes HTTP calls.
    Useful for wrapping service methods.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Inject timeout into kwargs if the function accepts it
            if 'timeout' not in kwargs:
                kwargs['timeout'] = timeout
            if 'retries' not in kwargs:
                kwargs['retries'] = retries
            return func(*args, **kwargs)

        return wrapper

    return decorator
