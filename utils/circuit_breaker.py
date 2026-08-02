"""
Circuit Breaker — resilience pattern for external service calls
Prevents cascade failures when Stripe, Twilio, WhatsApp, or other APIs are down
"""

import logging
import threading
import time
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = 'closed'  # Normal operation
    OPEN = 'open'  # Failing fast
    HALF_OPEN = 'half_open'  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is OPEN and a call is attempted."""

    def __init__(self, service_name: str, last_error: str | None = None):
        self.service_name = service_name
        self.last_error = last_error
        super().__init__(f'Circuit breaker OPEN for {service_name}. Last error: {last_error}')


class CircuitBreaker:
    """
    Thread-safe circuit breaker for external API calls.

    Configurable thresholds:
    - failure_threshold: number of failures before opening
    - recovery_timeout: seconds to wait before half-open
    - half_open_max_calls: number of test calls in half-open state
    - success_threshold: consecutive successes to close
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
        expected_exception: type = Exception,
        fallback: Callable | None = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold
        self.expected_exception = expected_exception
        self.fallback = fallback

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float | None = None
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if (
                    self._last_failure_time
                    and (time.time() - self._last_failure_time) >= self.recovery_timeout
                ):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._success_count = 0
                    logger.info('Circuit breaker %s moved to HALF_OPEN', self.name)
            return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute func with circuit breaker protection."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            if self.fallback:
                logger.warning('Circuit breaker %s OPEN — executing fallback', self.name)
                return self.fallback(*args, **kwargs)
            raise CircuitBreakerError(
                self.name, last_error=f'Circuit has been open since {self._last_failure_time}'
            )

        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerError(self.name, last_error='Half-open call limit reached')
                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as exc:
            self._record_failure(str(exc))
            raise

    def _record_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info('Circuit breaker %s CLOSED after recovery', self.name)
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            else:
                self._failure_count = max(0, self._failure_count - 1)

    def _record_failure(self, error_str: str):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    'Circuit breaker %s OPEN after half-open failure: %s', self.name, error_str
                )
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                logger.error(
                    'Circuit breaker %s OPEN after %s failures: %s',
                    self.name,
                    self._failure_count,
                    error_str,
                )
                self._state = CircuitState.OPEN

    def reset(self):
        """Manually reset the circuit breaker to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            logger.info('Circuit breaker %s manually reset to CLOSED', self.name)


# Global registry for named circuit breakers
_breakers: dict = {}
_breaker_lock = threading.Lock()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    with _breaker_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name=name, **kwargs)
        return _breakers[name]


def circuit_breaker_call(name: str, func: Callable, *args, **kwargs) -> Any:
    """Convenience: call func through a named circuit breaker."""
    breaker = get_circuit_breaker(name)
    return breaker.call(func, *args, **kwargs)


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    fallback: Callable | None = None,
):
    """Decorator to wrap a function with circuit breaker protection."""
    breaker = get_circuit_breaker(
        name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        fallback=fallback,
    )

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator
