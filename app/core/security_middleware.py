"""
Security hardening middleware — headers, CSP, HSTS, rate-limit stubs
"""
import logging
from flask import request, g

logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware:
    """Adds security headers to every response."""

    def init_app(self, app):
        @app.after_request
        def _add_headers(response):
            # Content Security Policy
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net unpkg.com; "
                "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com cdnjs.cloudflare.com unpkg.com; "
                "img-src 'self' data: blob:; "
                "font-src 'self' fonts.gstatic.com; "
                "connect-src 'self' cdn.jsdelivr.net;"
            )
            # Prevent MIME sniffing
            response.headers['X-Content-Type-Options'] = 'nosniff'
            # XSS protection
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            # HSTS (only in production with HTTPS)
            if not app.debug:
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
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
                    tenant_id = getattr(g, 'current_tenant_id', None)
                    logger.info(
                        "AUDIT %s %s user=%s tenant=%s status=%s",
                        request.method, request.path, user_id, tenant_id, response.status_code
                    )
                except Exception:
                    pass
            return response
