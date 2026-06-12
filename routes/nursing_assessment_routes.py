"""
Nursing Assessment Routes (Braden, Glasgow, Fall Risk, Pain, Norton)
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app_factory import db
from models import NursingAssessment, Patient, Visit
from sqlalchemy import func
from datetime import datetime, timezone

nursing_assessment_bp = Blueprint('nursing_assessment', __name__, url_prefix='/nursing-assessment')


@nursing_assessment_bp.route('/patient/<int:patient_id>')
@login_required
def patient_assessments(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    assessments = NursingAssessment.query.filter_by(patient_id=patient_id).order_by(NursingAssessment.created_at.desc()).all()
    return render_template('nursing_assessment/patient_list.html', patient=patient, assessments=assessments)


@nursing_assessment_bp.route('/new/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def new_assessment(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    assessment_type = request.args.get('type', 'braden')
    visit_id = request.args.get('visit_id', type=int)

    if request.method == 'POST':
        assessment = NursingAssessment(
            patient_id=patient_id,
            visit_id=visit_id,
            nurse_id=current_user.id,
            assessment_type=assessment_type,
            notes=request.form.get('notes', '')
        )

        if assessment_type == 'braden':
            assessment.braden_sensory_perception = int(request.form.get('sensory', 4))
            assessment.braden_moisture = int(request.form.get('moisture', 4))
            assessment.braden_activity = int(request.form.get('activity', 4))
            assessment.braden_mobility = int(request.form.get('mobility', 4))
            assessment.braden_nutrition = int(request.form.get('nutrition', 4))
            assessment.braden_friction_shear = int(request.form.get('friction', 3))
            assessment.total_score = assessment.braden_total
            if assessment.total_score is not None:
                score = int(assessment.total_score)
                if score <= 9:
                    assessment.risk_level = 'severe'
                elif score <= 12:
                    assessment.risk_level = 'high'
                elif score <= 14:
                    assessment.risk_level = 'moderate'
                else:
                    assessment.risk_level = 'low'

        elif assessment_type == 'glasgow':
            assessment.glasgow_eye = int(request.form.get('eye', 4))
            assessment.glasgow_verbal = int(request.form.get('verbal', 5))
            assessment.glasgow_motor = int(request.form.get('motor', 6))
            assessment.total_score = assessment.glasgow_total
            if assessment.total_score is not None:
                score = int(assessment.total_score)
                if score >= 13:
                    assessment.risk_level = 'low'
                elif score >= 9:
                    assessment.risk_level = 'moderate'
                elif score >= 4:
                    assessment.risk_level = 'high'
                else:
                    assessment.risk_level = 'severe'

        elif assessment_type == 'fall_risk':
            assessment.fall_history = int(request.form.get('history', 0))
            assessment.fall_secondary_diagnosis = int(request.form.get('diagnosis', 0))
            assessment.fall_ambulatory_aid = int(request.form.get('aid', 0))
            assessment.fall_iv_saline = int(request.form.get('iv', 0))
            assessment.fall_gait = int(request.form.get('gait', 0))
            assessment.fall_mental_status = int(request.form.get('mental', 0))
            assessment.total_score = assessment.morse_total
            if assessment.total_score is not None:
                score = int(assessment.total_score)
                if score >= 51:
                    assessment.risk_level = 'high'
                else:
                    assessment.risk_level = 'low'

        elif assessment_type == 'pain_scale':
            assessment.pain_score = int(request.form.get('pain_score', 0))
            assessment.pain_location = request.form.get('pain_location', '')
            assessment.pain_character = request.form.get('pain_character', '')
            assessment.total_score = assessment.pain_score
            if assessment.total_score is not None:
                score = int(assessment.total_score)
                if score <= 3:
                    assessment.risk_level = 'low'
                elif score <= 6:
                    assessment.risk_level = 'moderate'
                else:
                    assessment.risk_level = 'high'

        elif assessment_type == 'norton':
            assessment.norton_physical_condition = int(request.form.get('physical', 4))
            assessment.norton_mental_condition = int(request.form.get('mental', 4))
            assessment.norton_activity = int(request.form.get('activity', 4))
            assessment.norton_mobility = int(request.form.get('mobility', 4))
            assessment.norton_incontinence = int(request.form.get('incontinence', 4))
            assessment.total_score = assessment.norton_total
            if assessment.total_score is not None:
                score = int(assessment.total_score)
                if score <= 14:
                    assessment.risk_level = 'high'
                elif score <= 18:
                    assessment.risk_level = 'moderate'
                else:
                    assessment.risk_level = 'low'

        db.session.add(assessment)
        db.session.commit()
        flash('تم حفظ التقييم بنجاح', 'success')
        return redirect(url_for('nursing_assessment.patient_assessments', patient_id=patient_id))

    return render_template('nursing_assessment/new.html', patient=patient, assessment_type=assessment_type, visit_id=visit_id)


@nursing_assessment_bp.route('/view/<int:assessment_id>')
@login_required
def view_assessment(assessment_id):
    assessment = NursingAssessment.query.get_or_404(assessment_id)
    return render_template('nursing_assessment/view.html', assessment=assessment)


@nursing_assessment_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard showing recent assessments across all patients"""
    recent = NursingAssessment.query.order_by(NursingAssessment.created_at.desc()).limit(50).all()
    stats = db.session.query(
        NursingAssessment.assessment_type,
        func.count(NursingAssessment.id).label('count'),
        func.avg(NursingAssessment.total_score).label('avg_score')
    ).group_by(NursingAssessment.assessment_type).all()
    return render_template('nursing_assessment/dashboard.html', recent=recent, stats=stats)
