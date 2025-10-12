"""
نموذج الممرضة - Nurse Model
Medical System Nurse Model
"""

from datetime import datetime
from app_factory import db
import json

class Nurse(db.Model):
    """نموذج الممرضة"""
    
    __tablename__ = 'nurses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    specialization = db.Column(db.String(100), nullable=True)
    experience_years = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    user = db.relationship('User', backref='nurse_profile')
    
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
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    nurse_id = db.Column(db.Integer, db.ForeignKey('nurses.id'), nullable=False)
    
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
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    patient = db.relationship('Patient', backref='vital_signs')
    nurse = db.relationship('Nurse', backref='recorded_vital_signs')
    
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
