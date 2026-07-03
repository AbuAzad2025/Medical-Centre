"""Platform tenant assumption service (MC-005).

Allows platform users (super_admin, owner) to explicitly and audibly
assume a tenant identity for cross-tenant operations.
"""
from datetime import datetime, timezone
from flask import g
from app.extensions import db
from app.core.tenant.models import PlatformTenantAssumption


PLATFORM_ROLES = frozenset({"super_admin", "owner"})


class PlatformAssumptionError(PermissionError):
    pass


class PlatformAssumptionService:

    @staticmethod
    def create_assumption(
        user_id: int,
        assumed_tenant_id: int,
        reason: str,
        *,
        assumed_by: int | None = None,
        expires_at: datetime | None = None,
    ) -> PlatformTenantAssumption:
        if not reason or len(reason.strip()) < 10:
            raise PlatformAssumptionError("Reason must be at least 10 characters")

        assumption = PlatformTenantAssumption(
            user_id=user_id,
            assumed_tenant_id=assumed_tenant_id,
            assumed_by=assumed_by or user_id,
            reason=reason.strip(),
            is_active=True,
            expires_at=expires_at,
        )
        db.session.add(assumption)
        db.session.commit()
        return assumption

    @staticmethod
    def revoke_assumption(
        assumption_id: int,
        revoked_by: int,
        revoke_reason: str,
    ) -> PlatformTenantAssumption | None:
        assumption = db.session.get(PlatformTenantAssumption, assumption_id)
        if not assumption:
            return None
        if not assumption.is_active:
            return assumption

        assumption.is_active = False
        assumption.revoked_at = datetime.now(timezone.utc)
        assumption.revoked_by = revoked_by
        assumption.revoke_reason = revoke_reason
        db.session.commit()
        return assumption

    @staticmethod
    def has_valid_assumption(user_id: int, tenant_id: int) -> bool:
        now = datetime.now(timezone.utc)
        return db.session.query(
            PlatformTenantAssumption.query.filter(
                PlatformTenantAssumption.user_id == user_id,
                PlatformTenantAssumption.assumed_tenant_id == tenant_id,
                PlatformTenantAssumption.is_active == True,
            ).filter(
                db.or_(
                    PlatformTenantAssumption.expires_at.is_(None),
                    PlatformTenantAssumption.expires_at > now,
                )
            ).exists()
        ).scalar()

    @staticmethod
    def get_active_assumptions(user_id: int | None = None) -> list[PlatformTenantAssumption]:
        q = PlatformTenantAssumption.query.filter_by(is_active=True)
        if user_id is not None:
            q = q.filter_by(user_id=user_id)
        now = datetime.now(timezone.utc)
        q = q.filter(
            db.or_(
                PlatformTenantAssumption.expires_at.is_(None),
                PlatformTenantAssumption.expires_at > now,
            )
        )
        return q.order_by(PlatformTenantAssumption.created_at.desc()).all()

    @staticmethod
    def is_platform_user() -> bool:
        from flask_login import current_user
        return current_user.is_authenticated and getattr(current_user, 'role', None) in PLATFORM_ROLES

    @staticmethod
    def enforce_tenant_access() -> None:
        """Middleware hook: abort 403 if authenticated user does not match resolved tenant."""
        from flask import abort, request
        from flask_login import current_user
        import sys as _sys
        from flask import session as _sess
        print(f"[enforce] current_user={current_user} auth={current_user.is_authenticated} _id_in_sess={_sess.get('_id')!r} _uid_in_sess={_sess.get('_user_id')!r}", file=_sys.stderr)

        if not current_user.is_authenticated:
            return

        user_tenant_id = getattr(current_user, 'tenant_id', None)
        current_tenant_id = g.get('tenant_id')

        if current_tenant_id is None:
            return

        user_id = current_user.id
        role = getattr(current_user, 'role', None)

        if user_tenant_id is not None and user_tenant_id == current_tenant_id:
            return

        if role in PLATFORM_ROLES and PlatformAssumptionService.has_valid_assumption(user_id, current_tenant_id):
            return

        abort(403, description="Cross-tenant access denied — use explicit tenant assumption")
