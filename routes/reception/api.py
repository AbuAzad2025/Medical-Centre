"""api routes - extracted from monolithic reception.py"""

from routes.reception import reception_bp

# Imports
 
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timezone
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.follow_up import FollowUpRequest
from models.online_booking import OnlineBooking
from models.department import Department
from models.payment import Payment, PaymentMethod, PaymentStatus
from models.queue_management import QueueManagement
from models.patient_satisfaction import PatientSatisfactionSurvey
from services.gatekeeper_service import GatekeeperService
from services.reception_service import reception_service
from utils.decorators import can_create_visits, reception_only, role_required, role_required_json, can_modify_patient_data, can_delete_patient
from app_factory import db
import logging
from services.access_control_service import AccessControlService
from services.pos_terminal_service import PosTerminalService



# ═══════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════

@reception_bp.route('/api/doctors')
@login_required
def api_doctors():
    """API لجلب الأطباء"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    
    department_id = request.args.get('department_id')
    appointment_type = request.args.get('appointment_type')
    
    query = User.query.filter_by(role='doctor', is_active=True)
    
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    doctors = query.all()
    
    return jsonify({
        'success': True,
        'doctors': [{'id': doctor.id, 'full_name': doctor.full_name} for doctor in doctors]
    })

@reception_bp.route('/api/department-staff')
@login_required
def api_department_staff():
    """API لجلب موظفي القسم المناسبين"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'error': 'ليس لديك الصلاحيات'}), 403
    
    department_id = request.args.get('department_id', type=int)
    if not department_id:
        return jsonify({'error': 'معرف القسم مطلوب'}), 400
    
    try:
        # جلب موظفي القسم حسب نوع القسم
        department = db.session.get(Department, department_id)
        if not department:
            return jsonify({'error': 'القسم غير موجود'}), 404
        
        dept_type = department.get_type()
        roles = ['doctor']
        if dept_type == 'lab':
            roles = ['lab', 'technician', 'nurse']
        elif dept_type == 'radiology':
            roles = ['radiology', 'technician', 'nurse']
        elif dept_type == 'emergency':
            roles = ['emergency', 'doctor', 'nurse']
        
        # 1. موظفو القسم مباشرة بصرف النظر عن الدور
        from sqlalchemy import or_
        direct_staff = User.query.filter(
            User.department_id == department_id,
            User.is_active == True
        ).all()
        
        # 2. موظفون بدون قسم ودورهم يناسب نوع القسم
        unassigned = User.query.filter(
            User.role.in_(roles),
            User.is_active == True,
            User.department_id.is_(None)
        ).all()
        
        # دمج بدون تكرار
        seen_ids = set()
        staff = []
        for p in direct_staff + unassigned:
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                staff.append(p)
        
        results = []
        for person in staff:
            results.append({
                'id': person.id,
                'full_name': person.full_name,
                'role': person.role,
                'specialization': getattr(person, 'specialization', ''),
                'phone': getattr(person, 'phone', '')
            })
        
        return jsonify({'staff': results})
    except Exception as e:
        logging.error(f"Error getting department staff: {str(e)}")
        return jsonify({'error': 'حدث خطأ في جلب الموظفين'}), 500

@reception_bp.route('/api/department-services')
@login_required

def api_department_services():
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'error': 'ليس لديك الصلاحيات'}), 403
    department_id = request.args.get('department_id', type=int)
    if not department_id:
        return jsonify({'error': 'القسم مطلوب'}), 400
    dept = db.session.get(Department, department_id)
    if not dept:
        return jsonify({'error': 'القسم غير موجود'}), 404
    from models.service import ServiceMaster
    from sqlalchemy import or_ as _or
    dt = dept.get_type()
    category = 'doctor' if dt == 'general' else dt
    # أولاً: خدمات هذا القسم تحديداً
    services = ServiceMaster.query.filter(
        ServiceMaster.category == category,
        ServiceMaster.is_active == True,
        ServiceMaster.department_id == department_id
    ).order_by(ServiceMaster.name_ar).all()
    # إذا لم توجد خدمات مرتبطة بالقسم، أرجع كل خدمات الفئة
    if not services:
        services = ServiceMaster.query.filter(
            ServiceMaster.category == category,
            ServiceMaster.is_active == True
        ).order_by(ServiceMaster.name_ar).all()
    resp = {
        'category': category,
        'services': [
            {
                'id': s.id,
                'code': s.code,
                'name': s.name,
                'name_ar': s.name_ar or s.name,
                'base_price': float(s.base_price or 0),
                'insurance_price': float(s.insurance_price or 0),
                'price': float(s.base_price or 0)
            } for s in services
        ]
    }
    return jsonify(resp)

