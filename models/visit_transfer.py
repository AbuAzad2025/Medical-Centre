from datetime import datetime, timezone
from app_factory import db


class VisitTransferLog(db.Model):
    __tablename__ = 'visit_transfer_logs'

    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True)

    from_department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    to_department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)

    from_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    to_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    transferred_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    source = db.Column(db.String(30), default='reception', nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    visit = db.relationship('Visit', lazy='select')
    from_department = db.relationship('Department', foreign_keys=[from_department_id], lazy='select')
    to_department = db.relationship('Department', foreign_keys=[to_department_id], lazy='select')
    from_doctor = db.relationship('User', foreign_keys=[from_doctor_id], lazy='select')
    to_doctor = db.relationship('User', foreign_keys=[to_doctor_id], lazy='select')
    actor = db.relationship('User', foreign_keys=[transferred_by], lazy='select')

