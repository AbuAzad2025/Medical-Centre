"""queue routes - extracted from monolithic reception.py"""

import logging

# Imports
from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import AppointmentState, QueueState, VisitArchiveStatus, VisitState
from models.appointment import Appointment
from models.department import Department
from models.patient import Patient
from models.patient_satisfaction import PatientSatisfactionSurvey
from models.user import User
from models.visit import Visit
from routes.reception import reception_bp
from services.access_control_service import AccessControlService
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import (
    role_required,
)

# ═══════════════════════════════════════
# QUEUE ROUTES
# ═══════════════════════════════════════


@reception_bp.route('/display/waiting')
def waiting_display():
    return render_template('reception/waiting_display.html')


@reception_bp.route('/display/calls')
@login_required
@role_required('reception', 'super_admin', 'manager')
def calls_display():
    return render_template('reception/calls_display.html')


@reception_bp.route('/queue')
@login_required
@role_required('reception', 'manager')
def queue_management():
    """إدارة الطابور الموحد - الوحدة المركزية"""

    try:
        from models.department import Department
        from models.queue_management import QueueSettings
        from services.queue_management_service import QueueManagementService

        QueueManagementService()
        all_departments = (
            db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
        )

        dept_ids = AccessControlService.get_accessible_department_ids(current_user)
        if dept_ids is None:
            departments = all_departments
        elif dept_ids:
            departments = [d for d in all_departments if d.id in set(dept_ids)]
        else:
            departments = []

        settings_map = {}
        for dept in departments:
            s = (
                db.session.execute(select(QueueSettings).filter_by(department_id=dept.id))
                .scalars()
                .first()
            )
            settings_map[dept.id] = s.to_dict() if s else None
        can_manage_queue_settings = AccessControlService.has_permission(
            current_user, 'queue_settings_manage'
        )
        billing_active = 'billing' in getattr(g, 'enabled_modules', set())
        return render_template(
            'reception/queue_management.html',
            departments=departments,
            all_departments=all_departments
            if current_user.role in ['reception', 'super_admin', 'manager']
            else departments,
            queue_settings=settings_map,
            can_manage_queue_settings=can_manage_queue_settings,
            billing_active=billing_active,
        )
    except Exception as e:
        logging.exception(f'Error loading queue management: {e!s}')
        flash('حدث خطأ في تحميل إدارة الطابور', 'error')
        return redirect(url_for('reception.dashboard'))


@reception_bp.route('/queue/add-patient', methods=['GET', 'POST'])
@login_required
@role_required('reception')
def add_patient_to_queue():
    """إضافة مريض إلى الطابور - الوحدة المركزية"""

    if request.method == 'POST':
        try:
            from services.queue_management_service import QueueManagementService

            queue_service = QueueManagementService()

            # جلب البيانات من النموذج
            patient_id = request.form.get('patient_id')
            department_id = request.form.get('department_id')
            doctor_id = request.form.get('doctor_id') or None
            visit_id = request.form.get('visit_id') or None
            appointment_id = request.form.get('appointment_id') or None
            queue_type = request.form.get('queue_type', 'normal')
            is_emergency = 'is_emergency' in request.form
            emergency_reason = request.form.get('emergency_reason') if is_emergency else None
            # Ticket 1: force_entry and payment_status are resolved from the
            # authoritative server-side visit record, never from the form.

            # إلزام اختيار طبيب للأقسام التخصصية
            try:
                dept_obj = db.session.get(Department, int(department_id))
            except Exception:
                dept_obj = None
            if not dept_obj:
                flash('القسم غير موجود', 'error')
                return redirect(url_for('reception.queue_management'))
            if getattr(dept_obj, 'get_type', lambda: 'general')() == 'general' and not doctor_id:
                flash('يجب اختيار طبيب للقسم التخصصي', 'error')
                return redirect(url_for('reception.add_patient_to_queue'))

            # إضافة المريض إلى الطابور
            success, message = queue_service.add_patient_to_queue(
                patient_id=patient_id,
                department_id=department_id,
                doctor_id=doctor_id,
                visit_id=visit_id,
                appointment_id=appointment_id,
                queue_type=queue_type,
                is_emergency=is_emergency,
                emergency_reason=emergency_reason,
                created_by=current_user.id,
            )

            if success:
                flash(message, 'success')
            else:
                flash(message, 'error')
            return redirect(url_for('reception.queue_management'))
        except Exception as e:
            logging.exception(f'Error adding patient to queue: {e!s}')
            flash('تعذر إضافة المريض إلى الطابور، يرجى المحاولة مرة أخرى', 'error')
            return redirect(url_for('reception.queue_management'))

    # جلب البيانات المطلوبة للنموذج
    patients = db.session.execute(select(Patient)).scalars().all()
    departments = db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
    doctors = (
        db.session.execute(select(User).filter_by(role='doctor', is_active=True)).scalars().all()
    )
    visits = db.session.execute(select(Visit).filter_by(status='OPEN')).scalars().all()
    appointments = (
        db.session.execute(select(Appointment).filter_by(status='SCHEDULED')).scalars().all()
    )

    return render_template(
        'reception/add_patient_to_queue.html',
        patients=patients,
        departments=departments,
        doctors=doctors,
        visits=visits,
        appointments=appointments,
    )