@reception_bp.route('/api/queue-department-status/<int:department_id>')
@login_required

def api_queue_status(department_id):
    """API لحالة الطابور"""
    if current_user.role not in ['reception', 'super_admin', 'manager', 'lab', 'radiology', 'doctor']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        doctor_id = request.args.get('doctor_id', type=int)
        if current_user.role == 'doctor':
            doctor_id = current_user.id
        status = queue_service.get_queue_status(department_id, doctor_id=doctor_id)
        
        if status:
            return jsonify({'success': True, 'data': status})
        else:
            return jsonify({'success': False, 'message': 'خطأ في جلب حالة الطابور'})
            
    except Exception as e:
        logging.error(f"Error getting queue status: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب حالة الطابور حالياً'})

@reception_bp.route('/api/queue-status-all')
@login_required
def api_queue_status_all():
    if current_user.role not in ['reception', 'super_admin', 'manager', 'lab', 'radiology', 'doctor']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        from services.queue_management_service import QueueManagementService
        from models.department import Department
        queue_service = QueueManagementService()
        all_departments = Department.query.filter_by(is_active=True).all()
        if current_user.role in ['reception', 'super_admin', 'manager']:
            departments = all_departments
        elif current_user.role == 'lab':
            departments = [d for d in all_departments if 'lab' in (d.name or '').lower() or 'مختبر' in (d.name_ar or '')]
        elif current_user.role == 'radiology':
            departments = [d for d in all_departments if 'radiology' in (d.name or '').lower() or 'أشعة' in (d.name_ar or '')]
        elif current_user.role == 'doctor':
            departments = [d for d in all_departments if d.id == current_user.department_id] if current_user.department_id else []
        else:
            departments = []
        dept_ids = [d.id for d in departments]
        doctor_id = request.args.get('doctor_id', type=int)
        if current_user.role == 'doctor':
            doctor_id = current_user.id
        status = request.args.get('status')
        priority = request.args.get('priority')
        search = (request.args.get('search') or '').strip() or None
        is_emergency = request.args.get('is_emergency')
        force_entry = request.args.get('force_entry')
        is_emergency = (is_emergency == '1' or is_emergency == 'true' or is_emergency == 'on') if is_emergency is not None else None
        force_entry = (force_entry == '1' or force_entry == 'true' or force_entry == 'on') if force_entry is not None else None
        # فلترة القسم المحدد ضمن الأقسام المسموح بها
        selected_dep = request.args.get('department_id', type=int)
        if selected_dep and selected_dep in dept_ids:
            dept_ids = [selected_dep]
        data = queue_service.get_queue_status_all(
            dept_ids,
            doctor_id=doctor_id,
            status=status,
            priority=priority,
            search=search,
            is_emergency=is_emergency,
            force_entry=force_entry
        )
        if data:
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'message': 'خطأ في جلب حالة الطابور الموحد'})
    except Exception as e:
        logging.error(f"Error getting all queue status: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب حالة الطابور الموحد حالياً'})


@reception_bp.route('/api/queue-wait-metrics')
@login_required
def api_queue_wait_metrics():
    if current_user.role not in ['reception', 'super_admin', 'manager', 'lab', 'radiology', 'doctor']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        from services.queue_management_service import QueueManagementService
        from models.department import Department

        queue_service = QueueManagementService()
        all_departments = Department.query.filter_by(is_active=True).all()
        if current_user.role in ['reception', 'super_admin', 'manager']:
            departments = all_departments
        elif current_user.role == 'lab':
            departments = [d for d in all_departments if 'lab' in (d.name or '').lower() or 'مختبر' in (d.name_ar or '')]
        elif current_user.role == 'radiology':
            departments = [d for d in all_departments if 'radiology' in (d.name or '').lower() or 'أشعة' in (d.name_ar or '')]
        elif current_user.role == 'doctor':
            departments = [d for d in all_departments if d.id == current_user.department_id] if current_user.department_id else []
        else:
            departments = []

        dept_ids = [d.id for d in departments]
        selected_dep = request.args.get('department_id', type=int)
        if selected_dep and selected_dep in dept_ids:
            dept_ids = [selected_dep]

        data = queue_service.get_wait_metrics_today(dept_ids)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logging.error(f"Error getting queue wait metrics: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب مؤشرات الانتظار حالياً'})

@reception_bp.route('/api/fhir/patient/<int:patient_id>')
@login_required
def api_fhir_patient(patient_id):
    """تصدير بيانات المريض بصيغة FHIR Patient (مبسطة)"""
    try:
        from models.patient import Patient
        from models.visit import Visit
        patient = db.session.get(Patient, patient_id)
        if not patient:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على المريض المطلوب'}]}), 404
        gender_map = {'M': 'male', 'F': 'female'}
        resource = {
            'resourceType': 'Patient',
            'id': str(patient.id),
            'identifier': [{'system': 'urn:medical-system:national_id', 'value': patient.national_id}] if patient.national_id else [],
            'name': [{
                'text': patient.full_name,
                'given': [patient.first_name],
                'family': patient.last_name
            }],
            'telecom': ([{'system': 'phone', 'value': patient.phone}] if patient.phone else []),
            'gender': gender_map.get((patient.gender or '').upper(), 'unknown'),
            'birthDate': patient.birth_date.isoformat() if patient.birth_date else None,
            'address': ([{'text': patient.address}] if patient.address else []),
            'extension': [
                {'url': 'urn:medical-system:is_pregnant', 'valueBoolean': bool(patient.is_pregnant)}
            ],
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Patient']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Patient: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات المريض حالياً'}]}), 500

