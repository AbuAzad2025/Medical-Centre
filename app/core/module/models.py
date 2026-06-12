"""
Module Activation Models — which modules are enabled per tenant
"""
from datetime import datetime, timezone
from app.extensions import db
from app.shared.enums import ModuleName

class ModuleDefinition(db.Model):
    """Static registry mirror in DB (for referential integrity)."""
    __tablename__ = 'module_definitions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name_ar = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<ModuleDefinition {self.name}>"


class TenantModule(db.Model):
    """Link table: which modules are active for each tenant."""
    __tablename__ = 'tenant_modules'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    module_name = db.Column(db.String(50), nullable=False, index=True)

    is_active = db.Column(db.Boolean, default=False, nullable=False)
    activated_at = db.Column(db.DateTime, nullable=True)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    activated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    tenant = db.relationship('Tenant', back_populates='modules')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'module_name', name='uq_tenant_module'),
    )

    def __repr__(self):
        return f"<TenantModule {self.tenant_id}:{self.module_name}={self.is_active}>"
