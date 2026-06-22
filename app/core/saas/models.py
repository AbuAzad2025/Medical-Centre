"""
SaaS Data Contracts — S0-003

Core entities for package versioning, subscription lines, and entitlement grants.
All tables are expand-only and coexist with the legacy ProductBundle/SubscriptionPlan
models via the LegacyEntitlementAdapter (to be implemented in S0-004).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from app_factory import db
from app.shared.mixins import TenantMixin


class PackageCategory:
    BUNDLE = "bundle"
    ADDON = "addon"
    STANDALONE = "standalone"


class SubscriptionLineType:
    BASE = "base"
    ADDON = "addon"


class SubscriptionLineStatus:
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENDED = "ended"


class PackageVersionAvailabilityStatus:
    AVAILABLE = "available"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class OverrideType:
    GRANT = "grant"
    REVOKE = "revoke"


class Package(db.Model):
    """A sellable product (bundle, add-on, or standalone module)."""
    __tablename__ = "packages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "category IN ('bundle', 'addon', 'standalone')",
            name="chk_package_category"
        ),
    )

    versions = db.relationship("PackageVersion", back_populates="package",
                               lazy="selectin", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "name_ar": self.name_ar,
            "slug": self.slug,
            "category": self.category,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PackageVersion(db.Model):
    """Immutable published version of a Package."""
    __tablename__ = "package_versions"

    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey("packages.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    version = db.Column(db.String(20), nullable=False)
    changelog = db.Column(db.Text, nullable=True)
    is_deprecated = db.Column(db.Boolean, default=False, nullable=False)
    retirement_date = db.Column(db.Date, nullable=True)
    published_at = db.Column(db.DateTime, nullable=False,
                             default=lambda: datetime.now(timezone.utc))

    # Lifecycle configuration (S0-005)
    trial_days = db.Column(db.Integer, default=0, nullable=False)
    grace_days = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("package_id", "version", name="uq_package_version"),
        CheckConstraint("trial_days >= 0", name="chk_package_version_trial_days_non_negative"),
        CheckConstraint("grace_days >= 0", name="chk_package_version_grace_days_non_negative"),
    )

    package = db.relationship("Package", back_populates="versions", lazy="selectin")
    entitlements = db.relationship("PackageVersionEntitlement", back_populates="package_version",
                                   lazy="selectin", cascade="all, delete-orphan")
    limits = db.relationship("PackageVersionLimit", back_populates="package_version",
                             lazy="selectin", cascade="all, delete-orphan")
    pricing = db.relationship("PackageVersionPricing", back_populates="package_version",
                              lazy="selectin", cascade="all, delete-orphan")
    availability_records = db.relationship("PackageVersionAvailability",
                                           back_populates="package_version",
                                           lazy="selectin", cascade="all, delete-orphan",
                                           order_by="PackageVersionAvailability.effective_from.desc()")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "package_id": self.package_id,
            "version": self.version,
            "changelog": self.changelog,
            "is_deprecated": self.is_deprecated,
            "retirement_date": self.retirement_date.isoformat() if self.retirement_date else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PackageVersionEntitlement(db.Model):
    """A capability granted by a specific package version."""
    __tablename__ = "package_version_entitlements"

    id = db.Column(db.Integer, primary_key=True)
    package_version_id = db.Column(db.Integer,
                                   db.ForeignKey("package_versions.id", ondelete="CASCADE"),
                                   nullable=False, index=True)
    module_name = db.Column(db.String(50), nullable=False, index=True)
    capability_key = db.Column(db.String(80), nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    package_version = db.relationship("PackageVersion", back_populates="entitlements",
                                      lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "package_version_id": self.package_version_id,
            "module_name": self.module_name,
            "capability_key": self.capability_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PackageVersionLimit(db.Model):
    """A usage limit defined by a package version."""
    __tablename__ = "package_version_limits"

    id = db.Column(db.Integer, primary_key=True)
    package_version_id = db.Column(db.Integer,
                                   db.ForeignKey("package_versions.id", ondelete="CASCADE"),
                                   nullable=False, index=True)
    limit_key = db.Column(db.String(50), nullable=False, index=True)
    limit_value = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("limit_value IS NULL OR limit_value >= 0",
                        name="chk_package_version_limit_value_non_negative"),
    )

    package_version = db.relationship("PackageVersion", back_populates="limits", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "package_version_id": self.package_version_id,
            "limit_key": self.limit_key,
            "limit_value": self.limit_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PackageVersionPricing(db.Model):
    """Pricing for a package version by billing type."""
    __tablename__ = "package_version_pricing"

    id = db.Column(db.Integer, primary_key=True)
    package_version_id = db.Column(db.Integer,
                                   db.ForeignKey("package_versions.id", ondelete="CASCADE"),
                                   nullable=False, index=True)
    billing_type = db.Column(db.String(10), nullable=False, index=True)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    setup_fee = db.Column(db.Numeric(12, 2), default=Decimal(0), nullable=False)
    currency = db.Column(db.String(3), default="SAR", nullable=False)

    __table_args__ = (
        CheckConstraint("billing_type IN ('monthly', 'yearly')",
                        name="chk_package_version_pricing_billing_type"),
        CheckConstraint("price >= 0", name="chk_package_version_pricing_price_non_negative"),
        CheckConstraint("setup_fee >= 0", name="chk_package_version_pricing_setup_fee_non_negative"),
    )

    package_version = db.relationship("PackageVersion", back_populates="pricing", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "package_version_id": self.package_version_id,
            "billing_type": self.billing_type,
            "price": float(self.price or 0),
            "setup_fee": float(self.setup_fee or 0),
            "currency": self.currency,
        }


class SubscriptionLine(TenantMixin, db.Model):
    """A single line in a tenant's subscription (base package or add-on)."""
    __tablename__ = "subscription_lines"
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    package_version_id = db.Column(db.Integer,
                                   db.ForeignKey("package_versions.id", ondelete="RESTRICT"),
                                   nullable=False, index=True)
    line_type = db.Column(db.String(10), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=SubscriptionLineStatus.SCHEDULED,
                       index=True)
    billing_type = db.Column(db.String(10), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    trial_end = db.Column(db.Date, nullable=True)

    effective_from = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    effective_to = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    current_period_start = db.Column(db.Date, nullable=True)
    current_period_end = db.Column(db.Date, nullable=True)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancellation_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("line_type IN ('base', 'addon')",
                        name="chk_subscription_line_type"),
        CheckConstraint("status IN ('scheduled', 'active', 'ended')",
                        name="chk_subscription_line_status"),
        CheckConstraint("billing_type IN ('monthly', 'yearly')",
                        name="chk_subscription_line_billing_type"),
        CheckConstraint("quantity > 0", name="chk_subscription_line_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_subscription_line_unit_price_non_negative"),
        Index("idx_subscription_line_tenant_status", "tenant_id", "status"),
        Index("idx_subscription_line_tenant_type", "tenant_id", "line_type"),
    )

    package_version = db.relationship("PackageVersion", lazy="selectin")
    entitlement_grants = db.relationship("EntitlementGrant", back_populates="subscription_line",
                                         lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "package_version_id": self.package_version_id,
            "line_type": self.line_type,
            "status": self.status,
            "billing_type": self.billing_type,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price or 0),
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "cancellation_date": self.cancellation_date.isoformat() if self.cancellation_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PackageVersionAvailability(db.Model):
    """Lifecycle history for a package version (available / deprecated / retired)."""
    __tablename__ = "package_version_availability"

    id = db.Column(db.Integer, primary_key=True)
    package_version_id = db.Column(db.Integer,
                                   db.ForeignKey("package_versions.id", ondelete="CASCADE"),
                                   nullable=False, index=True)
    availability_status = db.Column(db.String(20), nullable=False, index=True)
    effective_from = db.Column(db.DateTime, nullable=False)
    effective_to = db.Column(db.DateTime, nullable=True)
    deprecation_reason = db.Column(db.Text, nullable=True)
    retirement_reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "availability_status IN ('available', 'deprecated', 'retired')",
            name="chk_package_version_availability_status"
        ),
    )

    package_version = db.relationship("PackageVersion", back_populates="availability_records",
                                      lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "package_version_id": self.package_version_id,
            "availability_status": self.availability_status,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "deprecation_reason": self.deprecation_reason,
            "retirement_reason": self.retirement_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantOverride(TenantMixin, db.Model):
    """Explicit per-tenant entitlement override (grant or revoke)."""
    __tablename__ = "tenant_overrides"
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    module_name = db.Column(db.String(50), nullable=False, index=True)
    capability_key = db.Column(db.String(80), nullable=False, index=True)
    override_type = db.Column(db.String(10), nullable=False, index=True)
    reason = db.Column(db.Text, nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                           nullable=True, index=True)
    effective_from = db.Column(db.DateTime, nullable=False)
    effective_to = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("override_type IN ('grant', 'revoke')",
                        name="chk_tenant_override_type"),
        Index("idx_tenant_override_tenant_capability", "tenant_id", "capability_key"),
    )

    entitlement_grants = db.relationship("EntitlementGrant", back_populates="tenant_override",
                                         lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "module_name": self.module_name,
            "capability_key": self.capability_key,
            "override_type": self.override_type,
            "reason": self.reason,
            "granted_by": self.granted_by,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EnterpriseContract(TenantMixin, db.Model):
    """Enterprise contract that may grant additional capabilities."""
    __tablename__ = "enterprise_contracts"
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    contract_ref = db.Column(db.String(100), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    signed_by = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    entitlements = db.relationship("EnterpriseContractEntitlement",
                                   back_populates="enterprise_contract", lazy="selectin",
                                   cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "contract_ref": self.contract_ref,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "signed_by": self.signed_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EnterpriseContractEntitlement(db.Model):
    """Capability granted by an enterprise contract."""
    __tablename__ = "enterprise_contract_entitlements"

    id = db.Column(db.Integer, primary_key=True)
    enterprise_contract_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprise_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    capability_key = db.Column(db.String(80), nullable=False, index=True)
    effective_from = db.Column(db.DateTime, nullable=False)
    effective_to = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoke_reason = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    enterprise_contract = db.relationship("EnterpriseContract", back_populates="entitlements",
                                          lazy="selectin")
    entitlement_grants = db.relationship("EntitlementGrant",
                                         back_populates="enterprise_contract_entitlement",
                                         lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "enterprise_contract_id": self.enterprise_contract_id,
            "capability_key": self.capability_key,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoke_reason": self.revoke_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EntitlementGrant(TenantMixin, db.Model):
    """Traceable grant of a capability to a tenant from exactly one source."""
    __tablename__ = "entitlement_grants"
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    capability_key = db.Column(db.String(80), nullable=False, index=True)

    subscription_line_id = db.Column(
        db.Integer,
        db.ForeignKey("subscription_lines.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    tenant_override_id = db.Column(
        db.Integer,
        db.ForeignKey("tenant_overrides.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    tenant_feature_flag_id = db.Column(
        db.Integer,
        db.ForeignKey("tenant_feature_flags.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    enterprise_contract_entitlement_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprise_contract_entitlements.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    effective_from = db.Column(db.DateTime, nullable=False)
    effective_to = db.Column(db.DateTime, nullable=True)
    granted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                                   nullable=True)
    revoked_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                                   nullable=True)
    revocation_reason = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(subscription_line_id IS NOT NULL)::int + "
            "(tenant_override_id IS NOT NULL)::int + "
            "(tenant_feature_flag_id IS NOT NULL)::int + "
            "(enterprise_contract_entitlement_id IS NOT NULL)::int = 1",
            name="chk_entitlement_grant_single_source"
        ),
        Index("idx_entitlement_grant_tenant_capability", "tenant_id", "capability_key"),
    )

    subscription_line = db.relationship("SubscriptionLine", back_populates="entitlement_grants",
                                        lazy="selectin")
    tenant_override = db.relationship("TenantOverride", back_populates="entitlement_grants",
                                      lazy="selectin")
    enterprise_contract_entitlement = db.relationship(
        "EnterpriseContractEntitlement", back_populates="entitlement_grants", lazy="selectin"
    )
    granted_by = db.relationship("User", foreign_keys=[granted_by_user_id], lazy="selectin")
    revoked_by = db.relationship("User", foreign_keys=[revoked_by_user_id], lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "capability_key": self.capability_key,
            "subscription_line_id": self.subscription_line_id,
            "tenant_override_id": self.tenant_override_id,
            "tenant_feature_flag_id": self.tenant_feature_flag_id,
            "enterprise_contract_entitlement_id": self.enterprise_contract_entitlement_id,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "granted_by_user_id": self.granted_by_user_id,
            "revoked_by_user_id": self.revoked_by_user_id,
            "revocation_reason": self.revocation_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantEntitlement(TenantMixin, db.Model):
    """Materialized read-only projection of effective tenant capabilities."""
    __tablename__ = "tenant_entitlements"
    __tenant_migration__ = True

    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"),
                          primary_key=True)
    capability_key = db.Column(db.String(80), primary_key=True)
    module_name = db.Column(db.String(50), nullable=True)
    effective_from = db.Column(db.DateTime, nullable=False)
    effective_to = db.Column(db.DateTime, nullable=True)
    is_effective = db.Column(db.Boolean, default=True, nullable=False, index=True)
    source_summary = db.Column(db.Text, nullable=True)
    calculated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                              nullable=False)
    calculation_version = db.Column(db.Integer, default=1, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_tenant_entitlement_effective", "tenant_id", "is_effective"),
    )

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "capability_key": self.capability_key,
            "module_name": self.module_name,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "is_effective": self.is_effective,
            "source_summary": self.source_summary,
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None,
            "calculation_version": self.calculation_version,
        }
