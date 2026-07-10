"""
Centralized exception classes for the Medical System.
"""

class ModuleNotEnabledError(Exception):
    """Raised when a required module is not enabled for the current tenant."""
    
    def __init__(self, module_name: str, message: str | None = None):
        self.module_name = module_name
        self.message = message or f"Module '{module_name}' is not enabled for this tenant"
        super().__init__(self.message)


class TenantContextError(Exception):
    """Raised when tenant context is missing or invalid."""
    pass


class IdempotencyError(Exception):
    """Raised when an idempotency key conflict occurs."""
    pass


class InsufficientPermissionsError(Exception):
    """Raised when a user lacks required permissions."""
    pass


class ValidationError(Exception):
    """Raised when business validation fails."""
    pass