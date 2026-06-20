"""
نموذج الذكاء الصناعي والتحليل - AI Analytics Model
Medical System AI Analytics Model
"""

from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class AIRecommendation(TenantMixin, db.Model):
    """نموذج توصية الذكاء الصناعي"""
    
    __tablename__ = 'ai_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    recommendation_type = db.Column(db.String(100), nullable=False)  # diagnosis, treatment, medication, test
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)  # 0-1
    source_data = db.Column(db.Text, nullable=True)  # JSON format
    is_accepted = db.Column(db.Boolean, nullable=True)
    accepted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    patient = db.relationship('Patient', back_populates='ai_recommendations')
    visit = db.relationship('Visit', back_populates='ai_recommendations')
    accepter = db.relationship('User')
    
    def __repr__(self):
        return f'<AIRecommendation {self.title}>'
    
    def get_recommendation_type_display(self):
        """نوع التوصية للعرض"""
        type_map = {
            'diagnosis': 'تشخيص',
            'treatment': 'علاج',
            'medication': 'دواء',
            'test': 'فحص'
        }
        return type_map.get(self.recommendation_type, self.recommendation_type)
    
    def get_confidence_display(self):
        """درجة الثقة للعرض"""
        if self.confidence_score >= 0.9:
            return "عالية جداً"
        elif self.confidence_score >= 0.7:
            return "عالية"
        elif self.confidence_score >= 0.5:
            return "متوسطة"
        else:
            return "منخفضة"
    
    def get_confidence_color(self):
        """لون درجة الثقة"""
        if self.confidence_score >= 0.7:
            return "success"
        elif self.confidence_score >= 0.5:
            return "warning"
        else:
            return "danger"
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.full_name if self.patient else None,
            'visit_id': self.visit_id,
            'recommendation_type': self.recommendation_type,
            'recommendation_type_display': self.get_recommendation_type_display(),
            'title': self.title,
            'description': self.description,
            'confidence_score': self.confidence_score,
            'confidence_display': self.get_confidence_display(),
            'confidence_color': self.get_confidence_color(),
            'source_data': self.source_data,
            'is_accepted': self.is_accepted,
            'accepted_by': self.accepted_by,
            'accepter_name': self.accepter.full_name if self.accepter else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'feedback': self.feedback,
            'created_at': self.created_at.isoformat()
        }

class DiseasePattern(TenantMixin, db.Model):
    """نموذج نمط المرض"""
    
    __tablename__ = 'disease_patterns'
    
    id = db.Column(db.Integer, primary_key=True)
    disease_name = db.Column(db.String(200), nullable=False)
    icd_code = db.Column(db.String(20), nullable=True)
    symptoms = db.Column(db.Text, nullable=True)  # JSON format
    risk_factors = db.Column(db.Text, nullable=True)  # JSON format
    age_group = db.Column(db.String(50), nullable=True)
    gender_preference = db.Column(db.String(10), nullable=True)
    seasonality = db.Column(db.String(100), nullable=True)
    prevalence_score = db.Column(db.Float, nullable=True)
    severity_level = db.Column(db.String(50), nullable=True)
    treatment_protocols = db.Column(db.Text, nullable=True)  # JSON format
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<DiseasePattern {self.disease_name}>'
    
    def get_severity_display(self):
        """مستوى الخطورة للعرض"""
        severity_map = {
            'mild': 'خفيف',
            'moderate': 'متوسط',
            'severe': 'شديد',
            'critical': 'حرج'
        }
        return severity_map.get(self.severity_level, self.severity_level)
    
    def get_severity_color(self):
        """لون مستوى الخطورة"""
        color_map = {
            'mild': 'success',
            'moderate': 'warning',
            'severe': 'danger',
            'critical': 'dark'
        }
        return color_map.get(self.severity_level, 'secondary')
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'disease_name': self.disease_name,
            'icd_code': self.icd_code,
            'symptoms': self.symptoms,
            'risk_factors': self.risk_factors,
            'age_group': self.age_group,
            'gender_preference': self.gender_preference,
            'seasonality': self.seasonality,
            'prevalence_score': self.prevalence_score,
            'severity_level': self.severity_level,
            'severity_display': self.get_severity_display(),
            'severity_color': self.get_severity_color(),
            'treatment_protocols': self.treatment_protocols,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class PerformanceAnalytics(TenantMixin, db.Model):
    """نموذج تحليل الأداء"""
    
    __tablename__ = 'performance_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    metric_name = db.Column(db.String(200), nullable=False)
    metric_type = db.Column(db.String(100), nullable=False)  # daily, weekly, monthly, yearly
    metric_value = db.Column(db.Float, nullable=False)
    target_value = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    additional_data = db.Column(db.Text, nullable=True)  # JSON format
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    doctor = db.relationship('User')
    
    def __repr__(self):
        return f'<PerformanceAnalytics {self.metric_name}>'
    
    def get_metric_type_display(self):
        """نوع المقياس للعرض"""
        type_map = {
            'daily': 'يومي',
            'weekly': 'أسبوعي',
            'monthly': 'شهري',
            'yearly': 'سنوي'
        }
        return type_map.get(self.metric_type, self.metric_type)
    
    def get_performance_status(self):
        """حالة الأداء"""
        if self.target_value:
            if self.metric_value >= self.target_value:
                return "ممتاز"
            elif self.metric_value >= (self.target_value * 0.8):
                return "جيد"
            elif self.metric_value >= (self.target_value * 0.6):
                return "متوسط"
            else:
                return "ضعيف"
        return "غير محدد"
    
    def get_performance_color(self):
        """لون الأداء"""
        status = self.get_performance_status()
        color_map = {
            "ممتاز": "success",
            "جيد": "info",
            "متوسط": "warning",
            "ضعيف": "danger"
        }
        return color_map.get(status, 'secondary')
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'metric_name': self.metric_name,
            'metric_type': self.metric_type,
            'metric_type_display': self.get_metric_type_display(),
            'metric_value': self.metric_value,
            'target_value': self.target_value,
            'unit': self.unit,
            'department': self.department,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.full_name if self.doctor else None,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'additional_data': self.additional_data,
            'performance_status': self.get_performance_status(),
            'performance_color': self.get_performance_color(),
            'created_at': self.created_at.isoformat()
        }