@reception_bp.route('/queue/call-next/<int:department_id>')
@login_required
@role_required('reception')
def call_next_patient(department_id):
    """استدعاء المريض التالي"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        doctor_id = request.args.get('doctor_id', type=int)
        success, message = queue_service.call_next_patient(
            department_id=department_id, doctor_id=doctor_id, called_by=current_user.id
        )

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('reception.queue_management'))

    except Exception as e:
        logging.exception(f'Error calling next patient: {e!s}')
        flash('تعذر استدعاء المريض، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/queue/start-treatment/<int:ticket_id>')
@login_required
@role_required('reception')
def start_treatment(ticket_id):
    """بدء العلاج"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        success, message = queue_service.start_treatment(
            ticket_id=ticket_id, started_by=current_user.id
        )

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('reception.queue_management'))

    except Exception as e:
        logging.exception(f'Error starting treatment: {e!s}')
        flash('تعذر بدء العلاج، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/queue/complete-treatment/<int:ticket_id>')
@login_required
@role_required('reception')
def complete_treatment(ticket_id):
    """إكمال العلاج"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        success, message = queue_service.complete_treatment(
            ticket_id=ticket_id, completed_by=current_user.id
        )

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('reception.queue_management'))

    except Exception as e:
        logging.exception(f'Error completing treatment: {e!s}')
        flash('تعذر إكمال العلاج، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/queue/skip-patient/<int:ticket_id>', methods=['POST'])
@login_required
@role_required('reception')
def skip_patient(ticket_id):
    """تخطي المريض"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        reason = request.form.get('reason')

        success, message = queue_service.skip_patient(
            ticket_id=ticket_id, reason=reason, skipped_by=current_user.id
        )

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('reception.queue_management'))

    except Exception as e:
        logging.exception(f'Error skipping patient: {e!s}')
        flash('تعذر تخطي المريض، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/queue/return-to-queue/<int:ticket_id>', methods=['POST'])
@login_required
@role_required('reception')
def return_to_queue(ticket_id):
    """إرجاع المريض للطابور"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        reason = request.form.get('reason')
        success, message = queue_service.return_to_queue(
            ticket_id=ticket_id, reason=reason, returned_by=current_user.id
        )
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        return redirect(url_for('reception.queue_management'))
    except Exception as e:
        logging.exception(f'Error returning to queue: {e!s}')
        flash('تعذر إرجاع المريض للطابور، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/queue/cancel-ticket/<int:ticket_id>', methods=['POST'])
@login_required
@role_required('reception')
def cancel_ticket(ticket_id):
    """إلغاء التذكرة"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        reason = request.form.get('reason')

        success, message = queue_service.cancel_ticket(
            ticket_id=ticket_id, reason=reason, cancelled_by=current_user.id
        )

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('reception.queue_management'))

    except Exception as e:
        logging.exception(f'Error cancelling ticket: {e!s}')
        flash('تعذر إلغاء التذكرة، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/queue/approve-emergency-debt/<int:ticket_id>', methods=['POST'])
