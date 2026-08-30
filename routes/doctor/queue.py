"""queue routes - extracted from monolithic doctor.py"""

import logging
from datetime import UTC, date

# Imports
from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.shared.enums import OrderState, VisitState
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.visit import Visit
from routes.doctor import doctor_bp
from utils.db_safety import safe_commit
from utils.decorators import role_required

# =============================================
# QUEUE ROUTES
# =============================================


@doctor_bp.route('/patient-queue')
@login_required
@role_required('doctor', 'admin', 'manager')
def patient_queue():
    """طابور المرضى للطبيب - إدارة متقدمة"""

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

        flash('لزيارة قسم أو طبيب آخر، يرجى إنشاء زيارة جديدة من الاستقبال', 'info')
        return render_template(
            'doctor/patient_queue.html',
            patients=patients,
            queue_stats=queue_stats,
            linked_requests=linked_requests,
            can_start_map=can_start_map,
            page=page,
            pages=pages,
            total=total,
        )
    except Exception:
        logging.exception('Error loading patient queue: %s')
        flash('حدث خطأ في تحميل طابور المرضى', 'error')
        return redirect(url_for('doctor.dashboard'))


@doctor_bp.route('/call-patient/<int:visit_id>', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def call_patient(visit_id):
    """استدعاء مريض محدد للعلاج"""
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
        logging.exception('Error calling patient: %s')
        flash('حدث خطأ أثناء استدعاء المريض', 'error')

    return redirect(url_for('doctor.patient_queue'))
