"""
نموذج الممرضة - Nurse Model
Medical System Nurse Model
"""

from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db
from app.shared.mixins import TenantMixin
import json

class Nurse(TenantMixin, db.Model):
    """نموذج الممرضة"""
    
    __tablename__ = 'nurses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    specialization = db.Column(db.String(100), nullable=True)
    experience_years = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    user = db.relationship('User', back_populates='nurse_profile')
    recorded_vital_signs = db.relationship('VitalSigns', back_populates='nurse')

    
    def __repr__(self):
        return f'<Nurse {self.user.full_name if self.user else "Unknown"}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'license_number': self.license_number,
            'specialization': self.specialization,
            'experience_years': self.experience_years,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# تم نقل نموذج NurseTask إلى models/task_management.py كجزء من النموذج الموحد Task
# يمكن استخدام Task مع task_type='nursing' للتمريض

class VitalSigns(db.Model):
    """نموذج العلامات الحيوية"""
    
    __tablename__ = 'vital_signs'
    
    __table_args__ = (
        Index('idx_vitals_patient_recorded', 'patient_id', 'recorded_at'),
        Index('idx_vitals_nurse_recorded', 'nurse_id', 'recorded_at'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    nurse_id = db.Column(db.Integer, db.ForeignKey('nurses.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # العلامات الحيوية
    blood_pressure_systolic = db.Column(db.Integer, nullable=True)
    blood_pressure_diastolic = db.Column(db.Integer, nullable=True)
    heart_rate = db.Column(db.Integer, nullable=True)
    temperature = db.Column(db.Float, nullable=True)
    oxygen_saturation = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    height = db.Column(db.Float, nullable=True)
    respiratory_rate = db.Column(db.Integer, nullable=True)
    
    # ملاحظات
    notes = db.Column(db.Text, nullable=True)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    patient = db.relationship('Patient', back_populates='vital_signs')
    nurse = db.relationship('Nurse', back_populates='recorded_vital_signs')
    
    def __repr__(self):
        return f'<VitalSigns for {self.patient.full_name if self.patient else "Unknown"}>'
    
    def get_blood_pressure_display(self):
        """عرض ضغط الدم"""
        if self.blood_pressure_systolic and self.blood_pressure_diastolic:
            return f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
        return "غير محدد"
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'visit_id': self.visit_id,
            'patient_id': self.patient_id,
            'nurse_id': self.nurse_id,
            'blood_pressure_systolic': self.blood_pressure_systolic,
            'blood_pressure_diastolic': self.blood_pressure_diastolic,
            'heart_rate': self.heart_rate,
            'temperature': self.temperature,
            'oxygen_saturation': self.oxygen_saturation,
            'weight': self.weight,
            'height': self.height,
            'respiratory_rate': self.respiratory_rate,
            'notes': self.notes,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }


class MedicationAdministrationLog(db.Model):
    __tablename__ = 'medication_administration_logs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='SET NULL'), nullable=True, index=True)
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_items.id', ondelete='SET NULL'), nullable=True, index=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='SET NULL'), nullable=True, index=True)
    nurse_id = db.Column(db.Integer, db.ForeignKey('nurses.id', ondelete='SET NULL'), nullable=True, index=True)
    administered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)

    patient = db.relationship('Patient', lazy='selectin')
    visit = db.relationship('Visit', lazy='selectin')
    prescription = db.relationship('Prescription', lazy='selectin')
    prescription_item = db.relationship('PrescriptionItem', lazy='selectin')
    medication = db.relationship('Medication', lazy='selectin')
    nurse = db.relationship('Nurse', lazy='selectin')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'patient_id': self.patient_id,
            'visit_id': self.visit_id,
            'prescription_id': self.prescription_id,
            'prescription_item_id': self.prescription_item_id,
            'medication_id': self.medication_id,
            'nurse_id': self.nurse_id,
            'administered_at': self.administered_at.isoformat() if self.administered_at else None,
            'notes': self.notes,
        }
