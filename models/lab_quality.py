from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db


class LabQualityControlEntry(db.Model):
    __tablename__ = 'lab_quality_control_entries'

    id = db.Column(db.Integer, primary_key=True)
    test_code = db.Column(db.String(50), nullable=False, index=True)
    test_name = db.Column(db.String(120), nullable=True)
    control_level = db.Column(db.String(16), nullable=False, default='NORMAL', index=True)
    measured_value = db.Column(db.String(120), nullable=False)
    unit = db.Column(db.String(40), nullable=True)
    expected_range = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(16), nullable=False, default='PASS', index=True)
    notes = db.Column(db.Text, nullable=True)

    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("control_level IN ('LOW','NORMAL','HIGH')", name='chk_lab_qc_control_level'),
        CheckConstraint("status IN ('PASS','FAIL')", name='chk_lab_qc_status'),
        Index('idx_lab_qc_test_date', 'test_code', 'recorded_at'),
    )

    recorder = db.relationship('User', foreign_keys=[recorded_by], lazy='selectin')

