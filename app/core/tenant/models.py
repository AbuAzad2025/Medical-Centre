"""
Tenant Models — multi-tenancy foundation
"""
from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db
from app.shared.enums import SubscriptionType, TenantStatus, StorageMode, ProductProfile
import json

class Tenant(db.Model):
    """Every customer/organization is a Tenant."""
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    domain = db.Column(db.String(255), nullable=True, index=True)          # dedicated domain
    subdomain = db.Column(db.String(80), nullable=True, unique=True, index=True)  # tenant.azad.com
    contact_email = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=True)
    tax_number = db.Column(db.String(50), nullable=True)

    status = db.Column(db.Enum(TenantStatus), default=TenantStatus.PENDING, nullable=False)
    storage_mode = db.Column(db.Enum(StorageMode), default=StorageMode.LOCAL, nullable=False)

    # Product Profile
    product_profile_code = db.Column(db.Enum(ProductProfile), nullable=True, default=None)

    # Subscription
    subscription_type = db.Column(db.Enum(SubscriptionType), nullable=True)
    subscription_start = db.Column(db.Date, nullable=True)
    subscription_end = db.Column(db.Date, nullable=True)
    grace_period_end = db.Column(db.Date, nullable=True)

    # Plan link (optional, for SaaS billing)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=True)

    # Branding
    logo_url = db.Column(db.String(255), nullable=True)
    primary_color = db.Column(db.String(7), default='#0d6efd', nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    modules = db.relationship('TenantModule', back_populates='tenant', cascade='all, delete-orphan', lazy='selectin')
    users = db.relationship('User', back_populates='tenant', lazy='select')

    def is_active_and_paid(self) -> bool:
        if self.status != TenantStatus.ACTIVE:
            return False
        if self.subscription_end:
            from datetime import date
            if date.today() > self.subscription_end:
                if self.grace_period_end and date.today() <= self.grace_period_end:
                    return True
                return False
        return True

    def __repr__(self):
        return f"<Tenant {self.slug}>"


class SubscriptionPlan(db.Model):
    """SaaS / perpetual plan definitions."""
    __tablename__ = 'subscription_plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=True)
    billing_type = db.Column(db.Enum(SubscriptionType), nullable=False)
    base_price = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='SAR', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # JSON list of module names included
    modules_included = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenants = db.relationship('Tenant', backref='plan', lazy='select')


class TenantSubscriptionHistory(db.Model):
    """Audit trail of subscription changes."""
    __tablename__ = 'tenant_subscription_history'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)  # ACTIVATE, RENEW, UPGRADE, DOWNGRADE, SUSPEND
    old_plan_id = db.Column(db.Integer, nullable=True)
    new_plan_id = db.Column(db.Integer, nullable=True)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=True)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SupportTicket(db.Model):
    """Support tickets raised by tenant users / super admins."""
    __tablename__ = 'support_tickets'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='general', nullable=False)  # general, billing, technical, feature
    priority = db.Column(db.String(20), default='medium', nullable=False)   # low, medium, high, critical
    status = db.Column(db.String(20), default='open', nullable=False)       # open, in_progress, resolved, closed

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    tenant = db.relationship('Tenant', backref='support_tickets', lazy='select')


