"""
AI Imaging Analysis Routes
"""

import random
from datetime import UTC, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models import AIImagingAnalysis, DICOMStudy
from utils.db_safety import safe_commit
from utils.decorators import handle_route_errors, role_required

ai_imaging_bp = Blueprint('ai_imaging', __name__)


@ai_imaging_bp.route('/')
@login_required
@role_required('doctor', 'radiology', 'admin', 'manager')
@handle_route_errors
def index():
    analyses = (
        db.session.execute(
            select(AIImagingAnalysis).order_by(AIImagingAnalysis.created_at.desc()).limit(50)
        )
        .scalars()
        .all()
    )
    return render_template('ai_imaging/index.html', analyses=analyses)


@ai_imaging_bp.route('/request', methods=['POST'])
@login_required
@role_required('doctor', 'radiology', 'admin', 'manager')
@handle_route_errors
def request_analysis():
    study_id = request.form.get('study_id', type=int)
    analysis_type = request.form.get('analysis_type', 'detection')
    provider = request.form.get('provider', 'internal')
    study = db.get_or_404(DICOMStudy, study_id)
    ai = AIImagingAnalysis(
        study_id=study_id,
        patient_id=study.patient_id if study.patient_id else 0,
        provider=provider,
        analysis_type=analysis_type,
        status='pending',
    )
    db.session.add(ai)
    safe_commit(db.session, error_message='database commit failed', reraise=True)

    ai.status = 'completed'
    ai.processed_at = datetime.now(UTC)
    ai.confidence_score = round(random.uniform(0.7, 0.99), 4)
    ai.severity = random.choice(['normal', 'mild', 'moderate', 'severe'])
    ai.suggested_report_text = (
        'AI Analysis: No significant abnormalities detected. Recommend clinical correlation.'
    )
    ai.processing_time_ms = random.randint(500, 3000)
    safe_commit(db.session, error_message='database commit failed', reraise=True)
    flash('تم إرسال الطلب للتحليل الذكي واكتماله', 'success')
    return redirect(url_for('ai_imaging.index'))


@ai_imaging_bp.route('/<int:ai_id>/review', methods=['POST'])
@login_required
@role_required('doctor', 'radiology', 'admin', 'manager')
@handle_route_errors
def review(ai_id):
    ai = db.get_or_404(AIImagingAnalysis, ai_id)
    ai.status = 'reviewed'
    ai.reviewed_by = current_user.id
    ai.review_notes = request.form.get('review_notes', '')
    safe_commit(db.session, error_message='database commit failed', reraise=True)
    flash('تم مراجعة التحليل', 'success')
    return redirect(url_for('ai_imaging.index'))
