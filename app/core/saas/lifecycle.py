"""
TenantProvisioningService — S0-005

Implements the tenant subscription lifecycle:
  provision → trial/active → upgrade/downgrade/add-on/renew
  → suspend → reactivate → cancel → (deleted after retention)
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.core.module.models import TenantModule
from app.core.tenant.models import (
    PlatformAuditLog,
    Tenant,
    TenantStatus,
    TenantSubscriptionHistory,
)
from app.core.saas.models import (
    EntitlementGrant,
    PackageVersion,
    PackageVersionAvailability,
    PackageVersionAvailabilityStatus,
    PackageVersionEntitlement,
    PackageVersionPricing,
    SubscriptionLine,
    SubscriptionLineStatus,
    SubscriptionLineType,
)
from app.core.saas.projection import EntitlementProjectionService


class ProvisioningError(Exception):
    """Raised when a provisioning action cannot be completed."""


class TenantProvisioningService:
    """High-level tenant provisioning and subscription lifecycle."""

    RETENTION_DAYS = 90

    @classmethod
    def provision_tenant(
        cls,
        slug: str,
        name: str,
        contact_email: str,
        package_version_id: int,
        billing_type: str,
        *,
        product_profile_code: Optional[str] = None,
        performed_by_user_id: Optional[int] = None,
        **tenant_kwargs,
    ) -> Tenant:
        """Create a new tenant with an active base subscription line."""
        if Tenant.query.filter_by(slug=slug).first():
            raise ProvisioningError(f"Tenant slug '{slug}' already exists.")

        package_version = cls._require_available_package_version(package_version_id)

        # Determine initial tenant status
        tenant_status = (
            TenantStatus.TRIAL
            if package_version.trial_days and package_version.trial_days > 0
            else TenantStatus.ACTIVE
        )

        tenant = Tenant(
            slug=slug,
            name=name,
            contact_email=contact_email,
            status=tenant_status,
            product_profile_code=product_profile_code
            or tenant_kwargs.get("product_profile_code"),
            **{k: v for k, v in tenant_kwargs.items() if k != "product_profile_code"},
        )
        db.session.add(tenant)
        db.session.flush()

        from flask import has_request_context
        if has_request_context():
            from app.core.tenant.middleware import bind_g_tenant
            bind_g_tenant(tenant)

        line = cls._create_base_line(tenant.id, package_version, billing_type)
        db.session.add(line)
        db.session.flush()

        cls._create_line_grants(line, package_version)
        db.session.commit()

        EntitlementProjectionService.calculate(tenant.id)
        cls._ensure_modules_for_package(tenant.id, package_version)
        cls._record_history(
            tenant.id,
            "ACTIVATE",
            notes=f"Provisioned with package_version={package_version_id}, billing={billing_type}",
            performed_by_user_id=performed_by_user_id,
        )
        cls._audit(
            tenant.id,
            "CREATE_TENANT",
            entity_type="tenant",
            entity_id=tenant.id,
            details=f"name={name}, package_version={package_version_id}, status={tenant_status.value}",
            user_id=performed_by_user_id,
        )
        cls._audit(
            tenant.id,
            "ACTIVATE",
            entity_type="tenant",
            entity_id=tenant.id,
            details=f"status={tenant_status.value}",
            user_id=performed_by_user_id,
        )
        return tenant

    @classmethod
    def upgrade_tenant(
        cls,
        tenant_id: int,
        new_package_version_id: int,
        billing_type: str,
        *,
        performed_by_user_id: Optional[int] = None,
    ) -> SubscriptionLine:
        """End current base line and create a new base line for the new package."""
        tenant = cls._require_tenant(tenant_id)
        new_version = cls._require_available_package_version(new_package_version_id)

        cls._end_current_base_line(tenant_id)
        new_line = cls._create_base_line(tenant.id, new_version, billing_type)
        db.session.add(new_line)
        db.session.flush()
        cls._create_line_grants(new_line, new_version)
        db.session.commit()

        EntitlementProjectionService.calculate(tenant.id)
        cls._ensure_modules_for_package(tenant.id, new_version)
        cls._record_history(
            tenant.id,
            "UPGRADE",
            notes=f"Upgraded to package_version={new_package_version_id}, billing={billing_type}",
            performed_by_user_id=performed_by_user_id,
        )
        cls._audit(
            tenant.id,
            "UPGRADE",
            entity_type="tenant",
            entity_id=tenant.id,
            details=f"package_version={new_package_version_id}, billing={billing_type}",
            user_id=performed_by_user_id,
        )
        return new_line

    @classmethod
    def downgrade_tenant(
        cls,
        tenant_id: int,
        new_package_version_id: int,
        billing_type: str,
        *,
        performed_by_user_id: Optional[int] = None,
    ) -> SubscriptionLine:
        """End current base line and create a new restricted base line."""
        tenant = cls._require_tenant(tenant_id)
        new_version = cls._require_available_package_version(new_package_version_id)

        cls._end_current_base_line(tenant_id)
        new_line = cls._create_base_line(tenant.id, new_version, billing_type)
        db.session.add(new_line)
        db.session.flush()
        cls._create_line_grants(new_line, new_version)
        db.session.commit()

        EntitlementProjectionService.calculate(tenant.id)
        # Historical data remains readable; creation is restricted via entitlement resolver.
        cls._record_history(
            tenant.id,
            "DOWNGRADE",
            notes=f"Downgraded to package_version={new_package_version_id}, billing={billing_type}",
            performed_by_user_id=performed_by_user_id,
        )
        cls._audit(
            tenant.id,
            "DOWNGRADE",
            entity_type="tenant",
            entity_id=tenant.id,
            details=f"package_version={new_package_version_id}, billing={billing_type}",
            user_id=performed_by_user_id,
        )
        return new_line

    @classmethod
    def add_addon(
        cls,
        tenant_id: int,
        package_version_id: int,
        billing_type: str,
        *,
        quantity: int = 1,
        performed_by_user_id: Optional[int] = None,
    ) -> SubscriptionLine:
        """Add an add-on subscription line to an active tenant."""
        tenant = cls._require_tenant(tenant_id)
        version = cls._require_available_package_version(package_version_id)

        line = cls._create_line(
            tenant.id,
            version,
            SubscriptionLineType.ADDON,
            billing_type,
            quantity=quantity,
        )
        db.session.add(line)
        db.session.flush()
        cls._create_line_grants(line, version)
        db.session.commit()

        EntitlementProjectionService.calculate(tenant.id)
        cls._ensure_modules_for_package(tenant.id, version)
        cls._record_history(
            tenant.id,
            "ADD_ON",
            notes=f"Add-on package_version={package_version_id}, billing={billing_type}",
            performed_by_user_id=performed_by_user_id,
        )
        cls._audit(
            tenant.id,
            "ADD_ON",
            entity_type="tenant",
            entity_id=tenant.id,
            details=f"package_version={package_version_id}, billing={billing_type}",
            user_id=performed_by_user_id,
        )
        return line

    @classmethod
    def renew_base_line(
        cls,
        line_id: int,
        periods: int = 1,
        *,
        performed_by_user_id: Optional[int] = None,
    ) -> SubscriptionLine:
        """Extend the current period of an active base line."""
        line = SubscriptionLine.query.get(line_id)
        if not line or line.line_type != SubscriptionLineType.BASE:
            raise ProvisioningError("Active base subscription line not found.")

        delta = cls._billing_delta(line.billing_type, periods)
        if line.effective_to:
            line.effective_to = line.effective_to + delta
        if line.current_period_end:
            line.current_period_end = line.current_period_end + delta

        # Extend grant effective dates with the line
        line_effective_to_naive = cls._utc_naive(line.effective_to)
        for grant in line.entitlement_grants:
            grant_effective_to_naive = cls._utc_naive(grant.effective_to)
            if line_effective_to_naive and (
                grant_effective_to_naive is None or grant_effective_to_naive < line_effective_to_naive
            ):
                grant.effective_to = line.effective_to

        db.session.commit()
        EntitlementProjectionService.calculate(line.tenant_id)
        cls._record_history(
            line.tenant_id,
            "RENEW",
            notes=f"Renewed subscription_line={line_id} by {periods} period(s)",
            performed_by_user_id=performed_by_user_id,
        )
        cls._audit(
            line.tenant_id,
            "RENEW",
            entity_type="subscription_line",
            entity_id=line.id,
            details=f"periods={periods}, effective_to={line.effective_to}",
            user_id=performed_by_user_id,
        )
        return line

    @classmethod
    def suspend_tenant(
        cls,
        tenant_id: int,
        reason: str,
        *,
        performed_by_user_id: Optional[int] = None,
    ) -> Tenant:
        tenant = cls._require_tenant(tenant_id)
        tenant.status = TenantStatus.SUSPENDED
        db.session.commit()
        EntitlementProjectionService.calculate(tenant.id)
        cls._record_history(
            tenant.id,
            "SUSPEND",
            notes=f"reason={reason}",
            performed_by_user_id=performed_by_user_id,
        )
        cls._audit(
            tenant.id,
            "SUSPEND",
            entity_type="tenant",
            entity_id=tenant.id,
            details=f"reason={reason}",
            user_id=performed_by_user_id,
        )
        return tenant

    @classmethod
    def reactivate_tenant(
        cls,
        tenant_id: int,
        *,
        performed_by_user_id: Optional[int] = None,
    ) -> Tenant:
        tenant = cls._require_tenant(tenant_id)
        if tenant.status != TenantStatus.SUSPENDED:
            raise ProvisioningError("Only suspended tenants can be reactivated.")
        tenant.status = TenantStatus.ACTIVE
        db.session.commit()
        EntitlementProjectionService.calculate(tenant.id)
        cls._record_history(
            tenant.id,
            "REACTIVATE",
            performed_by_user_id=performed_by_user_id,
        )
        cls._audit(
            tenant.id,
            "REACTIVATE",
            entity_type="tenant",
            entity_id=tenant.id,
            user_id=performed_by_user_id,
        )
        return tenant

    @classmethod
    def cancel_tenant(
        cls,
        tenant_id: int,
        *,
        performed_by_user_id: Optional[int] = None,
    ) -> Tenant:
        """Cancel tenant and end all subscription lines. Deletion happens later."""
        tenant = cls._require_tenant(tenant_id)
        tenant.status = TenantStatus.CANCELLED

        now = datetime.now(timezone.utc)
        lines = SubscriptionLine.query.filter_by(tenant_id=tenant_id).all()
        for line in lines:
            line.status = SubscriptionLineStatus.ENDED
            line.effective_to = now
            line.ended_at = now
            line.cancellation_date = date.today()

        db.session.commit()
        EntitlementProjectionService.calculate(tenant.id)
        cls._record_history(
            tenant.id,
            "CANCEL",
            performed_by_user_id=performed_by_user_id,
        )
        cls._audit(
            tenant.id,
            "CANCEL",
            entity_type="tenant",
            entity_id=tenant.id,
            user_id=performed_by_user_id,
        )
        return tenant

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _require_tenant(cls, tenant_id: int) -> Tenant:
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            raise ProvisioningError(f"Tenant {tenant_id} not found.")
        return tenant

    @classmethod
    def _require_available_package_version(cls, package_version_id: int) -> PackageVersion:
        version = PackageVersion.query.get(package_version_id)
        if not version:
            raise ProvisioningError(f"PackageVersion {package_version_id} not found.")
        if version.is_deprecated:
            raise ProvisioningError(f"PackageVersion {package_version_id} is deprecated.")
        latest_availability = (
            PackageVersionAvailability.query.filter_by(package_version_id=version.id)
            .order_by(PackageVersionAvailability.effective_from.desc())
            .first()
        )
        if latest_availability and latest_availability.availability_status == PackageVersionAvailabilityStatus.RETIRED:
            raise ProvisioningError(f"PackageVersion {package_version_id} is retired.")
        return version

    @classmethod
    def _billing_delta(cls, billing_type: str, periods: int = 1) -> relativedelta:
        if billing_type == "yearly":
            return relativedelta(years=periods)
        return relativedelta(months=periods)

    @classmethod
    def _create_base_line(
        cls,
        tenant_id: int,
        package_version: PackageVersion,
        billing_type: str,
    ) -> SubscriptionLine:
        return cls._create_line(
            tenant_id,
            package_version,
            SubscriptionLineType.BASE,
            billing_type,
        )

    @classmethod
    def _create_line(
        cls,
        tenant_id: int,
        package_version: PackageVersion,
        line_type: str,
        billing_type: str,
        *,
        quantity: int = 1,
    ) -> SubscriptionLine:
        now = datetime.now(timezone.utc)
        effective_to = now + cls._billing_delta(billing_type)

        pricing = PackageVersionPricing.query.filter_by(
            package_version_id=package_version.id, billing_type=billing_type
        ).first()
        unit_price = pricing.price if pricing else Decimal(0)

        trial_end = None
        if line_type == SubscriptionLineType.BASE and package_version.trial_days:
            trial_end = now.date() + timedelta(days=package_version.trial_days)

        return SubscriptionLine(
            tenant_id=tenant_id,
            package_version_id=package_version.id,
            line_type=line_type,
            status=SubscriptionLineStatus.ACTIVE,
            billing_type=billing_type,
            quantity=quantity,
            unit_price=unit_price,
            trial_end=trial_end,
            effective_from=now,
            effective_to=effective_to,
            current_period_start=now.date(),
            current_period_end=effective_to.date(),
        )

    @classmethod
    def _create_line_grants(
        cls, line: SubscriptionLine, package_version: PackageVersion
    ) -> None:
        entitlements = PackageVersionEntitlement.query.filter_by(
            package_version_id=package_version.id
        ).all()
        for entitlement in entitlements:
            grant = EntitlementGrant(
                tenant_id=line.tenant_id,
                capability_key=entitlement.capability_key,
                subscription_line_id=line.id,
                effective_from=cls._utc_naive(line.effective_from),
                effective_to=cls._utc_naive(line.effective_to),
            )
            db.session.add(grant)

    @staticmethod
    def _utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    @classmethod
    def _end_current_base_line(cls, tenant_id: int) -> None:
        now = datetime.now(timezone.utc)
        active_base = (
            SubscriptionLine.query.filter_by(
                tenant_id=tenant_id,
                line_type=SubscriptionLineType.BASE,
                status=SubscriptionLineStatus.ACTIVE,
            )
            .filter(
                (SubscriptionLine.effective_to.is_(None))
                | (SubscriptionLine.effective_to >= now)
            )
            .first()
        )
        if active_base:
            active_base.status = SubscriptionLineStatus.ENDED
            active_base.effective_to = now
            active_base.ended_at = now

    @classmethod
    def _ensure_modules_for_package(
        cls, tenant_id: int, package_version: PackageVersion
    ) -> None:
        module_names = {
            ent.module_name
            for ent in PackageVersionEntitlement.query.filter_by(
                package_version_id=package_version.id
            ).all()
        }
        for module_name in module_names:
            existing = TenantModule.query.filter_by(
                tenant_id=tenant_id, module_name=module_name
            ).first()
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    existing.activated_at = datetime.now(timezone.utc)
                    existing.deactivated_at = None
                continue
            tm = TenantModule(
                tenant_id=tenant_id,
                module_name=module_name,
                is_active=True,
                activated_at=datetime.now(timezone.utc),
            )
            db.session.add(tm)
        db.session.commit()

    @classmethod
    def _record_history(
        cls,
        tenant_id: int,
        action: str,
        *,
        notes: Optional[str] = None,
        performed_by_user_id: Optional[int] = None,
    ) -> None:
        history = TenantSubscriptionHistory(
            tenant_id=tenant_id,
            action=action,
            notes=notes,
            performed_by=performed_by_user_id,
        )
        db.session.add(history)
        db.session.commit()

    @classmethod
    def _audit(
        cls,
        tenant_id: int,
        action: str,
        *,
        entity_type: str,
        entity_id: Optional[int] = None,
        details: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> None:
        log = PlatformAuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.session.add(log)
        db.session.commit()