class PlatformAuditLog(db.Model):
    """Audit trail for owner / super_admin actions on the platform itself."""
    __tablename__ = 'platform_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True, index=True)

    action = db.Column(db.String(50), nullable=False)      # CREATE_TENANT, SUSPEND, RENEW, UPDATE_PLAN, etc.
    entity_type = db.Column(db.String(50), nullable=False) # tenant, plan, user, system
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)            # JSON / human-readable

    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResourceUsage(db.Model):
    """Per-tenant resource consumption snapshot."""
    __tablename__ = 'resource_usage'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Core resources
    db_size_mb = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    storage_mb = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    api_calls_24h = db.Column(db.Integer, default=0, nullable=False)
    active_users_24h = db.Column(db.Integer, default=0, nullable=False)

    # Extended resources for bundle limits
    total_users = db.Column(db.Integer, default=0, nullable=False)
    total_patients = db.Column(db.Integer, default=0, nullable=False)
    total_visits = db.Column(db.Integer, default=0, nullable=False)
    total_prescriptions = db.Column(db.Integer, default=0, nullable=False)
    total_lab_requests = db.Column(db.Integer, default=0, nullable=False)
    total_radiology_requests = db.Column(db.Integer, default=0, nullable=False)
    total_appointments = db.Column(db.Integer, default=0, nullable=False)
    total_invoices = db.Column(db.Integer, default=0, nullable=False)

    tenant = db.relationship('Tenant', backref='resource_snapshots', lazy='select')

    def to_dict(self) -> dict:
        return {
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "db_size_mb": float(self.db_size_mb),
            "storage_mb": float(self.storage_mb),
            "api_calls_24h": self.api_calls_24h,
            "active_users_24h": self.active_users_24h,
            "total_users": self.total_users,
            "total_patients": self.total_patients,
            "total_visits": self.total_visits,
            "total_prescriptions": self.total_prescriptions,
            "total_lab_requests": self.total_lab_requests,
            "total_radiology_requests": self.total_radiology_requests,
            "total_appointments": self.total_appointments,
            "total_invoices": self.total_invoices,
        }

    @classmethod
    def record_snapshot(cls, tenant_id: int) -> 'ResourceUsage':
        """Record a new resource usage snapshot for a tenant.

        Captures counts from live DB tables:
          - total_users, total_patients, total_visits, total_prescriptions
          - total_lab_requests, total_radiology_requests
          - total_appointments, total_invoices
          - active_users_24h (users logged in within 24h — approximated from User.updated_at)
          - db_size_mb (estimated from PG catalog when available, else 0)
          - storage_mb (from file_uploads when available, else 0)
          - api_calls_24h (incremented externally via track_api_call())
        """
        from app.extensions import db
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        from models.medication import Prescription
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from models.online_booking import OnlineBooking
        from models.invoice import Invoice
        from datetime import datetime, timedelta, timezone
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # DB size estimation from PostgreSQL catalog when available
        db_size_mb = 0
        try:
            result = db.session.execute(
                db.text("""
                    SELECT COALESCE(SUM(pg_total_relation_size(quote_ident(t.tablename))), 0)
                    FROM pg_tables t
                    WHERE t.schemaname = 'public'
                """)
            ).scalar()
            db_size_mb = round(float(result) / (1024 * 1024), 2) if result else 0
        except Exception:
            db_size_mb = 0
        
        # Storage from file_uploads
        storage_mb = 0
        try:
            from models.file_management import FileUpload
            total_bytes = db.session.query(db.func.coalesce(db.func.sum(FileUpload.file_size), 0))\
                .filter(FileUpload.tenant_id == tenant_id).scalar()
            storage_mb = round(float(total_bytes) / (1024 * 1024), 2)
        except Exception:
            storage_mb = 0
        
        # Active users in last 24h
        active_users = User.query.filter(
            User.tenant_id == tenant_id,
            User.updated_at >= cutoff
        ).count()
        
        snapshot = cls(
            tenant_id=tenant_id,
            db_size_mb=db_size_mb,
            storage_mb=storage_mb,
            active_users_24h=active_users,
            total_users=User.query.filter_by(tenant_id=tenant_id).count(),
            total_patients=Patient.query.filter_by(tenant_id=tenant_id).count(),
            total_visits=Visit.query.filter_by(tenant_id=tenant_id).count(),
            total_prescriptions=Prescription.query.filter_by(tenant_id=tenant_id).count(),
            total_lab_requests=LabRequest.query.filter_by(tenant_id=tenant_id).count(),
            total_radiology_requests=RadiologyRequest.query.filter_by(tenant_id=tenant_id).count(),
            total_appointments=OnlineBooking.query.filter_by(tenant_id=tenant_id).count(),
            total_invoices=Invoice.query.filter_by(tenant_id=tenant_id).count(),
        )
        db.session.add(snapshot)
        db.session.commit()
        return snapshot


class TenantFeatureFlag(db.Model):
    """Per-tenant feature flags for fine-grained control."""
    __tablename__ = 'tenant_feature_flags'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    feature_key = db.Column(db.String(80), nullable=False, index=True)
    is_enabled = db.Column(db.Boolean, default=False, nullable=False)
    module_name = db.Column(db.String(50), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'feature_key', name='uq_tenant_feature'),
    )

    tenant = db.relationship('Tenant', backref='feature_flags', lazy='select')

    def __repr__(self):
        return f"<TenantFeatureFlag {self.tenant_id}:{self.feature_key}={self.is_enabled}>"


