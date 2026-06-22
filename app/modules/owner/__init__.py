"""
Owner (Cloud Control Plane) — platform-level administration

S0-007 Platform Owner Console Security Contract:

1. Strict separation: platform-owner ≠ tenant-admin. Owner routes require
   `owner_required` (super_admin/admin/owner roles) and live under /owner/.
2. Tenant provisioning, package override management, and subscription
   administration are performed through this module only.
3. Emergency system switches (from P0E-001) are owner-accessible.
4. Support impersonation, if implemented, MUST require:
   - an explicit reason,
   - a time-bound session,
   - a visible banner in the impersonated UI,
   - an immutable audit trail entry,
   - no silent access.
5. All denied owner-area attempts and sensitive mutations are logged to
   PlatformAuditLog.
"""
from flask import Blueprint

owner_bp = Blueprint("owner", __name__)

from app.modules.owner import routes