@reception_bp.route('/api/fhir/encounter/<int:visit_id>')
@login_required
def api_fhir_encounter(visit_id):
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.user import User
        from models.department import Department
        visit = db.session.get(Visit, visit_id)
        if not visit:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على الزيارة المطلوبة'}]}), 404
        patient = db.session.get(Patient, visit.patient_id) if visit.patient_id else None
        doctor = db.session.get(User, visit.doctor_id) if visit.doctor_id else None
        dept = db.session.get(Department, visit.department_id) if visit.department_id else None
        status_map = {
            'OPEN': 'in-progress',
            'IN_PROGRESS': 'in-progress',
            'COMPLETED': 'finished',
            'ARCHIVED': 'cancelled'
        }
        start_dt = visit.visit_time or visit.created_at
        resource = {
            'resourceType': 'Encounter',
            'id': str(visit.id),
            'status': status_map.get(visit.status or '', 'unknown'),
            'class': {'system': 'http://terminology.hl7.org/CodeSystem/v3-ActCode', 'code': 'AMB'},
            'type': [{'text': visit.visit_type}] if visit.visit_type else [],
            'subject': {'reference': f'Patient/{visit.patient_id}', 'display': (patient.full_name if patient else None)},
            'participant': ([{'individual': {'reference': f'Practitioner/{doctor.id}', 'display': doctor.full_name}}] if doctor else []),
            'serviceType': ([{'text': (dept.name_ar or dept.name)}] if dept else []),
            'period': {
                'start': (start_dt.isoformat() if start_dt else None),
                'end': (visit.completed_at.isoformat() if visit.completed_at else None)
            },
            'reasonCode': ([{'text': visit.symptoms}] if getattr(visit, 'symptoms', None) else []),
            'note': ([{'text': visit.notes}] if getattr(visit, 'notes', None) else []),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Encounter']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Encounter: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الزيارة حالياً'}]}), 500