@login_required
@role_required('reception')
def approve_emergency_debt(ticket_id):
    """الموافقة على دين الطوارئ"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        max_amount = request.form.get('max_amount')
        max_amount = float(max_amount) if max_amount else None

        success, message = queue_service.approve_emergency_debt(
            ticket_id=ticket_id, approved_by=current_user.id, max_amount=max_amount
        )

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('reception.queue_management'))

    except Exception as e:
        logging.exception(f'Error approving emergency debt: {e!s}')
        flash('تعذر الموافقة على دين الطوارئ، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/queue/approve-force-entry/<int:ticket_id>', methods=['POST'])
@login_required
@role_required('reception')
def approve_force_entry(ticket_id):
    """الموافقة على الدخول القوي"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        reason = request.form.get('reason')

        success, message = queue_service.approve_force_entry(
            ticket_id=ticket_id, approved_by=current_user.id, reason=reason
        )

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')

        return redirect(url_for('reception.queue_management'))

    except Exception as e:
        logging.exception(f'Error approving force entry: {e!s}')
        flash('تعذر الموافقة على الدخول القوي، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/api/queue-status/<int:department_id>')
@login_required
def get_smart_queue_management(department_id=None):
    """إدارة الطابور الذكية"""
    try:
        from models.queue_management import QueueManagement

        # تحليل الطابور الحالي
        current_queue = (
            db.session.execute(
                select(QueueManagement)
                .filter(
                    QueueManagement.status.in_(
                        [QueueState.WAITING, QueueState.CALLED, QueueState.IN_PROGRESS]
                    )
                )
                .order_by(QueueManagement.created_at)
            )
            .scalars()
            .all()
        )

        # تحليل أوقات الانتظار
        avg_wait_time = (
            db.session.execute(select(func.avg(QueueManagement.estimated_wait_time))).scalar() or 0
        )

        # تحليل الأولويات
        priority_analysis = {
            'urgent': db.session.execute(
                select(func.count())
                .select_from(QueueManagement)
                .filter(QueueManagement.priority_level == 'urgent')
            ).scalar(),
            'normal': db.session.execute(
                select(func.count())
                .select_from(QueueManagement)
                .filter(QueueManagement.priority_level == 'normal')
            ).scalar(),
            'low': db.session.execute(
                select(func.count())
                .select_from(QueueManagement)
                .filter(QueueManagement.priority_level == 'low')
            ).scalar(),
        }

        # تحليل ساعات الذروة
        try:
            peak_hours = (
                db.session.execute(
                    select(
                        func.extract('hour', QueueManagement.created_at).label('hour'),
                        func.count(QueueManagement.id).label('count'),
                    ).group_by(func.extract('hour', QueueManagement.created_at))
                )
                .scalars()
                .all()
            )
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            peak_hours = []

        peak_hour = max(peak_hours, key=lambda x: x.count) if peak_hours else None

        return {
            'current_queue_length': len(current_queue),
            'avg_wait_time': round(avg_wait_time, 2),
            'priority_analysis': priority_analysis,
            'peak_hour': peak_hour.hour if peak_hour else None,
            'peak_count': peak_hour.count if peak_hour else 0,
            'efficiency_score': calculate_queue_efficiency(current_queue),
        }
    except Exception as e:
        logging.exception(f'Error getting smart queue management: {e!s}')
        return {}


def get_patient_flow_analysis():
    """تحليل تدفق المرضى"""
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import func

        from models.patient import Patient
        from models.visit import Visit

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        # تحليل التدفق اليومي
        daily_flow = []
        for i in range(7):
            date = today - timedelta(days=i)
            visits_count = db.session.execute(
                select(func.count()).select_from(Visit).filter(Visit.created_at == date)
            ).scalar()
            patients_count = db.session.execute(
                select(func.count())
                .select_from(Patient)
                .filter(Patient.created_at >= date, Patient.created_at < date + timedelta(days=1))
            ).scalar()
            daily_flow.append(
                {
                    'date': date.strftime('%Y-%m-%d'),
                    'visits': visits_count,
                    'new_patients': patients_count,
                }
            )

        # تحليل ساعات الذروة
        try:
            hourly_flow = (
                db.session.execute(
                    select(
                        func.extract('hour', Visit.created_at).label('hour'),
                        func.count(Visit.id).label('count'),
                    )
                    .filter(Visit.created_at >= week_ago)
                    .group_by(func.extract('hour', Visit.created_at))
                )
                .scalars()
                .all()
            )
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            hourly_flow = []

        # تحليل الأقسام
        department_flow = (
            db.session.execute(
                select(func.count(Visit.id).label('count'), Visit.department_id)
                .filter(Visit.created_at >= week_ago)
                .group_by(Visit.department_id)
            )
            .scalars()
            .all()
        )

        return {
            'daily_flow': daily_flow,
            'hourly_flow': [{'hour': h.hour, 'count': h.count} for h in hourly_flow],
            'department_flow': [
                {'department_id': d.department_id, 'count': d.count} for d in department_flow
            ],
            'trend': calculate_flow_trend(daily_flow),
        }
    except Exception as e:
        logging.exception(f'Error getting patient flow analysis: {e!s}')
        return {}


