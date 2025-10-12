"""
نموذج القسم - Department Model (نسخة نهائية)
"""
from datetime import datetime
from sqlalchemy import Index, CheckConstraint
from app_factory import db


class Department(db.Model):
    """نموذج القسم"""
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)   # EN
    name_ar = db.Column(db.String(100), nullable=False)             # AR
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)

    head_doctor_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', use_alter=True, ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    capacity = db.Column(db.Integer, default=0)
    current_patients = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("capacity >= 0", name='chk_department_capacity_non_negative'),
        Index('idx_department_active', 'is_active'),
        Index('idx_department_name_ar', 'name_ar'),
    )

    users = db.relationship(
        'User',
        back_populates='department',
        foreign_keys='User.department_id',
        lazy='selectin',
        passive_deletes=True
    )

    head_doctor = db.relationship(
        'User',
        foreign_keys=[head_doctor_id],
        back_populates='head_of_department',
        lazy='select',
        post_update=True
    )

    visits = db.relationship(
        'Visit',
        back_populates='department',
        lazy='selectin',
        passive_deletes=True
    )

    appointments = db.relationship(
        'Appointment',
        back_populates='department',
        lazy='selectin',
        passive_deletes=True
    )
    
    # علاقة التسعير للأطباء
    doctor_pricing = db.relationship(
        'DoctorPricing',
        back_populates='department',
        lazy='select'
    )

    def __repr__(self) -> str:
        return f"<Department {self.name_ar or self.name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "name_ar": self.name_ar,
            "description": self.description,
            "location": self.location,
            "phone": self.phone,
            "email": self.email,
            "head_doctor_id": self.head_doctor_id,
            "capacity": self.capacity,
            "current_patients": self.current_patients,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }