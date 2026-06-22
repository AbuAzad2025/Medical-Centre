"""SaaS entitlement exceptions."""


class EntitlementDeniedError(Exception):
    """Raised when a tenant is not entitled to a capability."""

    def __init__(self, tenant_id: int | None, capability_key: str, reason: str = ""):
        self.tenant_id = tenant_id
        self.capability_key = capability_key
        self.reason = reason
        message = f"Entitlement denied for tenant={tenant_id}, capability={capability_key}"
        if reason:
            message += f": {reason}"
        super().__init__(message)
