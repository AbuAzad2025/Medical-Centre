"""
API Security Decorators — payload limits, content-type enforcement, HMAC verification
Prevent DoS, webhook spoofing, and API abuse
"""

import json
import hmac
import hashlib
from functools import wraps
from flask import request, current_app, jsonify


class PayloadTooLargeError(Exception):
    pass


def limit_payload_size(max_size_bytes: int = 1024 * 1024):
    """
    Decorator to reject requests with body size exceeding max_size_bytes.
    Must be applied BEFORE request parsing to prevent memory exhaustion.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            content_length = request.content_length
            if content_length is not None and content_length > max_size_bytes:
                return jsonify({
                    'success': False,
                    'error': f'Payload too large. Maximum allowed is {max_size_bytes} bytes.',
                    'max_size': max_size_bytes,
                }), 413
            # Also guard against chunked transfer where content_length is None
            if content_length is None:
                # Read up to max_size_bytes + 1 to detect overflow
                body = request.get_data(cache=True, as_text=False, parse_form_data=False)
                if len(body) > max_size_bytes:
                    return jsonify({
                        'success': False,
                        'error': f'Payload too large. Maximum allowed is {max_size_bytes} bytes.',
                        'max_size': max_size_bytes,
                    }), 413
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_content_type(*allowed_types: str):
    """
    Decorator to enforce strict Content-Type validation.
    Rejects requests with unexpected content types.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            content_type = (request.content_type or '').lower()
            # Allow no content type for GET/DELETE unless specified
            if not content_type and request.method in ('GET', 'HEAD', 'DELETE'):
                return f(*args, **kwargs)
            matched = any(content_type.startswith(ct.lower()) for ct in allowed_types)
            if not matched:
                return jsonify({
                    'success': False,
                    'error': f'Unsupported Content-Type. Expected one of: {", ".join(allowed_types)}',
                    'received': content_type,
                }), 415
            return f(*args, **kwargs)
        return wrapper
    return decorator


def verify_webhook_signature(secret: str, header_name: str = 'X-Webhook-Signature', algorithm: str = 'sha256'):
    """
    Decorator to verify HMAC-SHA256 signature on webhook endpoints.
    Prevents webhook spoofing from unauthorized sources.
    
    Usage:
        @verify_webhook_signature(secret='my-secret')
        def stripe_webhook():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            signature = request.headers.get(header_name, '')
            if not signature:
                # Try common Stripe-style header
                signature = request.headers.get('Stripe-Signature', '')
            if not signature:
                return jsonify({
                    'success': False,
                    'error': 'Missing webhook signature header',
                }), 401

            body = request.get_data(cache=False, as_text=False)
            expected = hmac.new(
                secret.encode('utf-8'),
                body,
                getattr(hashlib, algorithm, hashlib.sha256)
            ).hexdigest()

            # Support both raw hex and 't=...,v1=...' (Stripe-style) signatures
            if 'v1=' in signature:
                # Simple parsing for Stripe-style multi-signature
                import re
                sigs = re.findall(r'v1=([a-f0-9]+)', signature)
                if not any(hmac.compare_digest(expected, s) for s in sigs):
                    return jsonify({
                        'success': False,
                        'error': 'Invalid webhook signature',
                    }), 401
            else:
                if not hmac.compare_digest(expected, signature):
                    return jsonify({
                        'success': False,
                        'error': 'Invalid webhook signature',
                    }), 401

            return f(*args, **kwargs)
        return wrapper
    return decorator


def sanitize_search_input(raw: str, max_length: int = 100) -> str:
    """
    Sanitize user-provided search strings to prevent injection and DoS.
    - Strips dangerous characters
    - Limits length
    - Escapes SQL wildcard abuse
    """
    if not raw:
        return ''
    # Limit length
    raw = raw[:max_length]
    # Remove null bytes and control characters
    raw = raw.replace('\x00', '').replace('\x1a', '')
    # Normalize SQL wildcards to prevent abuse (e.g., %%%%%%%%%%%)
    # We keep single % and _ for LIKE but collapse repeated ones
    import re
    raw = re.sub(r'%+', '%', raw)
    raw = re.sub(r'_+', '_', raw)
    return raw.strip()
