"""
Security hardening middleware — headers, CSP, HSTS, rate-limit stubs
"""

import logging
import secrets

from flask import g, request

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Adds security headers to every response."""

    def init_app(self, app):
        @app.before_request
        def _generate_csp_nonce():
            """Generate a nonce for CSP inline scripts."""
            g.csp_nonce = secrets.token_urlsafe(16)

        @app.after_request
        def _add_headers(response):
            # Content Security Policy with nonce.
            # All third-party libraries are self-hosted in static/vendor/,
            # so no external script/style/connect sources are required.
            nonce = getattr(g, 'csp_nonce', '')
            # Fonts are fully self-hosted (static/vendor/fonts) — no external
            # style/font origins are whitelisted.
            csp = (
                "default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                f"style-src 'self' 'nonce-{nonce}'; "
                "img-src 'self' data: blob:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            response.headers['Content-Security-Policy'] = csp
            # Prevent MIME sniffing
            response.headers['X-Content-Type-Options'] = 'nosniff'
            # XSS protection
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            # HSTS (only in production with HTTPS)
            if not app.debug:
                response.headers['Strict-Transport-Security'] = (
                    'max-age=31536000; includeSubDomains'
                )
            # Referrer policy
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            # Permissions policy
            response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
            return response


class AuditLogMiddleware:
    """Logs every POST/PUT/DELETE to audit trail."""

    def init_app(self, app):
        @app.after_request
        def _audit(response):
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                try:
                    user_id = getattr(g, 'current_user_id', None)
                    tenant_id = getattr(g, 'tenant_id', None)
                    logger.info(
                        'AUDIT %s %s user=%s tenant=%s status=%s',
                        request.method,
                        request.path,
                        user_id,
                        tenant_id,
                        response.status_code,
                    )
                except Exception:
                    pass
            return response
