"""
كتالوج الفحوصات المخبرية والباقات
Lab Test Catalog and Panel models
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin


class LabTestCatalog(TenantMixin, db.Model):
    __tablename__ = 'lab_test_catalog'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, index=True)
    name_ar = db.Column(db.String(200), nullable=False)
    name_en = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=False, default='other', index=True)
    unit = db.Column(db.String(40), nullable=True)
    default_reference_range = db.Column(db.String(120), nullable=True)
    critical_low = db.Column(db.String(40), nullable=True)
    critical_high = db.Column(db.String(40), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    preparation_instructions = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=True, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.Index('idx_lab_test_catalog_tenant_code', 'tenant_id', 'code', unique=True),
    )

    def __repr__(self):
        return f"<LabTestCatalog {self.code}: {self.name_ar}>"


class LabTestPanel(TenantMixin, db.Model):
    __tablename__ = 'lab_test_panels'

    id = db.Column(db.Integer, primary_key=True)
    name_ar = db.Column(db.String(200), nullable=False)
    name_en = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    items = db.relationship(
        'LabTestPanelItem',
        back_populates='panel',
        lazy='selectin',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='LabTestPanelItem.sort_order'
    )

    def __repr__(self):
        return f"<LabTestPanel {self.name_ar}>"


class LabTestPanelItem(db.Model):
    __tablename__ = 'lab_test_panel_items'

    id = db.Column(db.Integer, primary_key=True)
    panel_id = db.Column(db.Integer, db.ForeignKey('lab_test_panels.id', ondelete='CASCADE'), nullable=False, index=True)
    test_id = db.Column(db.Integer, db.ForeignKey('lab_test_catalog.id', ondelete='CASCADE'), nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=True, default=0)

    panel = db.relationship('LabTestPanel', back_populates='items', lazy='selectin')
    test = db.relationship('LabTestCatalog', lazy='selectin')

    __table_args__ = (
        db.Index('idx_lab_panel_item_unique', 'panel_id', 'test_id', unique=True),
    )

    def __repr__(self):
        return f"<LabTestPanelItem panel={self.panel_id} test={self.test_id}>"