def get_appointment_optimization():
    """تحسين المواعيد"""
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import func

        from models.appointment import Appointment
        from models.user import User

        # تحليل المواعيد المتاحة
        today = datetime.now().date()
        week_ahead = today + timedelta(days=7)

        # تحليل كثافة المواعيد
        appointment_density = (
            db.session.execute(
                select(
                    func.date(Appointment.starts_at).label('appointment_date'),
                    func.count(Appointment.id).label('count'),
                )
                .filter(Appointment.starts_at >= today, Appointment.starts_at <= week_ahead)
                .group_by(func.date(Appointment.starts_at))
            )
            .scalars()
            .all()
        )

        # تحليل الأطباء
        doctor_workload = (
            db.session.execute(
                select(User.id, User.full_name, func.count(Appointment.id).label('appointments'))
                .join(Appointment, User.id == Appointment.doctor_id)
                .filter(Appointment.starts_at >= today, Appointment.starts_at <= week_ahead)
                .group_by(User.id, User.full_name)
            )
            .scalars()
            .all()
        )

        # اقتراحات التحسين
        optimizations = []

        # تحليل الأيام المزدحمة
        if appointment_density:
            max_day = max(appointment_density, key=lambda x: x.count)
            if max_day.count > 20:
                optimizations.append(
                    {
                        'type': 'scheduling',
                        'title': 'توزيع المواعيد',
                        'description': f'اليوم {max_day.appointment_date} مزدحم جداً ({max_day.count} موعد)',
                        'suggestion': 'توزيع المواعيد على أيام أخرى',
                    }
                )

        # تحليل عبء العمل
        if doctor_workload:
            max_doctor = max(doctor_workload, key=lambda x: x.appointments)
            if max_doctor.appointments > 15:
                optimizations.append(
                    {
                        'type': 'workload',
                        'title': 'توزيع عبء العمل',
                        'description': f'الطبيب {max_doctor.full_name} محمل بكثرة ({max_doctor.appointments} موعد)',
                        'suggestion': 'إعادة توزيع المواعيد أو إضافة طبيب آخر',
                    }
                )

        return {
            'appointment_density': [
                {'date': str(d.appointment_date), 'count': d.count} for d in appointment_density
            ],
            'doctor_workload': [
                {'doctor_id': d.id, 'doctor_name': d.full_name, 'appointments': d.appointments}
                for d in doctor_workload
            ],
            'optimizations': optimizations,
        }
    except Exception as e:
        logging.exception(f'Error getting appointment optimization: {e!s}')
        return {}


def get_real_time_alerts():
    """التنبيهات في الوقت الفعلي"""
    try:
        from datetime import datetime, timedelta

        from models.appointment import Appointment
        from models.visit import Visit

        alerts = []

        # تنبيهات المواعيد
        today = datetime.now().date()
        overdue_appointments = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(Appointment.starts_at < today, Appointment.status == AppointmentState.SCHEDULED)
        ).scalar()

        if overdue_appointments > 0:
            alerts.append(
                {
                    'type': 'appointment',
                    'priority': 'high',
                    'title': 'مواعيد متأخرة',
                    'message': f'يوجد {overdue_appointments} موعد متأخر',
                    'action': 'مراجعة المواعيد المتأخرة',
                }
            )

        # تنبيهات الطابور
        long_waiting = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.status == VisitState.PENDING,
                Visit.created_at < datetime.now() - timedelta(hours=2),
            )
        ).scalar()

        if long_waiting > 0:
            alerts.append(
                {
                    'type': 'queue',
                    'priority': 'medium',
                    'title': 'انتظار طويل',
                    'message': f'يوجد {long_waiting} مريض ينتظر أكثر من ساعتين',
                    'action': 'مراجعة الطابور',
                }
            )

        # تنبيهات السعة
        today_visits = db.session.execute(
            select(func.count()).select_from(Visit).filter(Visit.created_at >= today)
        ).scalar()
        if today_visits > 50:
            alerts.append(
                {
                    'type': 'capacity',
                    'priority': 'medium',
                    'title': 'سعة عالية',
                    'message': f'عدد الزيارات اليوم: {today_visits} - قريب من السعة القصوى',
                    'action': 'مراقبة الأداء',
                }
            )

        return alerts
    except Exception as e:
        logging.exception(f'Error getting real-time alerts: {e!s}')
        return []