class PatientInsight(TenantMixin, db.Model):
    """نموذج رؤى المريض"""
    
    __tablename__ = 'patient_insights'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    insight_type = db.Column(db.String(100), nullable=False)  # health_risk, treatment_effectiveness, etc.
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    risk_level = db.Column(db.String(50), nullable=True)  # low, medium, high, critical
    confidence_score = db.Column(db.Float, nullable=True)
    recommendations = db.Column(db.Text, nullable=True)  # JSON format
    is_acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    patient = db.relationship('Patient', back_populates='patient_insights')
    acknowledger = db.relationship('User')
    
    def __repr__(self):
        return f'<PatientInsight {self.title}>'
    
    def get_insight_type_display(self):
        """نوع الرؤية للعرض"""
        type_map = {
            'health_risk': 'مخاطر صحية',
            'treatment_effectiveness': 'فعالية العلاج',
            'medication_adherence': 'التزام الدواء',
            'lifestyle_factors': 'عوامل نمط الحياة',
            'preventive_care': 'الرعاية الوقائية'
        }
        return type_map.get(self.insight_type, self.insight_type)
    
    def get_risk_level_display(self):
        """مستوى المخاطر للعرض"""
        risk_map = {
            'low': 'منخفض',
            'medium': 'متوسط',
            'high': 'عالي',
            'critical': 'حرج'
        }
        return risk_map.get(self.risk_level, self.risk_level)
    
    def get_risk_color(self):
        """لون مستوى المخاطر"""
        color_map = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'dark'
        }
        return color_map.get(self.risk_level, 'secondary')
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.full_name if self.patient else None,
            'insight_type': self.insight_type,
            'insight_type_display': self.get_insight_type_display(),
            'title': self.title,
            'description': self.description,
            'risk_level': self.risk_level,
            'risk_level_display': self.get_risk_level_display(),
            'risk_color': self.get_risk_color(),
            'confidence_score': self.confidence_score,
            'recommendations': self.recommendations,
            'is_acknowledged': self.is_acknowledged,
            'acknowledged_by': self.acknowledged_by,
            'acknowledger_name': self.acknowledger.full_name if self.acknowledger else None,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'created_at': self.created_at.isoformat()
        }


class ModelPrediction(TenantMixin, db.Model):
    __tablename__ = 'model_predictions'

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True, index=True)
    input_data = db.Column(db.Text, nullable=True)
    output_data = db.Column(db.Text, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    is_accepted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    accepted_at = db.Column(db.DateTime, nullable=True)

    patient = db.relationship('Patient', back_populates='model_predictions')
