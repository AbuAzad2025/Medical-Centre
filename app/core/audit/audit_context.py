import contextvars
from contextlib import contextmanager

audit_actor_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    'audit_actor_id', default=None
)
audit_ip_address: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'audit_ip_address', default=None
)
audit_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'audit_request_id', default=None
)
audit_tenant_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    'audit_tenant_id', default=None
)


def set_audit_context(actor_id=None, ip_address=None, request_id=None, tenant_id=None):
    audit_actor_id.set(actor_id)
    audit_ip_address.set(ip_address)
    audit_request_id.set(request_id)
    audit_tenant_id.set(tenant_id)


@contextmanager
def audit_tenant_scope(tenant_id: int | None):
    """Set the audit context's tenant for the duration of the block.

    A ContextVar has to be reset, not just overwritten: a caller that sets the
    audit tenant to another tenant's id and leaves it there makes every later
    audit row name that tenant, and the WITH CHECK policy on the audit tables
    rejects the row - which leaves the session in a failed state and every
    statement after it failing for a reason that has nothing to do with the
    audit.

    Restoring the previous value is what keeps the scope a scope.
    """
    token = audit_tenant_id.set(tenant_id)
    try:
        yield
    finally:
        audit_tenant_id.reset(token)


def get_audit_context():
    return {
        'actor_id': audit_actor_id.get(),
        'ip_address': audit_ip_address.get(),
        'request_id': audit_request_id.get(),
        'tenant_id': audit_tenant_id.get(),
    }


class AuditContextMiddleware:
    def init_app(self, app):
        @app.before_request
        def _populate_audit_context():
            from flask import g, request
            from flask_login import current_user

            actor_id = None
            ghost_user = getattr(g, 'current_user', None)
            if ghost_user is not None and ghost_user.is_authenticated:
                actor_id = ghost_user.id
            elif current_user.is_authenticated:
                actor_id = current_user.id

            set_audit_context(
                actor_id=actor_id,
                ip_address=request.remote_addr,
                request_id=getattr(g, 'trace_id', None),
                tenant_id=getattr(g, 'tenant_id', None),
            )
