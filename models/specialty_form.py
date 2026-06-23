"""Dynamic specialty forms — UX1-005."""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin


class SpecialtyForm(TenantMixin, db.Model):
    __tablename__ = 'specialty_forms'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    specialty = db.Column(db.String(80), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    latest_published_version_id = db.Column(db.Integer, db.ForeignKey('specialty_form_versions.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    versions = db.relationship('SpecialtyFormVersion', back_populates='form', foreign_keys='SpecialtyFormVersion.form_id', lazy='selectin', cascade='all, delete-orphan')
    latest_published_version = db.relationship('SpecialtyFormVersion', foreign_keys=[latest_published_version_id], lazy='selectin')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'slug', name='uq_specialty_form_tenant_slug'),
    )


class SpecialtyFormVersion(TenantMixin, db.Model):
    __tablename__ = 'specialty_form_versions'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('specialty_forms.id', ondelete='CASCADE'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='draft', nullable=False)  # draft, published, archived
    published_at = db.Column(db.DateTime, nullable=True)
    published_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    form = db.relationship('SpecialtyForm', back_populates='versions', foreign_keys=[form_id], lazy='selectin')
    fields = db.relationship('SpecialtyFormField', back_populates='version', lazy='selectin', cascade='all, delete-orphan', order_by='SpecialtyFormField.sort_order')

    __table_args__ = (
        db.UniqueConstraint('form_id', 'version_number', name='uq_specialty_form_version'),
    )


class SpecialtyFormField(TenantMixin, db.Model):
    __tablename__ = 'specialty_form_fields'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('specialty_form_versions.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    field_type = db.Column(db.String(40), nullable=False)  # text, number, date, select, checkbox, textarea
    required = db.Column(db.Boolean, default=False, nullable=False)
    options = db.Column(db.JSON, nullable=True)  # list of strings for select/checkbox
    default_value = db.Column(db.Text, nullable=True)
    validation_rules = db.Column(db.JSON, nullable=True)  # e.g. {"min": 0, "max": 100}
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    version = db.relationship('SpecialtyFormVersion', back_populates='fields', lazy='selectin')

    __table_args__ = (
        db.UniqueConstraint('version_id', 'name', name='uq_specialty_form_field_name'),
    )


class SpecialtyFormSubmission(TenantMixin, db.Model):
    __tablename__ = 'specialty_form_submissions'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('specialty_form_versions.id', ondelete='RESTRICT'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True)
    answers = db.Column(db.JSON, nullable=False)  # {field_name: value}
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    version = db.relationship('SpecialtyFormVersion', lazy='selectin')
    patient = db.relationship('Patient', lazy='selectin')
