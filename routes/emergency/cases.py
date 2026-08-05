"""cases routes - extracted from monolithic emergency.py"""

import json
import logging
from datetime import UTC, date, datetime

# Imports
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import EmergencyStatus
from models.emergency import EmergencyCase
from models.patient import Patient
from models.user import User
from models.visit import Visit
from routes.emergency import _set_emergency_status, emergency_bp
from services.emergency_service import emergency_service
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required, role_required_json

# =============================================
# CASES ROUTES
# =============================================


@emergency_bp.route('/cases')
@login_required
@role_required('emergency', 'manager')
def list_emergency_cases():
    """حالات الطوارئ"""

    try:
        page = request.args.get('page', 1, type=int)
        per_page = 12
        pagination = emergency_service.list_cases(
            search=request.args.get('search'),
            priority=request.args.get('priority'),
            status=request.args.get('status'),
            doctor_id=request.args.get('doctor_id'),
            today_only=request.args.get('today') == 'true',
            page=page,
            per_page=per_page,
        )
        emergency_cases = pagination

        for emergency in emergency_cases.items:
            emergency.emergency_date = emergency.created_at
            emergency.emergency_time = emergency.created_at
            emergency.doctor = (
                emergency.visit.doctor if emergency.visit and emergency.visit.doctor else None
            )
            try:
                emergency.vital_signs = (
                    json.loads(emergency.vital_signs) if emergency.vital_signs else None
                )
            except Exception:
                emergency.vital_signs = None

        total_emergencies = db.session.execute(
            select(func.count()).select_from(EmergencyCase)
        ).scalar()
        today_emergencies = db.session.execute(
            select(func.count())
            .select_from(EmergencyCase)
            .filter(EmergencyCase.created_at >= datetime.combine(date.today(), datetime.min.time()))
        ).scalar()
        critical_emergencies = db.session.execute(
            select(func.count())
            .select_from(EmergencyCase)
            .filter(EmergencyCase.severity == 'CRITICAL')
        ).scalar()
        active_emergencies = db.session.execute(
            select(func.count())
            .select_from(EmergencyCase)
            .filter(EmergencyCase.status != EmergencyStatus.COMPLETED)
        ).scalar()

        doctors = db.session.execute(select(User).filter_by(role='doctor')).scalars().all()

        return render_template(
            'emergency/list.html',
            emergency_cases=emergency_cases,
            total_emergencies=total_emergencies,
            today_emergencies=today_emergencies,
            critical_emergencies=critical_emergencies,
            active_emergencies=active_emergencies,
            doctors=doctors,
        )
    except Exception as e:
        logging.exception(f'Error loading emergency cases: {e!s}')
        flash('حدث خطأ في تحميل حالات الطوارئ', 'error')
        return redirect(url_for('emergency.dashboard'))