@reception_bp.route('/api/fhir/appointment/<int:appointment_id>')
@login_required
def api_fhir_appointment(appointment_id):
    try:
        from models.appointment import Appointment
        from models.patient import Patient
        from models.user import User
        from models.department import Department
        appt = db.session.get(Appointment, appointment_id)
        if not appt:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على الموعد المطلوب'}]}), 404
        patient = db.session.get(Patient, appt.patient_id) if appt.patient_id else None
        doctor = db.session.get(User, appt.doctor_id) if appt.doctor_id else None
        dept = db.session.get(Department, appt.department_id) if appt.department_id else None
        status_map = {
            'SCHEDULED': 'booked',
            'CONFIRMED': 'booked',
            'CANCELLED': 'cancelled',
            'NO_SHOW': 'noshow',
            'DONE': 'fulfilled'
        }
        participants = [
            {'actor': {'reference': f'Patient/{appt.patient_id}', 'display': (patient.full_name if patient else None)}, 'status': 'accepted'}
        ]
        if doctor:
            participants.append({'actor': {'reference': f'Practitioner/{doctor.id}', 'display': doctor.full_name}, 'status': 'accepted'})
        resource = {
            'resourceType': 'Appointment',
            'id': str(appt.id),
            'status': status_map.get(appt.status or '', 'booked'),
            'start': (appt.starts_at.isoformat() if appt.starts_at else None),
            'end': (appt.ends_at.isoformat() if appt.ends_at else None),
            'description': (appt.notes or None),
            'serviceType': ([{'text': (dept.name_ar or dept.name)}] if dept else []),
            'participant': participants,
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Appointment']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Appointment: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الموعد حالياً'}]}), 500

@reception_bp.route('/api/fhir/practitioner/<int:user_id>')
@login_required
def api_fhir_practitioner(user_id):
    try:
        from models.user import User
        from models.department import Department
        user = db.session.get(User, user_id)
        if not user or user.role != 'doctor':
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على الطبيب المطلوب'}]}), 404
        dept = db.session.get(Department, user.department_id) if user.department_id else None
        resource = {
            'resourceType': 'Practitioner',
            'id': str(user.id),
            'name': [{'text': user.full_name}],
            'telecom': ([{'system': 'phone', 'value': user.phone}] if user.phone else []) +
                       ([{'system': 'email', 'value': user.email}] if user.email else []),
            'qualification': [{'code': {'text': 'Doctor'}}],
            'extension': ([{'url': 'urn:medical-system:department', 'valueString': (dept.name_ar or dept.name)}] if dept else []),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Practitioner']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Practitioner: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الطبيب حالياً'}]}), 500

@reception_bp.route('/api/fhir/organization/<int:department_id>')
@login_required
def api_fhir_organization(department_id):
    try:
        from models.department import Department
        dept = db.session.get(Department, department_id)
        if not dept:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على القسم المطلوب'}]}), 404
        resource = {
            'resourceType': 'Organization',
            'id': str(dept.id),
            'name': (dept.name_ar or dept.name),
            'telecom': ([{'system': 'phone', 'value': dept.phone}] if getattr(dept, 'phone', None) else []) +
                       ([{'system': 'email', 'value': dept.email}] if getattr(dept, 'email', None) else []),
            'address': ([{'text': getattr(dept, 'location', None)}] if getattr(dept, 'location', None) else []),
            'active': bool(dept.is_active),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Organization']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Organization: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات القسم حالياً'}]}), 500

