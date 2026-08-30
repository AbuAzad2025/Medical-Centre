"""treatment routes - extracted from monolithic emergency.py"""

import logging
from datetime import UTC, datetime

# Imports
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, select

from app.extensions import db
from app.shared.enums import EmergencyStatus
from models.emergency import EmergencyCase
from models.visit import Visit
from routes.emergency import _set_emergency_status, emergency_bp
from services.emergency_service import emergency_service
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required, role_required_json

# =============================================
# TREATMENT ROUTES
# =============================================


@emergency_bp.route('/treatment/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'manager')
def treatment(emergency_id):
    """علاج الطوارئ"""

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        if request.method == 'POST':
            chief_complaint = request.form.get('chief_complaint')
            diagnosis = request.form.get('diagnosis')
            treatment_given = request.form.get('treatment_given')
            medications = request.form.get('medications')
            procedures = request.form.get('procedures')

            emergency.chief_complaint = chief_complaint
            emergency.diagnosis = diagnosis
            emergency.treatment_given = treatment_given
            emergency.medications_text = medications
            emergency.procedures_text = procedures
            _set_emergency_status(emergency, 'OBSERVATION')
            emergency.treated_by_id = current_user.id
            emergency.treatment_completed_at = datetime.now(UTC)

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم تسجيل العلاج بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/emergency_treatment.html', emergency=emergency)
    except Exception:
        logging.exception('Error in emergency treatment: %s')
        flash('حدث خطأ في تسجيل العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/end-treatment/<int:emergency_id>', methods=['POST'])
@login_required
@role_required('emergency', 'manager')
def end_treatment(emergency_id):
    """إنهاء العلاج في الطوارئ"""

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        # إنهاء العلاج
        _set_emergency_status(emergency, 'COMPLETED')
        emergency.completed_at = datetime.now(UTC)
        emergency.completed_by_id = current_user.id

        # إخطار الاستقبال لإتمام إجراءات الزيارة المرتبطة دون تعديل الحالة مباشرة
        try:
            if emergency.visit:
                from services.notification_service import NotificationService

                NotificationService.send_notification(
                    recipient_role='reception',
                    recipient_department_id=emergency.visit.department_id,
                    title='إنهاء علاج حالة طوارئ',
                    message=f'زيارة رقم {emergency.visit.id} المرتبطة بحالة الطوارئ {emergency_id} تم إنهاء علاجها - يرجى إتمام الإجراءات',
                    notification_type='warning',
                    sender_id=current_user.id,
                )
        except Exception as e:
            logging.warning(f'Error in {__name__}: {e}')
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        flash('تم إنهاء العلاج بنجاح وإخطار الاستقبال', 'success')
        return redirect(url_for('emergency.patient_queue'))
    except Exception:
        logging.exception('Error ending emergency treatment: %s')
        flash('حدث خطأ في إنهاء العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/start-treatment/<int:emergency_id>', methods=['POST'])
@login_required
@role_required('emergency', 'manager')
def start_treatment(emergency_id):
    """بدء علاج حالة الطوارئ"""

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        # تحديث حالة الطوارئ
        _set_emergency_status(emergency, 'TREATMENT')
        emergency.treatment_started_at = datetime.now(UTC)
        emergency.treated_by_id = current_user.id

        safe_commit(db.session, error_message='database commit failed', reraise=True)

        flash('تم بدء العلاج بنجاح', 'success')
        return redirect(url_for('emergency.patient_details', emergency_id=emergency_id))
    except Exception:
        logging.exception('Error starting treatment: %s')
        flash('حدث خطأ في بدء العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/emergency-visits')
@login_required
@role_required('emergency', 'manager')
def emergency_visits():
    try:
        from flask import g

        tenant_id = getattr(g, 'tenant_id', None)
        visits_query = select(Visit).filter(Visit.visit_type == 'EMERGENCY')
        if tenant_id is not None and hasattr(Visit, 'tenant_id'):
            visits_query = visits_query.filter(Visit.tenant_id == tenant_id)
        visits = db.session.execute(visits_query.order_by(desc(Visit.created_at))).scalars().all()
        return render_template('emergency/emergency_visits.html', visits=visits)
    except Exception:
        logging.exception('Error loading emergency visits: %s')
        flash('حدث خطأ في تحميل زيارات الطوارئ', 'error')
        return redirect(url_for('emergency.dashboard'))


@emergency_bp.route('/emergency-treatment/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'doctor', 'manager')
def emergency_treatment(visit_id):
    try:
        from flask import g

        tenant_id = getattr(g, 'tenant_id', None)
        visit_query = select(Visit).filter_by(id=visit_id)
        if tenant_id is not None and hasattr(Visit, 'tenant_id'):
            visit_query = visit_query.filter(Visit.tenant_id == tenant_id)
        visit = db.session.execute(visit_query).scalars().first()
        if not visit:
            if request.method == 'POST':
                return jsonify({'success': False, 'error': 'الزيارة غير موجودة'}), 404
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('emergency.emergency_visits'))
        if request.method == 'POST':
            diagnosis = request.form.get('emergency_diagnosis')
            procedures = request.form.get('emergency_procedures')
            notes = request.form.get('notes')
            if diagnosis:
                visit.diagnosis = diagnosis
            if procedures:
                visit.treatment_plan = procedures
            if notes:
                visit.notes = notes
            # إشعار الاستقبال ببدء علاج الطوارئ دون تعديل حالة الزيارة مباشرة
            try:
                from services.notification_service import NotificationService

                NotificationService.send_notification(
                    recipient_role='reception',
                    recipient_department_id=visit.department_id,
                    title='بدء علاج زيارة طوارئ',
                    message=f'تم تسجيل علاج إسعافي للزيارة رقم {visit.id}',
                    notification_type='info',
                    sender_id=current_user.id,
                )
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            return jsonify({'success': True})
        return render_template('emergency/emergency_treatment.html', visit=visit)
    except Exception:
        logging.exception('Error in emergency treatment: %s')
        if request.method == 'POST':
            return jsonify({'success': False, 'error': 'حدث خطأ أثناء حفظ العلاج الإسعافي'}), 500
        flash('حدث خطأ في تحميل صفحة العلاج الإسعافي', 'error')
        return redirect(url_for('emergency.emergency_visits'))


@emergency_bp.route('/emergency-visits/<int:visit_id>/complete', methods=['POST'])
@login_required
@role_required_json('emergency', 'manager')
def complete_visit(visit_id):
    try:
        from flask import g

        tenant_id = getattr(g, 'tenant_id', None)
        visit_query = select(Visit).filter_by(id=visit_id)
        if tenant_id is not None and hasattr(Visit, 'tenant_id'):
            visit_query = visit_query.filter(Visit.tenant_id == tenant_id)
        visit = db.session.execute(visit_query).scalars().first()
        if not visit:
            return jsonify({'success': False, 'message': 'الزيارة غير موجودة'}), 404
        emergency_case = (
            db.session.execute(select(EmergencyCase).filter_by(visit_id=visit_id)).scalars().first()
        )
        if emergency_case:
            emergency_case.status = EmergencyStatus.COMPLETED
            emergency_case.completed_at = datetime.now(UTC)
        # تسجيل اكتمال العلاج للطوارئ دون تعديل حالة الزيارة مباشرة، وإخطار الاستقبال
        visit.completed_at = datetime.now(UTC)
        visit.completed_by = current_user.id
        try:
            from services.notification_service import NotificationService

            NotificationService.send_notification(
                recipient_role='reception',
                recipient_department_id=visit.department_id,
                title='إنهاء علاج زيارة طوارئ',
                message=f'تم إنهاء علاج زيارة الطوارئ رقم {visit.id} - يرجى إتمام الإجراءات',
                notification_type='warning',
                sender_id=current_user.id,
            )
        except Exception as e:
            logging.warning(f'Error in {__name__}: {e}')
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': True}), 200
    except Exception:
        logging.exception('Complete emergency visit error: %s')
        safe_rollback(db.session, error_message='database rollback')
        return jsonify({'success': False, 'message': 'تعذر إنهاء الزيارة حالياً'}), 500
