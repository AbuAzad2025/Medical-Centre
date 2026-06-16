"""
Tenant Models — multi-tenancy foundation
"""
from datetime import datetime, timezone
from app.extensions import db
from app.shared.enums import SubscriptionType, TenantStatus, StorageMode, ProductProfile

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

    db_size_mb = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    storage_mb = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    api_calls_24h = db.Column(db.Integer, default=0, nullable=False)
    active_users_24h = db.Column(db.Integer, default=0, nullable=False)

    tenant = db.relationship('Tenant', backref='resource_snapshots', lazy='select')


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


PRODUCT_PROFILE_DEFAULTS: dict[str, dict] = {
    "private_doctor_clinic": {
        "modules": ["doctor", "appointments"],
        "dashboard_route": "/doctor/dashboard",
        "description_ar": "طبيب منفرد بعيادة خاصة",
    },
    "small_clinic": {
        "modules": ["reception", "doctor", "billing", "appointments"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "عيادة صغيرة باستقبال وطبيب وفوترة",
    },
    "standalone_lab": {
        "modules": ["lab", "billing", "reporting"],
        "dashboard_route": "/lab/worklist",
        "description_ar": "مختبر مستقل",
    },
    "standalone_radiology": {
        "modules": ["radiology", "billing", "reporting"],
        "dashboard_route": "/radiology/worklist",
        "description_ar": "مركز أشعة مستقل",
    },
    "standalone_pharmacy": {
        "modules": ["pharmacy", "inventory", "billing"],
        "dashboard_route": "/pharmacy/pos",
        "description_ar": "صيدلية مستقلة",
    },
    "multi_department_center": {
        "modules": ["reception", "doctor", "nursing", "billing", "appointments", "queue", "lab", "radiology", "pharmacy", "emergency", "reporting", "inventory"],
        "dashboard_route": "/reception/dashboard",
        "description_ar": "مركز طبي كامل",
    },
    "custom": {
        "modules": [],
        "dashboard_route": "/",
        "description_ar": "حسب الطلب",
    },
}


def get_default_modules_for_profile(profile_code: str) -> list[str]:
    profile = PRODUCT_PROFILE_DEFAULTS.get(profile_code)
    return list(profile["modules"]) if profile else []


def get_dashboard_for_profile(profile_code: str) -> str:
    profile = PRODUCT_PROFILE_DEFAULTS.get(profile_code)
    return profile["dashboard_route"] if profile else "/"


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