@reception_bp.route('/api/patient-queue-position/<int:patient_id>/<int:department_id>')
@login_required
def api_patient_queue_position(patient_id, department_id):
    """API لموقع المريض في الطابور"""
    if current_user.role != 'reception':
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        position, message = queue_service.get_patient_queue_position(patient_id, department_id)
        
        if position:
            return jsonify({'success': True, 'position': position, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        logging.error(f"Error getting queue position: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب موقع المريض في الطابور حالياً'})

@reception_bp.route('/api/queue-snapshot')
@login_required
def api_queue_snapshot():
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        active_queue_items = QueueManagement.query.filter(
            QueueManagement.status.in_(['waiting', 'called', 'in_progress'])
        ).order_by(QueueManagement.queued_at.asc()).limit(50).all()
        items = []
        for item in active_queue_items:
            items.append({
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'status': item.get_status_display(),
                'priority': item.get_priority_display(),
                'payment': item.get_payment_status_display()
            })
        stats = get_smart_queue_management()
        satisfaction = get_patient_satisfaction_ai()
        forecast = get_patient_demand_forecast()
        return jsonify({
            'success': True,
            'items': items,
            'stats': stats,
            'satisfaction': satisfaction,
            'forecast': forecast
        })
    except Exception as e:
        logging.error(f"Error getting queue snapshot: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب بيانات الطابور حالياً'}), 500

@reception_bp.route('/api/display/waiting')
@login_required
def api_display_waiting():
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        waiting = QueueManagement.query.filter(
            QueueManagement.status == 'waiting'
        ).order_by(QueueManagement.queued_at.asc()).limit(60).all()
        called = QueueManagement.query.filter(
            QueueManagement.status == 'called'
        ).order_by(QueueManagement.called_at.desc()).limit(12).all()
        current = QueueManagement.query.filter(
            QueueManagement.status == 'in_progress'
        ).order_by(QueueManagement.started_at.desc()).limit(6).all()

        def _pack(item):
            room_value = ''
            if item.visit and item.visit.doctor and item.visit.doctor.doctor_room:
                room_value = item.visit.doctor.doctor_room
            elif item.department and item.department.location:
                room_value = item.department.location
            return {
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'doctor_name': item.visit.doctor.full_name if item.visit and item.visit.doctor else '',
                'room_name': room_value,
                'status': item.get_status_display()
            }

        return jsonify({
            'success': True,
            'waiting': [_pack(i) for i in waiting],
            'called': [_pack(i) for i in called],
            'current': [_pack(i) for i in current]
        })
    except Exception as e:
        logging.error(f"Error getting waiting display: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب شاشة الانتظار حالياً'}), 500

@reception_bp.route('/api/display/calls')
@login_required
def api_display_calls():
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        called = QueueManagement.query.filter(
            QueueManagement.status.in_(['called', 'in_progress'])
        ).order_by(QueueManagement.called_at.desc()).limit(24).all()
        items = []
        for item in called:
            room_value = ''
            if item.visit and item.visit.doctor and item.visit.doctor.doctor_room:
                room_value = item.visit.doctor.doctor_room
            elif item.department and item.department.location:
                room_value = item.department.location
            items.append({
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'doctor_name': item.visit.doctor.full_name if item.visit and item.visit.doctor else '',
                'room_name': room_value,
                'status': item.get_status_display()
            })
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        logging.error(f"Error getting calls display: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب شاشة النداء حالياً'}), 500

# ==================== الميزات الذكية للاستقبال ====================


def can_search_all_patients(user_role):
    """التحقق من صلاحية البحث في كل المرضى"""
    # الأدوار التي يمكنها البحث في كل المرضى
    return user_role in ['reception', 'doctor', 'emergency', 'super_admin', 'manager', 'accountant']


def get_accessible_departments_for_user(user_role, user_id=None, user_department_id=None):
    """الحصول على الأقسام المتاحة للمستخدم"""
    all_departments = Department.query.filter_by(is_active=True).all()
    try:
        from services.access_control_service import AccessControlService
        if user_id:
            from models.user import User
            user = db.session.get(User, user_id)
        else:
            user = None
        if user:
            dept_ids = AccessControlService.get_accessible_department_ids(user)
            if dept_ids is None:
                return all_departments
            if dept_ids:
                return [d for d in all_departments if d.id in set(dept_ids)]
            return []
    except Exception:
        pass

    if user_role in ['reception', 'super_admin', 'manager', 'doctor', 'emergency', 'accountant']:
        return all_departments
    if user_role in ['lab', 'radiology', 'nurse'] and user_department_id:
        return [d for d in all_departments if d.id == user_department_id]
    return []

# ===== وظائف مساعدة لسيناريو الزيارة =====

