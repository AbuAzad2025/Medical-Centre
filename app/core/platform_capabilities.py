"""Platform-wide capability flags — hide incomplete integrations until ready."""
from __future__ import annotations

import os
from functools import wraps
from typing import Callable

_TRUTHY = frozenset(('true', 'on', '1', 'yes'))

_CAP_ENV: dict[str, str] = {
    'sms_live': 'PLATFORM_CAP_SMS_LIVE',
    'webauthn': 'PLATFORM_CAP_WEBAUTHN',
    'fhir_api': 'PLATFORM_CAP_FHIR',
    'sso': 'PLATFORM_CAP_SSO',
}


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in _TRUTHY


def platform_capability(name: str) -> bool:
    env_name = _CAP_ENV.get(name)
    if env_name is None:
        return False
    return env_bool(env_name, False)


def get_capabilities() -> dict[str, bool]:
    return {name: platform_capability(name) for name in _CAP_ENV}


CAPABILITIES = {name: env_bool(env_name, False) for name, env_name in _CAP_ENV.items()}


def require_platform_capability(cap: str) -> Callable:
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import abort
            if not platform_capability(cap):
                abort(404)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def guard_platform_capability(cap: str) -> None:
    from flask import abort
    if not platform_capability(cap):
        abort(404)
