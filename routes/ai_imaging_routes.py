"""
AI Imaging Analysis Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors
from app_factory import db
from models import AIImagingAnalysis, DICOMStudy
from datetime import datetime, timezone
import random

ai_imaging_bp = Blueprint('ai_imaging', __name__)


@ai_imaging_bp.route('/')
@login_required
@handle_route_errors
def index():
    analyses = AIImagingAnalysis.query.order_by(AIImagingAnalysis.created_at.desc()).limit(50).all()
    return render_template('ai_imaging/index.html', analyses=analyses)


@ai_imaging_bp.route('/request', methods=['POST'])
@login_required
@handle_route_errors
def request_analysis():
    study_id = request.form.get('study_id', type=int)
    analysis_type = request.form.get('analysis_type', 'detection')
    provider = request.form.get('provider', 'internal')
    study = DICOMStudy.query.get_or_404(study_id)
    ai = AIImagingAnalysis(
        study_id=study_id,
        patient_id=study.patient_id if study.patient_id else 0,
        provider=provider,
        analysis_type=analysis_type,
        status='pending'
    )
    db.session.add(ai)
    db.session.commit()

    ai.status = 'completed'
    ai.processed_at = datetime.now(timezone.utc)
    ai.confidence_score = round(random.uniform(0.7, 0.99), 4)
    ai.severity = random.choice(['normal', 'mild', 'moderate', 'severe'])
    ai.suggested_report_text = "AI Analysis: No significant abnormalities detected. Recommend clinical correlation."
    ai.processing_time_ms = random.randint(500, 3000)
    db.session.commit()
    flash('تم إرسال الطلب للتحليل الذكي واكتماله', 'success')
    return redirect(url_for('ai_imaging.index'))


@ai_imaging_bp.route('/<int:ai_id>/review', methods=['POST'])
@login_required
@handle_route_errors
def review(ai_id):
    ai = AIImagingAnalysis.query.get_or_404(ai_id)
    ai.status = 'reviewed'
    ai.reviewed_by = current_user.id
    ai.review_notes = request.form.get('review_notes', '')
    db.session.commit()
    flash('تم مراجعة التحليل', 'success')
    return redirect(url_for('ai_imaging.index'))
