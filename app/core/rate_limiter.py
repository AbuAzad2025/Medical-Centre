"""
Simple in-memory rate limiter for API routes
Can be replaced with Redis in production
"""
import time
import logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

class RateLimiter:
    """In-memory sliding-window rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._store = {}

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window
        timestamps = self._store.get(key, [])
        # Keep only timestamps within window
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= self.max_requests:
            self._store[key] = timestamps
            return False
        timestamps.append(now)
        self._store[key] = timestamps
        return True

    def clear(self):
        self._store.clear()


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """Decorator to rate-limit a route by IP + endpoint."""
    limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = f"{request.remote_addr}:{request.endpoint}"
            if not limiter.is_allowed(key):
                return jsonify({'success': False, 'message': 'Too many requests'}), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator
