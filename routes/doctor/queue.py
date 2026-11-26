"""queue routes - extracted from monolithic doctor.py"""

import logging
from datetime import UTC, date

# Imports
from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.shared.enums import OrderState, PaymentStatus, VisitState
from models.department import Department
from models.lab_request import LabRequest
from models.medical_record import MedicalRecord
from models.online_booking import OnlineBooking
from models.patient import Patient
from models.radiology_request import RadiologyRequest
from models.visit import Visit
from routes.doctor import doctor_bp
from services.feature_gate_service import FeatureGateService
from services.reception_service import ReceptionService
from services.visit_state_machine_service import VisitStateMachineService
from utils.db_safety import safe_commit
from utils.decorators import role_required
from utils.tenant_query import get_tenant_record

# QUEUE ROUTES


@doctor_bp.route('/patient-queue', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def patient_queue():
    """طابور المرضى للطبيب - إدارة متقدمة"""

    reception_enabled = (
        FeatureGateService.module_enabled(g.tenant_id, 'reception') if g.tenant_id else False
    )

    # One route for every package: in a clinic without reception the same
    # queue screen also registers the walk-in patient and opens the visit.
    if request.method == 'POST' and not reception_enabled:
        patient = None
        patient_id = request.form.get('patient_id', type=int)
        if patient_id:
            try:
                patient = get_tenant_record(Patient, patient_id)
            except Exception:
                patient = None
        if patient is None:
            first_name = (request.form.get('first_name') or '').strip()
            last_name = (request.form.get('last_name') or '').strip()
            phone = (request.form.get('phone') or '').strip()
            if not first_name or not phone:
                flash('الاسم ورقم الهاتف مطلوبان لمريض جديد', 'warning')
                return redirect(url_for('doctor.patient_queue'))
            patient = ReceptionService.register_patient(
                {'first_name': first_name, 'last_name': last_name, 'phone': phone}
            )
        if patient is None:
            flash('تعذر تسجيل المريض', 'error')
            return redirect(url_for('doctor.patient_queue'))

        department_id = request.form.get('department_id', type=int) or current_user.department_id
        if not department_id:
            department = (
                db.session.execute(
                    select(Department)
                    .filter_by(tenant_id=g.tenant_id, is_active=True)
                    .order_by(Department.id)
                )
                .scalars()
                .first()
            )
            department_id = department.id if department else None
        if not department_id:
            flash('لا يوجد قسم نشط لتسجيل الزيارة', 'error')
            return redirect(url_for('doctor.patient_queue'))

        visit = Visit(
            patient_id=patient.id,
            department_id=department_id,
            doctor_id=current_user.id,
            visit_type='OUTPATIENT',
            status=VisitState.OPEN.value,
            payment_status=PaymentStatus.PAID.value,
            visit_date=date.today(),
            chief_complaint=(request.form.get('chief_complaint') or '').strip() or None,
        )
        db.session.add(visit)
        db.session.flush()
        if not safe_commit(db.session, error_message='Failed to create walk-in visit'):
            flash('تعذر إنشاء الزيارة', 'error')
            return redirect(url_for('doctor.patient_queue'))

        # Entering a patient means starting care immediately — no extra stop
        # at the queue. Reuse the same validated state machine as the doctor
        # treatment route.
        for target in (VisitState.CHECKED_IN, VisitState.IN_PROGRESS):
            if VisitStateMachineService.can_transition(visit, target):
                VisitStateMachineService.transition(visit, target, actor=current_user)
        db.session.add(
            MedicalRecord(
                patient_id=visit.patient_id,
                visit_id=visit.id,
                title='بدء العلاج',
                details=f'تم بدء العلاج من قبل الطبيب: {current_user.full_name}',
                created_by=current_user.id,
            )
        )
        safe_commit(db.session, error_message='Failed to start treatment')
        flash('تم تسجيل المريض وبدء العلاج مباشرة', 'success')
        return redirect(url_for('doctor.patient_details', visit_id=visit.id))

    page = request.args.get('page', 1, type=int)
    per_page = 25

    try:
        # جلب المرضى المخصصين للطبيب مع تفاصيل إضافية
        query = select(Visit).filter(
            Visit.doctor_id == current_user.id,
            Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]),
            Visit.tenant_id == g.tenant_id if hasattr(Visit, 'tenant_id') and g.tenant_id else True,
        )

        total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
        pages = (total + per_page - 1) // per_page

        patients = (
            db.session.execute(query.offset((page - 1) * per_page).limit(per_page)).scalars().all()
        )

        # إحصائيات الطابور
        queue_stats = {
            'total_patients': total,
            'ready_patients': len([p for p in patients if p.status == VisitState.OPEN]),
            'in_progress': len([p for p in patients if p.status == VisitState.IN_PROGRESS]),
            'average_wait_time': 15,
        }
        # إمكانية البدء لكل زيارة بناءً على حالة تذكرة الطابور (يجب أن تكون 'called')
        can_start_map = {}
        try:
            from models.queue_management import QueueManagement

            if patients:
                patient_ids = [v.id for v in patients]
                dept_ids = [v.department_id for v in patients]
                called_queues = (
                    db.session.execute(
                        select(QueueManagement).filter(
                            QueueManagement.visit_id.in_(patient_ids),
                            QueueManagement.department_id.in_(dept_ids),
                            QueueManagement.status == 'called',
                        )
                    )
                    .scalars()
                    .all()
                )
                can_start_map = {q.visit_id: True for q in called_queues}
        except Exception:
            pass
        for v in patients:
            if v.id not in can_start_map:
                can_start_map[v.id] = False

        # Solo clinics have no reception module, so no queue ticket can exist.
        # The doctor starts treatment directly on the open visit in that case.
        if not reception_enabled:
            for v in patients:
                if v.status == VisitState.OPEN:
                    can_start_map[v.id] = True

        today = date.today()
        todays_visits = (
            db.session.execute(
                select(Visit)
                .options(joinedload(Visit.patient))
                .filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date == today,
                    Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]),
                    Visit.tenant_id == g.tenant_id
                    if hasattr(Visit, 'tenant_id') and g.tenant_id
                    else True,
                )
            )
            .scalars()
            .all()
        )
        linked_requests = []
        if todays_visits:
            visit_ids = [v.id for v in todays_visits]
            lab_counts = dict(
                db.session.execute(
                    select(LabRequest.visit_id, func.count(LabRequest.id))
                    .filter(
                        LabRequest.visit_id.in_(visit_ids),
                        LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
                    )
                    .group_by(LabRequest.visit_id)
                ).all()
            )
            rad_counts = dict(
                db.session.execute(
                    select(RadiologyRequest.visit_id, func.count(RadiologyRequest.id))
                    .filter(
                        RadiologyRequest.visit_id.in_(visit_ids),
                        RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
                    )
                    .group_by(RadiologyRequest.visit_id)
                ).all()
            )
            for v in todays_visits:
                linked_requests.append(
                    {
                        'visit_id': v.id,
                        'patient_name': getattr(v.patient, 'full_name', 'غير محدد'),
                        'lab_pending': lab_counts.get(v.id, 0),
                        'rad_pending': rad_counts.get(v.id, 0),
                    }
                )

        if reception_enabled:
            flash('لزيارة قسم أو طبيب آخر، يرجى إنشاء زيارة جديدة من الاستقبال', 'info')
        return render_template(
            'doctor/patient_queue.html',
            patients=patients,
            queue_stats=queue_stats,
            linked_requests=linked_requests,
            can_start_map=can_start_map,
            reception_enabled=reception_enabled,
            walkin_departments=(
                []
                if reception_enabled
                else db.session.execute(
                    select(Department)
                    .filter_by(tenant_id=g.tenant_id, is_active=True)
                    .order_by(Department.id)
                )
                .scalars()
                .all()
            ),
            walkin_patients=(
                []
                if reception_enabled
                else db.session.execute(
                    select(Patient)
                    .filter_by(tenant_id=g.tenant_id)
                    .order_by(Patient.id.desc())
                    .limit(50)
                )
                .scalars()
                .all()
            ),
            pending_bookings=(
                []
                if reception_enabled
                else db.session.execute(
                    select(OnlineBooking)
                    .filter_by(tenant_id=g.tenant_id, status='pending')
                    .order_by(OnlineBooking.appointment_date.asc())
                    .limit(20)
                )
                .scalars()
                .all()
            ),
            page=page,
            pages=pages,
            total=total,
        )
    except Exception:
        logging.exception('Error loading patient queue')
        flash('حدث خطأ في تحميل طابور المرضى', 'error')
        return redirect(url_for('doctor.dashboard'))


@doctor_bp.route('/call-patient/<int:visit_id>', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def call_patient(visit_id):
    """استدعاء مريض محدد للعلاج"""
    if 'reception' not in getattr(g, 'enabled_modules', set()):
        flash('لا يوجد طابور استقبال في باقتك — ابدأ العلاج مباشرة من الزيارة', 'info')
        return redirect(url_for('doctor.patient_queue'))
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))

        from models.queue_management import QueueManagement

        ticket = (
            db.session.execute(
                select(QueueManagement)
                .filter_by(visit_id=visit_id, department_id=visit.department_id, status='waiting')
                .order_by(QueueManagement.queued_at.desc())
            )
            .scalars()
            .first()
        )

        if not ticket:
            flash('لا يوجد تذكرة طابور نشطة لهذا المريض', 'warning')
            return redirect(url_for('doctor.patient_queue'))

        ticket.status = 'called'
        from datetime import datetime

        ticket.called_at = datetime.now(UTC)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        flash(f'تم استدعاء المريض — التذكرة رقم {ticket.queue_number}', 'success')
    except Exception:
        logging.exception('Error calling patient')
        flash('حدث خطأ أثناء استدعاء المريض', 'error')

    return redirect(url_for('doctor.patient_queue'))