@emergency_bp.route('/cases/<int:id>')
@login_required
@role_required('emergency', 'manager')
def view_emergency_case(id):
    try:
        emergency = emergency_service.get_case(id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.list_emergency_cases'))
        emergency.emergency_date = emergency.created_at
        emergency.emergency_time = emergency.created_at
        emergency.doctor = (
            emergency.visit.doctor if emergency.visit and emergency.visit.doctor else None
        )
        try:
            emergency.vital_signs = (
                json.loads(emergency.vital_signs) if emergency.vital_signs else None
            )
        except Exception:
            emergency.vital_signs = None
        history = []
        timeline = []
        try:
            from models.emergency_status_history import EmergencyStatusHistory

            history = (
                db.session.execute(
                    select(EmergencyStatusHistory)
                    .filter_by(emergency_id=emergency.id)
                    .order_by(EmergencyStatusHistory.created_at.asc())
                )
                .scalars()
                .all()
            )
            for i, h in enumerate(history):
                next_h = history[i + 1] if i + 1 < len(history) else None
                dur_min = None
                if next_h and h.created_at and next_h.created_at:
                    dur_min = int((next_h.created_at - h.created_at).total_seconds() // 60)
                timeline.append({'item': h, 'duration_minutes': dur_min})
        except Exception:
            timeline = []

        return render_template('emergency/view.html', emergency=emergency, status_timeline=timeline)
    except Exception as e:
        logging.exception(f'Error viewing emergency case: {e!s}')
        flash('حدث خطأ في عرض حالة الطوارئ', 'error')
        return redirect(url_for('emergency.list_emergency_cases'))


@emergency_bp.route('/cases/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'manager')
def edit_emergency_case(id):
    try:
        emergency = emergency_service.get_case(id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.list_emergency_cases'))
        if request.method == 'POST':
            emergency.patient_id = request.form.get('patient_id', type=int) or emergency.patient_id
            emergency_date = request.form.get('emergency_date')
            emergency_time = request.form.get('emergency_time')
            if emergency_date and emergency_time:
                try:
                    dt = datetime.strptime(f'{emergency_date} {emergency_time}', '%Y-%m-%d %H:%M')
                    emergency.created_at = dt
                except Exception as e:
                    logging.warning(f'Error in {__name__}: {e}')
            priority_val = request.form.get('priority')
            severity_map = {
                'low': 'LOW',
                'medium': 'MODERATE',
                'high': 'HIGH',
                'critical': 'CRITICAL',
            }
            emergency.severity = severity_map.get(priority_val, emergency.severity)
            status_val = request.form.get('status')
            if status_val:
                mapped = (
                    status_val.upper()
                    if status_val in ['active', 'resolved', 'transferred', 'cancelled']
                    else status_val
                )
                _set_emergency_status(emergency, mapped)
                if status_val == 'resolved':
                    emergency.completed_at = datetime.now(UTC)
            emergency.chief_complaint = (
                request.form.get('chief_complaint') or emergency.chief_complaint
            )
            emergency.symptoms = request.form.get('symptoms') or emergency.symptoms
            vs = {
                'bp_systolic': request.form.get('vital_signs_bp_systolic'),
                'bp_diastolic': request.form.get('vital_signs_bp_diastolic'),
                'heart_rate': request.form.get('vital_signs_heart_rate'),
                'temperature': request.form.get('vital_signs_temperature'),
                'oxygen_saturation': request.form.get('vital_signs_oxygen_saturation'),
            }
            try:
                emergency.vital_signs = json.dumps(vs)
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')
            emergency.diagnosis = request.form.get('initial_assessment') or emergency.diagnosis
            emergency.treatment_plan = (
                request.form.get('treatment_given') or emergency.treatment_plan
            )
            emergency.notes = request.form.get('notes') or emergency.notes
            follow_up_required = bool(request.form.get('follow_up_required'))
            emergency.follow_up_required = (
                follow_up_required
                if hasattr(emergency, 'follow_up_required')
                else getattr(emergency, 'follow_up_required', False)
            )
            follow_up_date = request.form.get('follow_up_date')
            if follow_up_date and hasattr(emergency, 'follow_up_date'):
                try:
                    emergency.follow_up_date = datetime.strptime(follow_up_date, '%Y-%m-%d').date()
                except Exception as e:
                    logging.warning(f'Error in {__name__}: {e}')
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم تحديث حالة الطوارئ بنجاح', 'success')
            return redirect(url_for('emergency.view_emergency_case', id=emergency.id))
        doctors = db.session.execute(select(User).filter_by(role='doctor')).scalars().all()
        patients = db.session.execute(select(Patient)).scalars().all()
        emergency.emergency_date = emergency.created_at
        emergency.emergency_time = emergency.created_at
        emergency.doctor = (
            emergency.visit.doctor if emergency.visit and emergency.visit.doctor else None
        )
        try:
            emergency.vital_signs = (
                json.loads(emergency.vital_signs) if emergency.vital_signs else None
            )
        except Exception:
            emergency.vital_signs = None
        return render_template(
            'emergency/edit.html', emergency=emergency, doctors=doctors, patients=patients
        )
    except Exception as e:
        logging.exception(f'Error editing emergency case: {e!s}')
        flash('حدث خطأ في تعديل حالة الطوارئ', 'error')
        return redirect(url_for('emergency.list_emergency_cases'))


@emergency_bp.route('/cases/<int:id>/resolve', methods=['POST'])
@login_required
@role_required('emergency', 'manager')
def resolve_emergency_case(id):
    try:
        emergency = emergency_service.get_case(id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.list_emergency_cases'))
        _set_emergency_status(emergency, 'COMPLETED')
        emergency.completed_at = datetime.now(UTC)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        flash('تم حل الحالة بنجاح', 'success')
        return redirect(url_for('emergency.list_emergency_cases'))
    except Exception as e:
        logging.exception(f'Error resolving emergency case: {e!s}')
        flash('حدث خطأ في حل حالة الطوارئ', 'error')
        return redirect(url_for('emergency.list_emergency_cases'))


@emergency_bp.route('/cases/create', methods=['POST'])
@login_required
@role_required_json('emergency', 'manager')
def create_emergency_case():
    try:
        data = request.get_json(silent=True) if request.is_json else request.form
        patient_id = data.get('patient_id')
        if not patient_id:
            return jsonify({'success': False, 'message': 'رقم المريض مطلوب'}), 400
        try:
            patient_id = int(patient_id)
        except Exception:
            return jsonify({'success': False, 'message': 'رقم المريض غير صحيح'}), 400
        patient = db.session.execute(select(Patient).filter_by(id=patient_id)).scalars().first()
        if not patient:
            return jsonify({'success': False, 'message': 'المريض غير موجود'}), 404

        emergency_department_id = None
        try:
            from models.department import Department

            departments = (
                db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
            )
            for d in departments:
                if d.get_type() == 'emergency':
                    emergency_department_id = d.id
                    break
        except Exception:
            emergency_department_id = None

        visit = Visit(
            patient_id=patient_id,
            department_id=emergency_department_id,
            status='OPEN',
            visit_type='EMERGENCY',
            is_emergency=True,
            created_by=current_user.id,
        )
        db.session.add(visit)
        db.session.flush()
        case_number = f'EC-{visit.id}-{datetime.now(UTC).strftime("%Y%m%d%H%M%S")}'
        emergency = EmergencyCase(
            patient_id=patient_id,
            visit_id=visit.id,
            case_number=case_number,
            chief_complaint=data.get('case_description') or '',
            severity=(data.get('priority') or 'MODERATE').upper(),
            status='WAITING',
        )
        db.session.add(emergency)
        db.session.flush()
        try:
            from models.emergency_status_history import EmergencyStatusHistory

            db.session.add(
                EmergencyStatusHistory(
                    emergency_id=emergency.id,
                    from_status=None,
                    to_status='WAITING',
                    changed_by=current_user.id,
                )
            )
        except Exception as e:
            logging.warning(f'Error in {__name__}: {e}')
        try:
            from models.queue_management import QueueManagement

            if visit.department_id:
                qm = QueueManagement(
                    department_id=visit.department_id,
                    patient_id=patient_id,
                    visit_id=visit.id,
                    queue_number=str(visit.id),
                    priority_level='urgent',
                    status='waiting',
                    is_emergency=True,
                )
                db.session.add(qm)
        except Exception as e:
            logging.warning(f'Error in {__name__}: {e}')
        try:
            from models.patient_visit_counter import PatientVisitCounter

            pvc = (
                db.session.execute(select(PatientVisitCounter).filter_by(patient_id=patient_id))
                .scalars()
                .first()
            )
            if not pvc:
                pvc = PatientVisitCounter(patient_id=patient_id, visit_count=0)
                db.session.add(pvc)
            pvc.visit_count = (pvc.visit_count or 0) + 1
            from datetime import datetime as _dt

            pvc.last_visit_at = _dt.now(UTC)
        except Exception as e:
            logging.warning(f'Error in {__name__}: {e}')
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': True, 'visit_id': visit.id, 'case_id': emergency.id}), 200
    except Exception as e:
        logging.exception(f'Create emergency case error: {e!s}')
        safe_rollback(db.session, error_message='database rollback')
        return jsonify({'success': False, 'message': 'تعذر إنشاء حالة الطوارئ حالياً'}), 500


@emergency_bp.route('/cases/<int:id>/convert', methods=['POST'])
@login_required
@role_required('reception')
def convert_emergency_case(id):
    try:
        emergency = emergency_service.get_case(id)
        if not emergency:
            return jsonify({'success': False, 'message': 'حالة الطوارئ غير موجودة'}), 404
        visit = emergency.visit
        if not visit:
            return jsonify({'success': False, 'message': 'الزيارة غير موجودة'}), 404
        dest = (
            (request.get_json(silent=True) or {}).get('new_destination')
            if request.is_json
            else request.form.get('new_destination')
        )
        if not dest:
            return jsonify({'success': False, 'message': 'الوجهة مطلوبة'}), 400
        dest = str(dest).lower().strip()
        target_department_id = None
        target_doctor_id = visit.doctor_id
        try:
            from models.department import Department

            departments = (
                db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
            )
            if dest == 'lab':
                for d in departments:
                    if d.get_type() == 'lab':
                        target_department_id = d.id
                        break
            elif dest == 'radiology':
                for d in departments:
                    if d.get_type() == 'radiology':
                        target_department_id = d.id
                        break
            elif dest == 'doctor':
                for d in departments:
                    if d.get_type() == 'general':
                        target_department_id = d.id
                        break
            else:
                return jsonify({'success': False, 'message': 'الوجهة غير صحيحة'}), 400
        except Exception:
            target_department_id = None
        if not target_department_id:
            return jsonify({'success': False, 'message': 'القسم غير موجود'}), 404
        from services.queue_management_service import QueueManagementService

        ok, msg = QueueManagementService().transfer_visit(
            visit.id, target_department_id, target_doctor_id if dest == 'doctor' else None
        )
        if ok:
            return jsonify({'success': True}), 200
        status = 500
        if msg in {'invalid_department', 'doctor_required'}:
            status = 400
            msg = 'بيانات القسم أو الطبيب غير صحيحة'
        elif msg in {'visit_not_found', 'department_not_found'}:
            status = 404
            msg = 'الزيارة أو القسم غير موجود'
        elif msg == 'cannot_transfer_active_treatment':
            status = 409
            msg = 'لا يمكن تحويل زيارة قيد العلاج'
        elif not msg:
            msg = 'تعذر تحويل الزيارة حالياً'
        return jsonify({'success': False, 'message': msg}), status
    except Exception as e:
        logging.exception(f'Convert emergency case outer error: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر تحويل الحالة حالياً'}), 500
