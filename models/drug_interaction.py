from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint, UniqueConstraint
from app_factory import db


class DrugInteraction(db.Model):
    __tablename__ = 'drug_interactions'

    id = db.Column(db.Integer, primary_key=True)

    medication_a_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False, index=True)
    medication_b_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False, index=True)

    severity = db.Column(db.String(16), nullable=False, default='MODERATE', index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("severity IN ('LOW','MODERATE','HIGH')", name='chk_drug_interactions_severity'),
        UniqueConstraint('medication_a_id', 'medication_b_id', name='uq_drug_interactions_pair'),
        Index('idx_drug_interactions_active_severity', 'is_active', 'severity'),
    )

    medication_a = db.relationship('Medication', foreign_keys=[medication_a_id], lazy='select')
    medication_b = db.relationship('Medication', foreign_keys=[medication_b_id], lazy='select')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'medication_a_id': self.medication_a_id,
            'medication_b_id': self.medication_b_id,
            'severity': self.severity,
            'description': self.description,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