class TenantModuleSetting(db.Model):
    """Per-tenant module-level settings (JSON config)."""
    __tablename__ = 'tenant_module_settings'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    module_name = db.Column(db.String(50), nullable=False, index=True)
    settings_json = db.Column(db.Text, nullable=True)  # JSON blob for module config

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'module_name', name='uq_tenant_module_setting'),
    )

    tenant = db.relationship('Tenant', backref='module_settings', lazy='select')


# ═══════════════════════════════════════════════════════════════
# SEED DATA ONLY — used ONLY by seed_default_bundles() below.
# All runtime lookups go through ProductBundle (DB table).
# ═══════════════════════════════════════════════════════════════
_PRODUCT_PROFILE_SEED: dict[str, dict] = {
    "private_doctor_clinic": {
        "modules": ["doctor", "appointments"],
        "dashboard_route": "/doctor/dashboard",
        "description_ar": "طبيب منفرد بعيادة خاصة",
        "bundle_slug": "private_doctor_clinic",
        "max_users": 3,
        "max_patients": 500,
    },
    "doctor_clinic_reception": {
        "modules": ["reception", "doctor", "appointments"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "طبيب باستقبال ومواعيد",
        "bundle_slug": "doctor_clinic_reception",
        "max_users": 5,
        "max_patients": 1000,
    },
    "doctor_clinic_full": {
        "modules": ["reception", "doctor", "billing", "lab", "radiology", "appointments", "pharmacy", "reporting"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "عيادة طبيب متكاملة بكامل الخدمات",
        "bundle_slug": "doctor_clinic_full",
        "max_users": 10,
        "max_patients": 3000,
    },
    "small_clinic": {
        "modules": ["reception", "doctor", "billing", "appointments"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "عيادة صغيرة باستقبال وطبيب وفوترة",
        "bundle_slug": "small_clinic",
        "max_users": 10,
        "max_patients": 2000,
    },
    "clinic_with_lab": {
        "modules": ["reception", "doctor", "lab", "billing", "appointments"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "عيادة مع مختبر",
        "bundle_slug": "clinic_with_lab",
        "max_users": 12,
        "max_patients": 3000,
    },
    "clinic_with_radiology": {
        "modules": ["reception", "doctor", "radiology", "billing", "appointments"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "عيادة مع أشعة",
        "bundle_slug": "clinic_with_radiology",
        "max_users": 12,
        "max_patients": 3000,
    },
    "clinic_with_lab_radiology": {
        "modules": ["reception", "doctor", "lab", "radiology", "billing", "appointments"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "عيادة مع مختبر وأشعة",
        "bundle_slug": "clinic_with_lab_radiology",
        "max_users": 15,
        "max_patients": 5000,
    },
    "standalone_lab": {
        "modules": ["lab", "billing", "reporting"],
        "dashboard_route": "/lab/worklist",
        "description_ar": "مختبر مستقل",
        "bundle_slug": "standalone_lab",
        "max_users": 5,
        "max_patients": 1000,
    },
    "lab_with_reception": {
        "modules": ["reception", "lab", "billing", "appointments", "reporting"],
        "dashboard_route": "/lab/worklist",
        "description_ar": "مختبر مع استقبال ومواعيد",
        "bundle_slug": "lab_with_reception",
        "max_users": 8,
        "max_patients": 2000,
    },
    "standalone_radiology": {
        "modules": ["radiology", "billing", "reporting"],
        "dashboard_route": "/radiology/worklist",
        "description_ar": "مركز أشعة مستقل",
        "bundle_slug": "standalone_radiology",
        "max_users": 5,
        "max_patients": 1000,
    },
    "radiology_with_reception": {
        "modules": ["reception", "radiology", "billing", "appointments", "reporting"],
        "dashboard_route": "/radiology/worklist",
        "description_ar": "أشعة مع استقبال ومواعيد",
        "bundle_slug": "radiology_with_reception",
        "max_users": 8,
        "max_patients": 2000,
    },
    "standalone_pharmacy": {
        "modules": ["pharmacy", "inventory", "billing"],
        "dashboard_route": "/pharmacy/pos",
        "description_ar": "صيدلية مستقلة",
        "bundle_slug": "standalone_pharmacy",
        "max_users": 5,
        "max_patients": 1000,
    },
    "standalone_emergency": {
        "modules": ["reception", "emergency", "doctor", "nursing", "billing"],
        "dashboard_route": "/emergency/dashboard",
        "description_ar": "طوارئ مستقلة",
        "bundle_slug": "standalone_emergency",
        "max_users": 15,
        "max_patients": 3000,
    },
    "walkin_clinic": {
        "modules": ["reception", "doctor", "billing", "pharmacy"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "عيادة بدون مواعيد",
        "bundle_slug": "walkin_clinic",
        "max_users": 8,
        "max_patients": 2000,
    },
    "urgent_care": {
        "modules": ["reception", "doctor", "emergency", "nursing", "billing", "lab", "radiology", "pharmacy"],
        "dashboard_route": "/emergency/dashboard",
        "description_ar": "مركز إسعاف وعناية عاجلة",
        "bundle_slug": "urgent_care",
        "max_users": 25,
        "max_patients": 5000,
    },
    "diagnostic_center": {
        "modules": ["reception", "lab", "radiology", "billing", "reporting"],
        "dashboard_route": "/lab/worklist",
        "description_ar": "مركز تشخيص (مختبر + أشعة)",
        "bundle_slug": "diagnostic_center",
        "max_users": 10,
        "max_patients": 3000,
    },
    "community_clinic": {
        "modules": ["reception", "doctor", "nursing", "billing", "appointments", "lab", "pharmacy", "reporting"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "مركز صحي مجتمعي",
        "bundle_slug": "community_clinic",
        "max_users": 20,
        "max_patients": 8000,
    },
    "nursing_home": {
        "modules": ["reception", "nursing", "doctor", "appointments", "pharmacy", "inventory"],
        "dashboard_route": "/nurse/dashboard",
        "description_ar": "دار رعاية تمريضية",
        "bundle_slug": "nursing_home",
        "max_users": 15,
        "max_patients": 500,
    },
    "multi_department_center": {
        "modules": ["reception", "doctor", "nursing", "billing", "appointments", "lab", "radiology", "pharmacy", "emergency", "reporting", "inventory"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "مركز طبي متعدد الأقسام",
        "bundle_slug": "multi_department_center",
        "max_users": 50,
        "max_patients": 10000,
    },
    "polyclinic": {
        "modules": ["reception", "doctor", "nursing", "billing", "appointments", "lab", "radiology", "pharmacy", "emergency", "reporting", "inventory", "portal"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "مجمع عيادات متكامل مع بوابة مرضى",
        "bundle_slug": "polyclinic",
        "max_users": 100,
        "max_patients": 20000,
    },
    "hospital": {
        "modules": ["reception", "doctor", "nursing", "billing", "appointments", "lab", "radiology", "pharmacy", "emergency", "reporting", "inventory", "portal", "ai_imaging", "integration"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "مستشفى كامل بكل الموديولات",
        "bundle_slug": "hospital",
        "max_users": 500,
        "max_patients": 100000,
    },
    "billing_only": {
        "modules": ["billing", "appointments"],
        "dashboard_route": "/finance/dashboard",
        "description_ar": "فوترة ومواعيد فقط",
        "bundle_slug": "billing_only",
        "max_users": 3,
        "max_patients": 500,
    },
    "custom": {
        "modules": [],
        "dashboard_route": "/",
        "description_ar": "حسب الطلب",
        "bundle_slug": "custom",
        "max_users": None,
        "max_patients": None,
    },
}


def get_default_modules_for_profile(profile_code: str) -> list[str]:
    """Get default modules from ProductBundle (DB). Falls back to seed data."""
    try:
        bundle = get_bundle_for_profile(profile_code)
        if bundle:
            return bundle.get_modules()
    except Exception:
        pass
    profile = _PRODUCT_PROFILE_SEED.get(profile_code)
    return list(profile["modules"]) if profile else []


def get_dashboard_for_profile(profile_code: str) -> str:
    """Get dashboard route from ProductBundle (DB). Falls back to seed data."""
    try:
        bundle = get_bundle_for_profile(profile_code)
        if bundle and bundle.get_modules():
            from app.core.module.registry import get_module_metadata
            meta = get_module_metadata(bundle.get_modules()[0])
            if meta and meta.default_route:
                return meta.default_route
    except Exception:
        pass
    profile = _PRODUCT_PROFILE_SEED.get(profile_code)
    return profile["dashboard_route"] if profile else "/"


class ProductBundle(db.Model):
    """Product bundle — sellable package of modules with pricing and limits."""
    __tablename__ = 'product_bundles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description_ar = db.Column(db.Text, nullable=True)

    # Pricing
    monthly_price = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    yearly_price = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    setup_fee = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    currency = db.Column(db.String(3), default='SAR', nullable=False)

    # Modules included (JSON array of module names from MODULE_REGISTRY)
    modules = db.Column(db.Text, nullable=False)  # JSON array

    # Limits
    max_users = db.Column(db.Integer, nullable=True)       # NULL = unlimited
    max_patients = db.Column(db.Integer, nullable=True)    # NULL = unlimited
    storage_gb = db.Column(db.Integer, nullable=True)      # NULL = unlimited
    api_calls_per_month = db.Column(db.Integer, nullable=True)  # NULL = unlimited

    # Status
    is_public = db.Column(db.Boolean, default=True, nullable=False)  # visible in storefront
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Profile linkage (maps to Tenant.product_profile_code)
    profile_code = db.Column(db.String(50), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def get_modules(self) -> list[str]:
        """Return list of module names from JSON."""
        try:
            return json.loads(self.modules) if self.modules else []
        except Exception:
            return []

    def set_modules(self, modules: list[str]):
        """Store module list as JSON."""
        self.modules = json.dumps(modules)

    def get_price(self, billing_type: str) -> Decimal:
        """Return price for billing type (monthly/yearly)."""
        if billing_type == 'yearly':
            return self.yearly_price
        return self.monthly_price

    def is_unlimited(self, resource: str) -> bool:
        """Check if a resource is unlimited."""
        return getattr(self, resource, None) is None

    def __repr__(self):
        return f"<ProductBundle {self.slug}>"


def seed_default_bundles() -> None:
    """Create default ProductBundles from seed data."""
    from app.extensions import db

    bundle_defs = {
        # ── Solo / Small ──
        "private_doctor_clinic": {
            "name": "Private Doctor Clinic",
            "name_ar": "عيادة طبيب خاص",
            "description_ar": "طبيب منفرد بمواعيد فقط",
            "monthly_price": 299.00, "yearly_price": 2999.00, "setup_fee": 0.00,
            "modules": ["doctor", "appointments"],
            "max_users": 3, "max_patients": 500, "storage_gb": 5, "api_calls_per_month": 10000,
        },
        "doctor_clinic_reception": {
            "name": "Doctor Clinic with Reception",
            "name_ar": "عيادة طبيب باستقبال",
            "description_ar": "استقبال + طبيب + مواعيد",
            "monthly_price": 499.00, "yearly_price": 4999.00, "setup_fee": 200.00,
            "modules": ["reception", "doctor", "appointments"],
            "max_users": 5, "max_patients": 1000, "storage_gb": 10, "api_calls_per_month": 25000,
        },
        "doctor_clinic_full": {
            "name": "Doctor Clinic Full",
            "name_ar": "عيادة طبيب متكاملة",
            "description_ar": "استقبال + طبيب + فوترة + مختبر + أشعة + مواعيد + صيدلية + تقارير",
            "monthly_price": 1499.00, "yearly_price": 14999.00, "setup_fee": 1000.00,
            "modules": ["reception", "doctor", "billing", "lab", "radiology", "appointments", "pharmacy", "reporting"],
            "max_users": 10, "max_patients": 3000, "storage_gb": 30, "api_calls_per_month": 75000,
        },
        # ── Small Clinic variants ──
        "small_clinic": {
            "name": "Small Clinic",
            "name_ar": "عيادة صغيرة",
            "description_ar": "استقبال + طبيب + فوترة + مواعيد",
            "monthly_price": 799.00, "yearly_price": 7999.00, "setup_fee": 500.00,
            "modules": ["reception", "doctor", "billing", "appointments"],
            "max_users": 10, "max_patients": 2000, "storage_gb": 20, "api_calls_per_month": 50000,
        },
        "clinic_with_lab": {
            "name": "Clinic with Lab",
            "name_ar": "عيادة مع مختبر",
            "description_ar": "استقبال + طبيب + مختبر + فوترة + مواعيد",
            "monthly_price": 1199.00, "yearly_price": 11999.00, "setup_fee": 800.00,
            "modules": ["reception", "doctor", "lab", "billing", "appointments"],
            "max_users": 12, "max_patients": 3000, "storage_gb": 25, "api_calls_per_month": 60000,
        },
        "clinic_with_radiology": {
            "name": "Clinic with Radiology",
            "name_ar": "عيادة مع أشعة",
            "description_ar": "استقبال + طبيب + أشعة + فوترة + مواعيد",
            "monthly_price": 1299.00, "yearly_price": 12999.00, "setup_fee": 800.00,
            "modules": ["reception", "doctor", "radiology", "billing", "appointments"],
            "max_users": 12, "max_patients": 3000, "storage_gb": 60, "api_calls_per_month": 60000,
        },
        "clinic_with_lab_radiology": {
            "name": "Clinic with Lab & Radiology",
            "name_ar": "عيادة مع مختبر وأشعة",
            "description_ar": "استقبال + طبيب + مختبر + أشعة + فوترة + مواعيد",
            "monthly_price": 1799.00, "yearly_price": 17999.00, "setup_fee": 1200.00,
            "modules": ["reception", "doctor", "lab", "radiology", "billing", "appointments"],
            "max_users": 15, "max_patients": 5000, "storage_gb": 70, "api_calls_per_month": 100000,
        },
        # ── Standalone ──
        "standalone_lab": {
            "name": "Standalone Lab",
            "name_ar": "مختبر مستقل",
            "description_ar": "تحاليل + فوترة + تقارير",
            "monthly_price": 599.00, "yearly_price": 5999.00, "setup_fee": 300.00,
            "modules": ["lab", "billing", "reporting"],
            "max_users": 5, "max_patients": 1000, "storage_gb": 10, "api_calls_per_month": 20000,
        },
        "lab_with_reception": {
            "name": "Lab with Reception",
            "name_ar": "مختبر مع استقبال",
            "description_ar": "استقبال + مختبر + فوترة + مواعيد + تقارير",
            "monthly_price": 899.00, "yearly_price": 8999.00, "setup_fee": 500.00,
            "modules": ["reception", "lab", "billing", "appointments", "reporting"],
            "max_users": 8, "max_patients": 2000, "storage_gb": 15, "api_calls_per_month": 30000,
        },
        "standalone_radiology": {
            "name": "Standalone Radiology",
            "name_ar": "أشعة مستقلة",
            "description_ar": "أشعة + فوترة + تقارير",
            "monthly_price": 799.00, "yearly_price": 7999.00, "setup_fee": 500.00,
            "modules": ["radiology", "billing", "reporting"],
            "max_users": 5, "max_patients": 1000, "storage_gb": 50, "api_calls_per_month": 20000,
        },
        "radiology_with_reception": {
            "name": "Radiology with Reception",
            "name_ar": "أشعة مع استقبال",
            "description_ar": "استقبال + أشعة + فوترة + مواعيد + تقارير",
            "monthly_price": 1099.00, "yearly_price": 10999.00, "setup_fee": 700.00,
            "modules": ["reception", "radiology", "billing", "appointments", "reporting"],
            "max_users": 8, "max_patients": 2000, "storage_gb": 60, "api_calls_per_month": 30000,
        },
        "standalone_pharmacy": {
            "name": "Standalone Pharmacy",
            "name_ar": "صيدلية مستقلة",
            "description_ar": "صيدلية + مخزون + فوترة",
            "monthly_price": 499.00, "yearly_price": 4999.00, "setup_fee": 300.00,
            "modules": ["pharmacy", "inventory", "billing"],
            "max_users": 5, "max_patients": 1000, "storage_gb": 10, "api_calls_per_month": 30000,
        },
        "standalone_emergency": {
            "name": "Standalone Emergency Center",
            "name_ar": "طوارئ مستقلة",
            "description_ar": "استقبال + طوارئ + طبيب + تمريض + فوترة",
            "monthly_price": 1299.00, "yearly_price": 12999.00, "setup_fee": 1000.00,
            "modules": ["reception", "emergency", "doctor", "nursing", "billing"],
            "max_users": 15, "max_patients": 3000, "storage_gb": 20, "api_calls_per_month": 50000,
        },
        # ── Mid-size ──
        "walkin_clinic": {
            "name": "Walk-in Clinic",
            "name_ar": "عيادة بدون مواعيد",
            "description_ar": "استقبال + طبيب + فوترة + صيدلية (دخول مباشر)",
            "monthly_price": 999.00, "yearly_price": 9999.00, "setup_fee": 600.00,
            "modules": ["reception", "doctor", "billing", "pharmacy"],
            "max_users": 8, "max_patients": 2000, "storage_gb": 15, "api_calls_per_month": 40000,
        },
        "urgent_care": {
            "name": "Urgent Care Center",
            "name_ar": "مركز إسعاف وعناية عاجلة",
            "description_ar": "استقبال + طوارئ + طبيب + تمريض + فوترة + مختبر + أشعة + صيدلية",
            "monthly_price": 2499.00, "yearly_price": 24999.00, "setup_fee": 2000.00,
            "modules": ["reception", "doctor", "emergency", "nursing", "billing", "lab", "radiology", "pharmacy"],
            "max_users": 25, "max_patients": 5000, "storage_gb": 50, "api_calls_per_month": 150000,
        },
        "diagnostic_center": {
            "name": "Diagnostic Center",
            "name_ar": "مركز تشخيص",
            "description_ar": "استقبال + مختبر + أشعة + فوترة + تقارير",
            "monthly_price": 1399.00, "yearly_price": 13999.00, "setup_fee": 800.00,
            "modules": ["reception", "lab", "radiology", "billing", "reporting"],
            "max_users": 10, "max_patients": 3000, "storage_gb": 100, "api_calls_per_month": 50000,
        },
        "community_clinic": {
            "name": "Community Health Center",
            "name_ar": "مركز صحي مجتمعي",
            "description_ar": "استقبال + طبيب + تمريض + فوترة + مواعيد + مختبر + صيدلية + تقارير",
            "monthly_price": 1999.00, "yearly_price": 19999.00, "setup_fee": 1500.00,
            "modules": ["reception", "doctor", "nursing", "billing", "appointments", "lab", "pharmacy", "reporting"],
            "max_users": 20, "max_patients": 8000, "storage_gb": 40, "api_calls_per_month": 100000,
        },
        "nursing_home": {
            "name": "Nursing Home",
            "name_ar": "دار رعاية تمريضية",
            "description_ar": "استقبال + تمريض + طبيب + مواعيد + صيدلية + مخزون",
            "monthly_price": 1599.00, "yearly_price": 15999.00, "setup_fee": 1000.00,
            "modules": ["reception", "nursing", "doctor", "appointments", "pharmacy", "inventory"],
            "max_users": 15, "max_patients": 500, "storage_gb": 20, "api_calls_per_month": 40000,
        },
        # ── Large ──
        "multi_department_center": {
            "name": "Multi-Department Medical Center",
            "name_ar": "مركز طبي متعدد الأقسام",
            "description_ar": "منصة طبية متكاملة بجميع الأقسام",
            "monthly_price": 2499.00, "yearly_price": 24999.00, "setup_fee": 2000.00,
            "modules": ["reception", "doctor", "nursing", "billing", "appointments", "lab", "radiology", "pharmacy", "emergency", "reporting", "inventory"],
            "max_users": 50, "max_patients": 10000, "storage_gb": 100, "api_calls_per_month": 200000,
        },
        "polyclinic": {
            "name": "Polyclinic",
            "name_ar": "مجمع عيادات",
            "description_ar": "مركز طبي متعدد الأقسام مع بوابة مرضى",
            "monthly_price": 3499.00, "yearly_price": 34999.00, "setup_fee": 3000.00,
            "modules": ["reception", "doctor", "nursing", "billing", "appointments", "lab", "radiology", "pharmacy", "emergency", "reporting", "inventory", "portal"],
            "max_users": 100, "max_patients": 20000, "storage_gb": 200, "api_calls_per_month": 500000,
        },
        "hospital": {
            "name": "Hospital",
            "name_ar": "مستشفى كامل",
            "description_ar": "جميع الموديولات — تصوير ذكي + تكامل خارجي + بوابة مرضى",
            "monthly_price": 5999.00, "yearly_price": 59999.00, "setup_fee": 5000.00,
            "modules": ["reception", "doctor", "nursing", "billing", "appointments", "lab", "radiology", "pharmacy", "emergency", "reporting", "inventory", "portal", "ai_imaging", "integration"],
            "max_users": 500, "max_patients": 100000, "storage_gb": 500, "api_calls_per_month": 2000000,
        },
        # ── Special ──
        "billing_only": {
            "name": "Billing & Appointments Only",
            "name_ar": "فوترة ومواعيد فقط",
            "description_ar": "فوترة ومواعيد — مناسب لصالونات ومراكز الخدمات",
            "monthly_price": 199.00, "yearly_price": 1999.00, "setup_fee": 0.00,
            "modules": ["billing", "appointments"],
            "max_users": 3, "max_patients": 500, "storage_gb": 5, "api_calls_per_month": 5000,
        },
        "custom": {
            "name": "Custom Bundle",
            "name_ar": "حزمة مخصصة",
            "description_ar": "اختر الموديولز التي تناسبك",
            "monthly_price": 0.00, "yearly_price": 0.00, "setup_fee": 0.00,
            "modules": [],
            "max_users": None, "max_patients": None, "storage_gb": None, "api_calls_per_month": None,
        },
    }
    
    for slug, defn in bundle_defs.items():
        existing = ProductBundle.query.filter_by(slug=slug).first()
        if existing:
            continue
        b = ProductBundle(
            slug=slug,
            name=defn["name"],
            name_ar=defn["name_ar"],
            description_ar=defn["description_ar"],
            monthly_price=defn["monthly_price"],
            yearly_price=defn["yearly_price"],
            setup_fee=defn["setup_fee"],
            currency="SAR",
            modules=json.dumps(defn["modules"]),
            max_users=defn["max_users"],
            max_patients=defn["max_patients"],
            storage_gb=defn["storage_gb"],
            api_calls_per_month=defn["api_calls_per_month"],
            is_public=True,
            is_active=True,
            profile_code=slug,
        )
        db.session.add(b)
    db.session.commit()
    print(f"Seeded {len(bundle_defs)} default ProductBundles")


def get_bundle_for_profile(profile_code: str) -> ProductBundle | None:
    """Get ProductBundle linked to a profile code."""
    return ProductBundle.query.filter_by(profile_code=profile_code, is_active=True).first()


def check_tenant_limits(tenant_id: int) -> dict[str, bool]:
    """Check if tenant is within bundle limits.
    Returns dict with keys: users_ok, patients_ok, storage_ok, api_ok
    Each limit is checked independently — an unlimited field does NOT bypass other limits.
    Comparisons use <= (inclusive) so that max_users=3 allows exactly 3 users.
    API calls compare api_calls_24h against monthly cap by dividing by 30.
    """
    from app.extensions import db
    from app.core.tenant.models import ResourceUsage

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return {"users_ok": True, "patients_ok": True, "storage_ok": True, "api_ok": True}

    bundle = get_bundle_for_profile(tenant.product_profile_code or "")
    if not bundle:
        return {"users_ok": True, "patients_ok": True, "storage_ok": True, "api_ok": True}

    latest_usage = ResourceUsage.query.filter_by(tenant_id=tenant_id).order_by(ResourceUsage.recorded_at.desc()).first()
    if not latest_usage:
        latest_usage = ResourceUsage.record_snapshot(tenant_id)

    # Each limit is independent — unlimited fields use float('inf') which passes <=
    return {
        "users_ok": latest_usage.total_users <= (bundle.max_users if bundle.max_users is not None else float('inf')),
        "patients_ok": latest_usage.total_patients <= (bundle.max_patients if bundle.max_patients is not None else float('inf')),
        "storage_ok": (float(latest_usage.storage_mb) / 1024) <= (bundle.storage_gb if bundle.storage_gb is not None else float('inf')),
        "api_ok": int(latest_usage.api_calls_24h * 30) <= (bundle.api_calls_per_month if bundle.api_calls_per_month is not None else float('inf')),
    }


class NotificationRule(db.Model):
    """Owner-configured notification triggers (email/webhook)."""
    __tablename__ = 'notification_rules'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # subscription_expiry, trial_ending, high_resource, ticket_new
    channel = db.Column(db.String(20), default='email', nullable=False)  # email, webhook, sms
    target = db.Column(db.String(255), nullable=False)       # email address or webhook URL
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    template_subject = db.Column(db.String(255), nullable=True)
    template_body = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
