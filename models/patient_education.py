"""
Patient Education Materials
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class PatientEducationMaterial(TenantMixin, db.Model):
    __tablename__ = 'patient_education_materials'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    # categories: 'medication', 'disease', 'procedure', 'lifestyle', 'nutrition', 'post_op', 'general'

    content_html = db.Column(db.Text, nullable=True)
    content_text = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=True)  # uploaded PDF/image
    file_type = db.Column(db.String(20), nullable=True)  # pdf, image, video

    language = db.Column(db.String(10), default='ar', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    view_count = db.Column(db.Integer, default=0, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    creator = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<PatientEducationMaterial {self.title}>"


class PatientEducationAssignment(TenantMixin, db.Model):
    __tablename__ = 'patient_education_assignments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey('patient_education_materials.id', ondelete='CASCADE'), nullable=False, index=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    status = db.Column(db.String(20), default='assigned', nullable=False)  # assigned | viewed | completed
    viewed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    patient = db.relationship('Patient', lazy='selectin')
    material = db.relationship('PatientEducationMaterial', lazy='selectin')
    assigner = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<PatientEducationAssignment patient={self.patient_id} material={self.material_id}>"