def get_workflow_automation():
    """أتمتة سير العمل"""
    try:
        from datetime import datetime, timedelta

        from models.appointment import Appointment
        from models.patient import Patient
        from models.visit import Visit

        automation_suggestions = []

        # أتمتة المواعيد المتكررة
        recurring_patients = (
            db.session.execute(
                select(Patient.id, func.count(Visit.id).label('visit_count'))
                .join(Visit, Patient.id == Visit.patient_id)
                .filter(Visit.created_at >= datetime.now().date() - timedelta(days=30))
                .group_by(Patient.id)
                .having(func.count(Visit.id) > 3)
            )
            .scalars()
            .all()
        )

        if recurring_patients:
            automation_suggestions.append(
                {
                    'type': 'recurring_appointments',
                    'title': 'المواعيد المتكررة',
                    'description': f'يوجد {len(recurring_patients)} مريض يحتاج مواعيد متكررة',
                    'suggestion': 'إعداد مواعيد تلقائية للمرضى المتكررين',
                }
            )

        # أتمتة التذكيرات
        tomorrow_appointments = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(
                Appointment.starts_at >= datetime.now().date() + timedelta(days=1),
                Appointment.starts_at < datetime.now().date() + timedelta(days=2),
            )
        ).scalar()

        if tomorrow_appointments > 0:
            automation_suggestions.append(
                {
                    'type': 'reminders',
                    'title': 'التذكيرات التلقائية',
                    'description': f'يوجد {tomorrow_appointments} موعد غداً',
                    'suggestion': 'إرسال تذكيرات تلقائية للمرضى',
                }
            )

        # أتمتة المتابعة
        completed_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.archive_status == VisitArchiveStatus.ARCHIVED,
                Visit.completed_at >= datetime.now() - timedelta(days=7),
            )
        ).scalar()

        if completed_visits > 10:
            automation_suggestions.append(
                {
                    'type': 'follow_up',
                    'title': 'المتابعة التلقائية',
                    'description': f'تم إنجاز {completed_visits} زيارة هذا الأسبوع',
                    'suggestion': 'إعداد نظام متابعة تلقائي للمرضى',
                }
            )

        return automation_suggestions
    except Exception as e:
        logging.exception(f'Error getting workflow automation: {e!s}')
        return []


