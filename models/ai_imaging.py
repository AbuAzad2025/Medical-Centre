"""
AI Radiology / Imaging Analysis Results
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class AIImagingAnalysis(TenantMixin, db.Model):
    __tablename__ = 'ai_imaging_analyses'

    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.Integer, db.ForeignKey('dicom_studies.id', ondelete='CASCADE'), nullable=True, index=True)
    series_id = db.Column(db.Integer, db.ForeignKey('dicom_series.id', ondelete='CASCADE'), nullable=True, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)

    # AI provider
    provider = db.Column(db.String(50), nullable=False, index=True)
    # providers: 'internal', 'google_medlm', 'azure_health', 'aws_health', 'custom'
    model_name = db.Column(db.String(100), nullable=True)
    model_version = db.Column(db.String(50), nullable=True)

    # Analysis type
    analysis_type = db.Column(db.String(50), nullable=False)
    # types: 'classification', 'detection', 'segmentation', 'anomaly', 'report_suggestion'

    # Results
    findings = db.Column(db.Text, nullable=True)  # JSON structured findings
    confidence_score = db.Column(db.Numeric(5, 4), nullable=True)  # 0.0000 - 1.0000
    severity = db.Column(db.String(20), nullable=True)  # normal | mild | moderate | severe | critical

    # Detailed annotations
    annotations = db.Column(db.Text, nullable=True)  # JSON array of bounding boxes / masks
    suggested_report_text = db.Column(db.Text, nullable=True)
    suggested_icd_codes = db.Column(db.Text, nullable=True)

    # Status
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    # pending | processing | completed | failed | reviewed
    processed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    review_notes = db.Column(db.Text, nullable=True)

    # Raw response from AI service
    raw_response = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    # Cost / usage tracking
    processing_time_ms = db.Column(db.Integer, nullable=True)
    cost_usd = db.Column(db.Numeric(10, 4), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    study = db.relationship('DICOMStudy', lazy='selectin')
    series = db.relationship('DICOMSeries', lazy='selectin')
    patient = db.relationship('Patient', lazy='selectin')
    reviewer = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<AIImagingAnalysis patient={self.patient_id} type={self.analysis_type} status={self.status}>"
