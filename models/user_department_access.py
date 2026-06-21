from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin


class UserDepartmentAccess(TenantMixin, db.Model):
    __tablename__ = 'user_department_access'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'), nullable=False, index=True)
    can_access = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'department_id', name='uq_user_department_access'),
    )

    user = db.relationship('User', foreign_keys=[user_id], lazy='selectin')
    department = db.relationship('Department', foreign_keys=[department_id], lazy='selectin')