def get_patient_satisfaction_ai():
    """ذكاء اصطناعي لرضا المرضى"""
    try:
        from sqlalchemy import func

        from models.queue_management import QueueManagement
        from models.visit import Visit

        # تحليل عوامل الرضا
        total_visits = db.session.execute(select(func.count()).select_from(Visit)).scalar()
        completed_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(Visit.archive_status == VisitArchiveStatus.ARCHIVED)
        ).scalar()

        # معدل الإنجاز
        completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0

        # متوسط وقت الانتظار
        avg_wait_time = (
            db.session.execute(select(func.avg(QueueManagement.estimated_wait_time))).scalar() or 0
        )

        # تحليل التكرار
        repeat_visits = db.session.execute(
            select(Visit.patient_id, func.count(Visit.id).label('visit_count'))
            .group_by(Visit.patient_id)
            .having(func.count(Visit.id) > 1)
        ).scalar()

        satisfaction_score = calculate_satisfaction_score(
            completion_rate, avg_wait_time, repeat_visits
        )

        avg_rating = db.session.execute(
            select(func.avg(PatientSatisfactionSurvey.rating)).filter(
                PatientSatisfactionSurvey.rating.isnot(None)
            )
        ).scalar()
        rating_count = (
            db.session.execute(
                select(func.count(PatientSatisfactionSurvey.id)).filter(
                    PatientSatisfactionSurvey.rating.isnot(None)
                )
            ).scalar()
            or 0
        )
        rating_score = (float(avg_rating or 0) / 5 * 100) if avg_rating else None
        if rating_score is not None:
            satisfaction_score = (satisfaction_score * 0.6) + (rating_score * 0.4)

        # توصيات التحسين
        recommendations = []

        if completion_rate < 80:
            recommendations.append(
                {
                    'type': 'completion',
                    'title': 'تحسين معدل الإنجاز',
                    'description': f'معدل إنجاز الزيارات: {completion_rate:.1f}%',
                    'suggestion': 'تحسين كفاءة العمليات',
                }
            )

        if avg_wait_time > 30:
            recommendations.append(
                {
                    'type': 'wait_time',
                    'title': 'تقليل أوقات الانتظار',
                    'description': f'متوسط وقت الانتظار: {avg_wait_time:.1f} دقيقة',
                    'suggestion': 'تحسين تدفق المرضى',
                }
            )

        if avg_rating and avg_rating < 3.5:
            recommendations.append(
                {
                    'type': 'survey',
                    'title': 'تحسين رضا المرضى',
                    'description': f'متوسط التقييم: {avg_rating:.2f} من 5',
                    'suggestion': 'تحليل الملاحظات وتحسين التجربة',
                }
            )

        return {
            'satisfaction_score': round(satisfaction_score, 2),
            'avg_rating': round(float(avg_rating), 2) if avg_rating else None,
            'rating_count': int(rating_count),
            'completion_rate': round(completion_rate, 2),
            'avg_wait_time': round(avg_wait_time, 2),
            'repeat_visits': repeat_visits,
            'recommendations': recommendations,
            'status': 'excellent'
            if satisfaction_score > 90
            else 'good'
            if satisfaction_score > 70
            else 'needs_improvement',
        }
    except Exception as e:
        logging.exception(f'Error getting patient satisfaction AI: {e!s}')
        return {}


def get_patient_demand_forecast(hours_ahead=4, days_window=14):
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import func

        from models.visit import Visit

        now = datetime.now()
        start_date = now - timedelta(days=days_window)

        hourly = []
        try:
            hourly = (
                db.session.execute(
                    select(
                        func.extract('hour', Visit.created_at).label('hour'),
                        func.count(Visit.id).label('count'),
                    )
                    .filter(Visit.created_at >= start_date)
                    .group_by(func.extract('hour', Visit.created_at))
                )
                .scalars()
                .all()
            )
        except Exception:
            hourly = (
                db.session.execute(
                    select(
                        func.extract('hour', Visit.created_at).label('hour'),
                        func.count(Visit.id).label('count'),
                    )
                    .filter(Visit.created_at >= start_date)
                    .group_by(func.extract('hour', Visit.created_at))
                )
                .scalars()
                .all()
            )

        avg_by_hour = {}
        for h in hourly:
            hour_val = int(getattr(h, 'hour', None) or 0)
            avg_by_hour[hour_val] = float(h.count or 0) / float(days_window)

        next_hours = []
        for i in range(hours_ahead):
            hour = (now.hour + i) % 24
            next_hours.append({'hour': hour, 'expected': round(avg_by_hour.get(hour, 0), 2)})

        expected_total = round(sum(h['expected'] for h in next_hours), 2)

        return {
            'hours_ahead': hours_ahead,
            'expected_total': expected_total,
            'next_hours': next_hours,
        }
    except Exception as e:
        logging.exception(f'Error getting patient demand forecast: {e!s}')
        return {}


