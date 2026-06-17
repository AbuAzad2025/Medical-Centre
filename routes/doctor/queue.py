"""queue routes - extracted from monolithic doctor.py"""

from routes.doctor import doctor_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from models.appointment import Appointment
from models.follow_up import FollowUpRequest
from models.drug_interaction import DrugInteraction
from models.audit_trail import AuditTrail
from models.system_config import SystemConfig
from app_factory import db
from sqlalchemy import and_, or_, desc, func, case
import logging, json, secrets
from datetime import datetime, date, timedelta, timezone


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
        query = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status.in_(['OPEN', 'IN_PROGRESS'])
        ).order_by(Visit.visit_time)
        
        total = query.count()
        pages = (total + per_page - 1) // per_page
        
        patients = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # إحصائيات الطابور
        queue_stats = {
            'total_patients': total,
            'ready_patients': len([p for p in patients if p.status == 'OPEN']),
            'in_progress': len([p for p in patients if p.status == 'IN_PROGRESS']),
            'average_wait_time': 15
        }
        # إمكانية البدء لكل زيارة بناءً على حالة تذكرة الطابور (يجب أن تكون 'called')
        can_start_map = {}
        try:
            from models.queue_management import QueueManagement
            for v in patients:
                can_start_map[v.id] = bool(QueueManagement.query.filter_by(
                    visit_id=v.id,
                    department_id=v.department_id,
                    status='called'
                ).first())
        except Exception:
            for v in patients:
                can_start_map[v.id] = False

        today = date.today()
        todays_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status.in_(['OPEN','IN_PROGRESS'])
        ).all()
        linked_requests = []
        for v in todays_visits:
            lab_pending = LabRequest.query.filter(
                LabRequest.visit_id == v.id,
                LabRequest.status.in_(['REQUESTED','IN_PROGRESS'])
            ).count()
            rad_pending = RadiologyRequest.query.filter(
                RadiologyRequest.visit_id == v.id,
                RadiologyRequest.status.in_(['REQUESTED','IN_PROGRESS'])
            ).count()
            linked_requests.append({
                'visit_id': v.id,
                'patient_name': getattr(v.patient, 'full_name', 'غير محدد'),
                'lab_pending': lab_pending,
                'rad_pending': rad_pending
            })
        
        flash('لزيارة قسم أو طبيب آخر، يرجى إنشاء زيارة جديدة من الاستقبال', 'info')
        return render_template('doctor/patient_queue.html', 
                             patients=patients, 
                             queue_stats=queue_stats,
                             linked_requests=linked_requests,
                             can_start_map=can_start_map,
                             page=page,
                             pages=pages,
                             total=total)
    except Exception as e:
        logging.error(f"Error loading patient queue: {str(e)}")
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
        ticket = QueueManagement.query.filter_by(
            visit_id=visit_id,
            department_id=visit.department_id,
            status='waiting'
        ).order_by(QueueManagement.queued_at.desc()).first()

        if not ticket:
            flash('لا يوجد تذكرة طابور نشطة لهذا المريض', 'warning')
            return redirect(url_for('doctor.patient_queue'))

        ticket.status = 'called'
        from datetime import datetime, timezone
        ticket.called_at = datetime.now(timezone.utc)
        db.session.commit()

        flash(f'تم استدعاء المريض — التذكرة رقم {ticket.queue_number}', 'success')
    except Exception as e:
        logging.error(f"Error calling patient: {str(e)}")
        flash('حدث خطأ أثناء استدعاء المريض', 'error')

    return redirect(url_for('doctor.patient_queue'))
