"""orders routes - extracted from monolithic emergency.py"""

import logging

# Imports
from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.shared.print_context import generate_qr_data_uri
from models.lab_request import LabRequest
from models.medication import Prescription
from models.radiology_request import RadiologyRequest
from routes.emergency import emergency_bp
from services.emergency_service import emergency_service
from utils.db_safety import safe_commit
from utils.decorators import role_required

# =============================================
# ORDERS ROUTES
# =============================================


@emergency_bp.route('/prescription/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'manager')
def prescription(emergency_id):
    """وصفة طبية للطوارئ"""

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        if request.method == 'POST':
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم إنشاء الوصفة بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/prescription.html', emergency=emergency)
    except Exception:
        logging.exception('Error in emergency prescription: %s')
        flash('حدث خطأ في إنشاء الوصفة', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/lab-request/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'manager')
def lab_request(emergency_id):
    """طلب فحوصات للطوارئ"""
    if 'lab' not in getattr(g, 'enabled_modules', set()):
        flash('وحدة المختبر غير مفعلة في باقة العيادة', 'error')
        return redirect(url_for('emergency.patient_queue'))

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        if request.method == 'POST':
            tests_requested = (
                request.form.getlist('tests[]')
                or request.form.getlist('tests')
                or [t.strip() for t in (request.form.get('tests') or '').split(',') if t.strip()]
            )
            if not tests_requested:
                flash('اختر فحصاً واحداً على الأقل', 'error')
                return redirect(request.referrer or url_for('emergency.patient_queue'))
            urgency = (request.form.get('urgency') or 'ROUTINE').strip()
            notes = (request.form.get('notes') or '').strip()
            notes_text = f'[{urgency}] {notes}' if notes else f'[{urgency}]'

            lab_request = LabRequest(
                tenant_id=emergency.tenant_id,
                patient_id=emergency.patient_id,
                visit_id=None,
                requested_by=current_user.id,
                status='REQUESTED',
                notes=notes_text,
            )
            db.session.add(lab_request)
            db.session.flush()
            emergency.lab_request_id = lab_request.id

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم إرسال طلب الفحوصات بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/lab_request.html', emergency=emergency)
    except Exception:
        logging.exception('Error in emergency lab request: %s')
        flash('حدث خطأ في إرسال طلب الفحوصات', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/radiology-request/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'manager')
def radiology_request(emergency_id):
    """طلب أشعة للطوارئ"""
    if 'radiology' not in getattr(g, 'enabled_modules', set()):
        flash('وحدة الأشعة غير مفعلة في باقة العيادة', 'error')
        return redirect(url_for('emergency.patient_queue'))

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        if request.method == 'POST':
            imaging_type = (request.form.get('imaging_type') or '').strip()
            body_part = (request.form.get('body_part') or '').strip()
            urgency = (request.form.get('urgency') or 'ROUTINE').strip()
            clinical_question = (request.form.get('clinical_question') or '').strip()
            notes = (request.form.get('notes') or '').strip()
            notes_parts = [p for p in (f'[{urgency}]', clinical_question, notes) if p]
            notes_text = ' | '.join(notes_parts)

            radiology_request_row = RadiologyRequest(
                tenant_id=emergency.tenant_id,
                patient_id=emergency.patient_id,
                visit_id=None,
                requested_by=current_user.id,
                status='REQUESTED',
                modality=imaging_type or None,
                body_part=body_part or None,
                notes=notes_text,
            )
            db.session.add(radiology_request_row)
            db.session.flush()
            emergency.radiology_request_id = radiology_request_row.id

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم إرسال طلب الأشعة بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/radiology_request.html', emergency=emergency)
    except Exception:
        logging.exception('Error in emergency radiology request: %s')
        flash('حدث خطأ في إرسال طلب الأشعة', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/print-prescription/<int:prescription_id>')
@login_required
@role_required('emergency', 'manager')
def print_prescription(prescription_id):
    """طباعة الوصفة الطبية للطوارئ"""

    try:
        prescription = (
            db.session.execute(select(Prescription).filter_by(id=prescription_id)).scalars().first()
        )
        if not prescription:
            flash('الوصفة غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        qr_data_uri = generate_qr_data_uri(
            f'RX|{prescription.id}|{prescription.patient_id}|{prescription.created_at.isoformat() if prescription.created_at else ""}'
        )
        return render_template(
            'print/prescription.html', prescription=prescription, qr_data_uri=qr_data_uri
        )
    except Exception:
        logging.exception('Error printing prescription: %s')
        flash('حدث خطأ في طباعة الوصفة', 'error')
        return redirect(url_for('emergency.patient_queue'))
