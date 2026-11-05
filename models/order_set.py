"""Order Sets and Best Practice Advisories (BPA) models."""

from datetime import UTC, datetime

from app.shared.mixins import TenantMixin
from app_factory import db


class OrderSet(TenantMixin, db.Model):
    """A predefined set of orders (medications, labs, imaging) for a clinical scenario."""

    __tablename__ = 'order_sets'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)  # diagnosis, procedure, preventive
    diagnosis_code = db.Column(db.String(20), nullable=True)  # ICD-10
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    items = db.relationship(
        'OrderSetItem', backref='order_set', lazy='dynamic', cascade='all, delete-orphan'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'description': self.description,
            'category': self.category,
            'diagnosis_code': self.diagnosis_code,
            'is_active': self.is_active,
            'items': [item.to_dict() for item in self.items],
        }


class OrderSetItem(TenantMixin, db.Model):
    """An individual order within an order set."""

    __tablename__ = 'order_set_items'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    order_set_id = db.Column(
        db.Integer, db.ForeignKey('order_sets.id', ondelete='CASCADE'), nullable=False
    )
    item_type = db.Column(db.String(20), nullable=False)  # medication, lab, imaging, procedure
    item_name = db.Column(db.String(200), nullable=False)
    item_code = db.Column(db.String(50), nullable=True)
    default_dosage = db.Column(db.String(100), nullable=True)
    default_quantity = db.Column(db.Integer, default=1)
    default_duration = db.Column(db.Integer, default=7)
    is_optional = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'item_type': self.item_type,
            'item_name': self.item_name,
            'item_code': self.item_code,
            'default_dosage': self.default_dosage,
            'default_quantity': self.default_quantity,
            'default_duration': self.default_duration,
            'is_optional': self.is_optional,
        }


class BestPracticeAdvisory(TenantMixin, db.Model):
    """A best practice advisory (BPA) that triggers on clinical conditions."""

    __tablename__ = 'best_practice_advisories'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    trigger_condition = db.Column(
        db.String(50), nullable=False
    )  # diagnosis, medication, lab_result, vital
    trigger_value = db.Column(db.String(200), nullable=True)  # e.g., ICD-10 code, medication name
    advisory_type = db.Column(db.String(20), default='info')  # info, warning, hard_stop
    advisory_message = db.Column(db.Text, nullable=False)
    advisory_message_ar = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'description': self.description,
            'trigger_condition': self.trigger_condition,
            'trigger_value': self.trigger_value,
            'advisory_type': self.advisory_type,
            'advisory_message': self.advisory_message,
            'advisory_message_ar': self.advisory_message_ar,
            'is_active': self.is_active,
            'priority': self.priority,
        }

    def check_trigger(self, context: dict) -> bool:
        """Check if this advisory should trigger based on clinical context."""
        if not self.is_active:
            return False
        if self.trigger_condition == 'diagnosis':
            diagnoses = context.get('diagnoses', [])
            return any(self.trigger_value in (d.get('code') or '') for d in diagnoses)
        if self.trigger_condition == 'medication':
            meds = context.get('medications', [])
            return any(self.trigger_value.lower() in (m.get('name') or '').lower() for m in meds)
        if self.trigger_condition == 'lab_result':
            results = context.get('lab_results', [])
            return any(self.trigger_value in (r.get('test_name') or '') for r in results)
        if self.trigger_condition == 'vital':
            vitals = context.get('vitals', {})
            return self.trigger_value in vitals
        return False