def get_resource_planning():
    """تخطيط الموارد"""
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import func

        from models.appointment import Appointment
        from models.user import User
        from models.visit import Visit

        # تحليل الموظفين
        total_staff = db.session.execute(select(func.count()).select_from(User)).scalar()
        active_staff = db.session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.last_login >= datetime.now() - timedelta(days=7))
        ).scalar()

        # تحليل الأطباء
        total_doctors = db.session.execute(
            select(func.count()).select_from(User).filter(User.role == 'doctor')
        ).scalar()
        active_doctors = db.session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.role == 'doctor', User.last_login >= datetime.now() - timedelta(days=7))
        ).scalar()

        # تحليل الأحمال
        today = datetime.now().date()
        today_visits = db.session.execute(
            select(func.count()).select_from(Visit).filter(Visit.created_at >= today)
        ).scalar()
        tomorrow_appointments = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(
                Appointment.starts_at >= today + timedelta(days=1),
                Appointment.starts_at < today + timedelta(days=2),
            )
        ).scalar()

        # حساب الكفاءة
        efficiency_score = (active_staff / total_staff * 100) if total_staff > 0 else 0

        # توصيات التخطيط
        planning_recommendations = []

        if efficiency_score < 70:
            planning_recommendations.append(
                {
                    'type': 'staff_engagement',
                    'title': 'تحسين مشاركة الموظفين',
                    'description': f'معدل المشاركة: {efficiency_score:.1f}%',
                    'suggestion': 'تحفيز الموظفين أو إعادة توزيع المهام',
                }
            )

        if today_visits > 30:
            planning_recommendations.append(
                {
                    'type': 'capacity_planning',
                    'title': 'تخطيط السعة',
                    'description': f'عدد الزيارات اليوم: {today_visits}',
                    'suggestion': 'مراجعة القدرة الاستيعابية',
                }
            )

        return {
            'total_staff': total_staff,
            'active_staff': active_staff,
            'total_doctors': total_doctors,
            'active_doctors': active_doctors,
            'today_visits': today_visits,
            'tomorrow_appointments': tomorrow_appointments,
            'efficiency_score': round(efficiency_score, 2),
            'planning_recommendations': planning_recommendations,
        }
    except Exception as e:
        logging.exception(f'Error getting resource planning: {e!s}')
        return {}


def get_smart_recommendations():
    """التوصيات الذكية"""
    try:
        from datetime import datetime, timedelta

        from models.patient import Patient
        from models.visit import Visit

        recommendations = []

        # تحليل النمو
        week_ago = datetime.now().date() - timedelta(days=7)
        new_patients_week = db.session.execute(
            select(func.count()).select_from(Patient).filter(Patient.created_at >= week_ago)
        ).scalar()

        if new_patients_week > 20:
            recommendations.append(
                {
                    'type': 'growth',
                    'title': 'نمو سريع',
                    'description': f'تم تسجيل {new_patients_week} مريض جديد هذا الأسبوع',
                    'suggestion': 'مراجعة القدرة الاستيعابية والموارد',
                }
            )

        # تحليل المواعيد
        no_show_rate = calculate_no_show_rate()
        if no_show_rate > 20:
            recommendations.append(
                {
                    'type': 'no_show',
                    'title': 'معدل عدم الحضور',
                    'description': f'معدل عدم الحضور: {no_show_rate:.1f}%',
                    'suggestion': 'تحسين نظام التذكيرات',
                }
            )

        # تحليل الكفاءة
        try:
            avg_visit_duration = (
                db.session.execute(
                    select(
                        func.avg(
                            (
                                func.extract('epoch', Visit.completed_at)
                                - func.extract('epoch', Visit.created_at)
                            )
                            / 60.0
                        )
                    ).filter(Visit.completed_at.isnot(None))
                ).scalar()
                or 0
            )
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            avg_visit_duration = 0
        if avg_visit_duration > 45:
            recommendations.append(
                {
                    'type': 'efficiency',
                    'title': 'تحسين الكفاءة',
                    'description': f'متوسط مدة الزيارة: {avg_visit_duration:.1f} دقيقة',
                    'suggestion': 'تحسين العمليات لتقليل مدة الزيارة',
                }
            )

        return recommendations
    except Exception as e:
        logging.exception(f'Error getting smart recommendations: {e!s}')
        return []


# دوال مساعدة
def calculate_queue_efficiency(queue):
    """حساب كفاءة الطابور"""
    if not queue:
        return 100

    completed = len([t for t in queue if t.status == QueueState.COMPLETED])
    total = len(queue)
    return (completed / total * 100) if total > 0 else 0


def calculate_flow_trend(daily_flow):
    """حساب اتجاه التدفق"""
    if len(daily_flow) < 2:
        return 'stable'

    recent = daily_flow[0]['visits']
    previous = daily_flow[1]['visits']

    if recent > previous * 1.1:
        return 'growing'
    if recent < previous * 0.9:
        return 'declining'
    return 'stable'


def calculate_satisfaction_score(completion_rate, avg_wait_time, repeat_visits):
    """حساب نقاط الرضا"""
    # نقاط الإنجاز
    completion_score = completion_rate

    # نقاط وقت الانتظار (كلما قل الوقت كلما زادت النقاط)
    wait_score = max(0, 100 - (avg_wait_time / 60 * 20))

    # نقاط التكرار (كلما زاد التكرار كلما زادت النقاط)
    repeat_score = min(100, repeat_visits * 5)

    return (completion_score + wait_score + repeat_score) / 3


def calculate_no_show_rate():
    """حساب معدل عدم الحضور"""
    try:
        from models.appointment import Appointment

        total_appointments = db.session.execute(
            select(func.count()).select_from(Appointment)
        ).scalar()
        no_show_appointments = db.session.execute(
            select(func.count()).select_from(Appointment).filter(Appointment.status == 'no_show')
        ).scalar()
        return (no_show_appointments / total_appointments * 100) if total_appointments > 0 else 0
    except (TypeError, ValueError, ZeroDivisionError) as e:
        logging.exception(f'calculate_no_show_rate failed: {e}')
        return 0


# ===== وظائف مساعدة لتطبيق قيود البحث =====


def add_patient_to_queue_auto(visit_id, department_id, doctor_id=None):
    """إضافة المريض للطابور تلقائياً.

    Ticket 1: payment_status and is_emergency are resolved from the
    authoritative server-side visit record inside add_patient_to_queue.
    force_entry is removed; manager force-payment approval is never a
    queue-entry bypass.
    """
    try:
        from services.queue_management_service import QueueManagementService
        from utils.tenant_query import TenantContextError, get_tenant_record

        queue_service = QueueManagementService()

        # tenant-safe visit lookup (resolved inside the service as well)
        try:
            visit = get_tenant_record(Visit, int(visit_id))
        except (TenantContextError, Exception):
            return False, 'الزيارة غير موجودة'
        if not visit:
            return False, 'الزيارة غير موجودة'

        is_emergency = (
            bool(getattr(visit, 'is_emergency', False))
            or str(getattr(visit, 'visit_type', '') or '').upper() == 'EMERGENCY'
        )
        emergency_reason = (
            (getattr(visit, 'symptoms', None) or '').strip() if is_emergency else None
        )

        # إضافة المريض للطابور
        return queue_service.add_patient_to_queue(
            patient_id=visit.patient_id,
            department_id=department_id,
            doctor_id=doctor_id,
            visit_id=visit_id,
            queue_type='normal',
            is_emergency=is_emergency,
            emergency_reason=emergency_reason,
        )

    except Exception as e:
        logging.exception(f'Error adding patient to queue: {e!s}')
        return False, f'خطأ في النظام: {e!s}'


@reception_bp.route('/queue/save-settings/<int:department_id>', methods=['POST'])
@login_required
@AccessControlService.require_permission('queue_settings_manage')
def save_queue_settings(department_id):
    """حفظ إعدادات الطابور للقسم"""
    try:
        from models.department import Department
        from models.queue_management import QueueSettings

        dept = db.session.get(Department, department_id)
        if not dept:
            flash('القسم غير موجود', 'error')
            return redirect(url_for('reception.queue_management'))
        settings = (
            db.session.execute(select(QueueSettings).filter_by(department_id=department_id))
            .scalars()
            .first()
        )
        if not settings:
            settings = QueueSettings(department_id=department_id)
            db.session.add(settings)
            db.session.flush()
        # تحديث القيم من النموذج
        settings.payment_required = 'payment_required' in request.form
        settings.allow_partial_payment = 'allow_partial_payment' in request.form
        settings.allow_debt = 'allow_debt' in request.form
        settings.emergency_payment_waived = 'emergency_payment_waived' in request.form
        settings.force_entry_allowed = 'force_entry_allowed' in request.form
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        flash('تم حفظ إعدادات الطابور للقسم.', 'success')
        return redirect(url_for('reception.queue_management'))
    except Exception as e:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception(f'Error saving queue settings: {e!s}')
        flash('حدث خطأ في حفظ الإعدادات', 'error')
        return redirect(url_for('reception.queue_management'))
