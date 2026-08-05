"""api routes - extracted from monolithic reception.py"""

import logging

# Imports
from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.shared.enums import QueueState
from models.department import Department
from models.queue_management import QueueManagement
from models.user import User
from routes.reception import reception_bp
from routes.reception.queue import (
    get_patient_demand_forecast,
    get_patient_satisfaction_ai,
    get_smart_queue_management,
)
from utils.decorators import (
    role_required_json,
)
from utils.tenant_query import TenantContextError, get_tenant_record

# ═══════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════


@reception_bp.route('/api/doctors')
@login_required
@role_required_json('reception', 'manager')
def api_doctors():
    """API لجلب الأطباء"""

    department_id = request.args.get('department_id')
    request.args.get('appointment_type')

    query = select(User)

    if department_id:
        query = query.filter_by(department_id=department_id)

    doctors = db.session.execute(query).scalars().all()

    return jsonify(
        {
            'success': True,
            'doctors': [{'id': doctor.id, 'full_name': doctor.full_name} for doctor in doctors],
        }
    )


@reception_bp.route('/api/department-staff')
@login_required
@role_required_json('reception', 'manager')
def api_department_staff():
    """API لجلب موظفي القسم المناسبين"""

    department_id = request.args.get('department_id', type=int)
    if not department_id:
        return jsonify({'error': 'معرف القسم مطلوب'}), 400

    try:
        # جلب موظفي القسم حسب نوع القسم
        try:
            department = get_tenant_record(Department, department_id)
        except TenantContextError:
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
        direct_staff = (
            db.session.execute(
                select(User).filter(User.department_id == department_id, User.is_active)
            )
            .scalars()
            .all()
        )

        # 2. موظفون بدون قسم ودورهم يناسب نوع القسم
        unassigned = (
            db.session.execute(
                select(User).filter(
                    User.role.in_(roles), User.is_active, User.department_id.is_(None)
                )
            )
            .scalars()
            .all()
        )

        # دمج بدون تكرار
        seen_ids = set()
        staff = []
        for p in direct_staff + unassigned:
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                staff.append(p)

        results = []
        for person in staff:
            results.append(
                {
                    'id': person.id,
                    'full_name': person.full_name,
                    'role': person.role,
                    'specialization': getattr(person, 'specialization', ''),
                    'phone': getattr(person, 'phone', ''),
                }
            )

        return jsonify({'staff': results})
    except Exception as e:
        logging.exception(f'Error getting department staff: {e!s}')
        return jsonify({'error': 'حدث خطأ في جلب الموظفين'}), 500


@reception_bp.route('/api/department-services')
@login_required
@role_required_json('reception', 'manager')
def api_department_services():
    department_id = request.args.get('department_id', type=int)
    if not department_id:
        return jsonify({'error': 'القسم مطلوب'}), 400
    try:
        dept = get_tenant_record(Department, department_id)
    except TenantContextError:
        return jsonify({'error': 'القسم غير موجود'}), 404

    from models.service import ServiceMaster

    dt = dept.get_type()
    category = 'doctor' if dt == 'general' else dt
    # أولاً: خدمات هذا القسم تحديداً
    services = (
        db.session.execute(
            select(ServiceMaster)
            .filter(
                ServiceMaster.category == category,
                ServiceMaster.is_active,
                ServiceMaster.department_id == department_id,
            )
            .order_by(ServiceMaster.name_ar)
        )
        .scalars()
        .all()
    )
    # إذا لم توجد خدمات مرتبطة بالقسم، أرجع كل خدمات الفئة
    if not services:
        services = (
            db.session.execute(
                select(ServiceMaster)
                .filter(ServiceMaster.category == category, ServiceMaster.is_active)
                .order_by(ServiceMaster.name_ar)
            )
            .scalars()
            .all()
        )
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
                'price': float(s.base_price or 0),
            }
            for s in services
        ],
    }
    return jsonify(resp)


@reception_bp.route('/api/queue-department-status/<int:department_id>')
@login_required
@role_required_json('reception', 'manager', 'lab', 'radiology', 'doctor')
def api_queue_status(department_id):
    """API لحالة الطابور"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        doctor_id = request.args.get('doctor_id', type=int)
        if current_user.role == 'doctor':
            doctor_id = current_user.id
        status = queue_service.get_queue_status(department_id, doctor_id=doctor_id)

        if status:
            return jsonify({'success': True, 'data': status})
        return jsonify({'success': False, 'message': 'خطأ في جلب حالة الطابور'})

    except Exception as e:
        logging.exception(f'Error getting queue status: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر جلب حالة الطابور حالياً'})


@reception_bp.route('/api/queue-status-all')
@login_required
@role_required_json('reception', 'manager', 'lab', 'radiology', 'doctor')
def api_queue_status_all():
    try:
        from models.department import Department
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        all_departments = (
            db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
        )
        if current_user.role in ['reception', 'super_admin', 'manager']:
            departments = all_departments
        elif current_user.role == 'lab':
            departments = [
                d
                for d in all_departments
                if 'lab' in (d.name or '').lower() or 'مختبر' in (d.name_ar or '')
            ]
        elif current_user.role == 'radiology':
            departments = [
                d
                for d in all_departments
                if 'radiology' in (d.name or '').lower() or 'أشعة' in (d.name_ar or '')
            ]
        elif current_user.role == 'doctor':
            departments = (
                [d for d in all_departments if d.id == current_user.department_id]
                if current_user.department_id
                else []
            )
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
        is_emergency = (
            (is_emergency in {'1', 'true', 'on'})
            if is_emergency is not None
            else None
        )
        force_entry = (
            (force_entry in {'1', 'true', 'on'})
            if force_entry is not None
            else None
        )
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
            force_entry=force_entry,
        )
        if data:
            return jsonify({'success': True, 'data': data})
        return jsonify({'success': False, 'message': 'خطأ في جلب حالة الطابور الموحد'})
    except Exception as e:
        logging.exception(f'Error getting all queue status: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر جلب حالة الطابور الموحد حالياً'})


@reception_bp.route('/api/queue-wait-metrics')
@login_required
@role_required_json('reception', 'manager', 'lab', 'radiology', 'doctor')
def api_queue_wait_metrics():
    try:
        from models.department import Department
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        all_departments = (
            db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
        )
        if current_user.role in ['reception', 'super_admin', 'manager']:
            departments = all_departments
        elif current_user.role == 'lab':
            departments = [
                d
                for d in all_departments
                if 'lab' in (d.name or '').lower() or 'مختبر' in (d.name_ar or '')
            ]
        elif current_user.role == 'radiology':
            departments = [
                d
                for d in all_departments
                if 'radiology' in (d.name or '').lower() or 'أشعة' in (d.name_ar or '')
            ]
        elif current_user.role == 'doctor':
            departments = (
                [d for d in all_departments if d.id == current_user.department_id]
                if current_user.department_id
                else []
            )
        else:
            departments = []

        dept_ids = [d.id for d in departments]
        selected_dep = request.args.get('department_id', type=int)
        if selected_dep and selected_dep in dept_ids:
            dept_ids = [selected_dep]

        data = queue_service.get_wait_metrics_today(dept_ids)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logging.exception(f'Error getting queue wait metrics: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر جلب مؤشرات الانتظار حالياً'})


@reception_bp.route('/api/fhir/patient/<int:patient_id>')
@login_required
def api_fhir_patient(patient_id):
    """تصدير بيانات المريض بصيغة FHIR Patient (مبسطة)"""
    try:
        from models.patient import Patient

        try:
            patient = get_tenant_record(Patient, patient_id)
        except TenantContextError:
            return jsonify(
                {
                    'resourceType': 'OperationOutcome',
                    'issue': [
                        {'severity': 'error', 'diagnostics': 'تعذر العثور على المريض المطلوب'}
                    ],
                }
            ), 404
        gender_map = {'M': 'male', 'F': 'female'}
        resource = {
            'resourceType': 'Patient',
            'id': str(patient.id),
            'identifier': [
                {'system': 'urn:medical-system:national_id', 'value': patient.national_id}
            ]
            if patient.national_id
            else [],
            'name': [
                {
                    'text': patient.full_name,
                    'given': [patient.first_name],
                    'family': patient.last_name,
                }
            ],
            'telecom': ([{'system': 'phone', 'value': patient.phone}] if patient.phone else []),
            'gender': gender_map.get((patient.gender or '').upper(), 'unknown'),
            'birthDate': patient.birth_date.isoformat() if patient.birth_date else None,
            'address': ([{'text': patient.address}] if patient.address else []),
            'extension': [
                {'url': 'urn:medical-system:is_pregnant', 'valueBoolean': bool(patient.is_pregnant)}
            ],
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Patient']},
        }
        return jsonify(resource)
    except Exception as e:
        logging.exception(f'Error exporting FHIR Patient: {e!s}')
        return jsonify(
            {
                'resourceType': 'OperationOutcome',
                'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات المريض حالياً'}],
            }
        ), 500


@reception_bp.route('/api/fhir/encounter/<int:visit_id>')
@login_required
def api_fhir_encounter(visit_id):
    try:
        from models.department import Department
        from models.patient import Patient
        from models.user import User
        from models.visit import Visit

        try:
            visit = get_tenant_record(Visit, visit_id)
        except TenantContextError:
            return jsonify(
                {
                    'resourceType': 'OperationOutcome',
                    'issue': [
                        {'severity': 'error', 'diagnostics': 'تعذر العثور على الزيارة المطلوبة'}
                    ],
                }
            ), 404
        patient = db.session.get(Patient, visit.patient_id) if visit.patient_id else None
        doctor = db.session.get(User, visit.doctor_id) if visit.doctor_id else None
        dept = db.session.get(Department, visit.department_id) if visit.department_id else None
        status_map = {
            'OPEN': 'in-progress',
            'IN_PROGRESS': 'in-progress',
            'COMPLETED': 'finished',
            'ARCHIVED': 'cancelled',
        }
        start_dt = visit.visit_time or visit.created_at
        resource = {
            'resourceType': 'Encounter',
            'id': str(visit.id),
            'status': status_map.get(visit.status or '', 'unknown'),
            'class': {'system': 'http://terminology.hl7.org/CodeSystem/v3-ActCode', 'code': 'AMB'},
            'type': [{'text': visit.visit_type}] if visit.visit_type else [],
            'subject': {
                'reference': f'Patient/{visit.patient_id}',
                'display': (patient.full_name if patient else None),
            },
            'participant': (
                [
                    {
                        'individual': {
                            'reference': f'Practitioner/{doctor.id}',
                            'display': doctor.full_name,
                        }
                    }
                ]
                if doctor
                else []
            ),
            'serviceType': ([{'text': (dept.name_ar or dept.name)}] if dept else []),
            'period': {
                'start': (start_dt.isoformat() if start_dt else None),
                'end': (visit.completed_at.isoformat() if visit.completed_at else None),
            },
            'reasonCode': ([{'text': visit.symptoms}] if getattr(visit, 'symptoms', None) else []),
            'note': ([{'text': visit.notes}] if getattr(visit, 'notes', None) else []),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Encounter']},
        }
        return jsonify(resource)
    except Exception as e:
        logging.exception(f'Error exporting FHIR Encounter: {e!s}')
        return jsonify(
            {
                'resourceType': 'OperationOutcome',
                'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الزيارة حالياً'}],
            }
        ), 500


@reception_bp.route('/api/fhir/appointment/<int:appointment_id>')
@login_required
def api_fhir_appointment(appointment_id):
    try:
        from models.appointment import Appointment
        from models.department import Department
        from models.patient import Patient
        from models.user import User

        try:
            appt = get_tenant_record(Appointment, appointment_id)
        except TenantContextError:
            return jsonify(
                {
                    'resourceType': 'OperationOutcome',
                    'issue': [
                        {'severity': 'error', 'diagnostics': 'تعذر العثور على الموعد المطلوب'}
                    ],
                }
            ), 404
        patient = db.session.get(Patient, appt.patient_id) if appt.patient_id else None
        doctor = db.session.get(User, appt.doctor_id) if appt.doctor_id else None
        dept = db.session.get(Department, appt.department_id) if appt.department_id else None
        status_map = {
            'SCHEDULED': 'booked',
            'CONFIRMED': 'booked',
            'CANCELLED': 'cancelled',
            'NO_SHOW': 'noshow',
            'DONE': 'fulfilled',
        }
        participants = [
            {
                'actor': {
                    'reference': f'Patient/{appt.patient_id}',
                    'display': (patient.full_name if patient else None),
                },
                'status': 'accepted',
            }
        ]
        if doctor:
            participants.append(
                {
                    'actor': {
                        'reference': f'Practitioner/{doctor.id}',
                        'display': doctor.full_name,
                    },
                    'status': 'accepted',
                }
            )
        resource = {
            'resourceType': 'Appointment',
            'id': str(appt.id),
            'status': status_map.get(appt.status or '', 'booked'),
            'start': (appt.starts_at.isoformat() if appt.starts_at else None),
            'end': (appt.ends_at.isoformat() if appt.ends_at else None),
            'description': (appt.notes or None),
            'serviceType': ([{'text': (dept.name_ar or dept.name)}] if dept else []),
            'participant': participants,
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Appointment']},
        }
        return jsonify(resource)
    except Exception as e:
        logging.exception(f'Error exporting FHIR Appointment: {e!s}')
        return jsonify(
            {
                'resourceType': 'OperationOutcome',
                'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الموعد حالياً'}],
            }
        ), 500


@reception_bp.route('/api/fhir/practitioner/<int:user_id>')
@login_required
def api_fhir_practitioner(user_id):
    try:
        from models.department import Department
        from models.user import User

        try:
            user = get_tenant_record(User, user_id)
        except TenantContextError:
            return jsonify(
                {
                    'resourceType': 'OperationOutcome',
                    'issue': [
                        {'severity': 'error', 'diagnostics': 'تعذر العثور على الطبيب المطلوب'}
                    ],
                }
            ), 404
        if user.role != 'doctor':
            return jsonify(
                {
                    'resourceType': 'OperationOutcome',
                    'issue': [
                        {'severity': 'error', 'diagnostics': 'تعذر العثور على الطبيب المطلوب'}
                    ],
                }
            ), 404
        dept = db.session.get(Department, user.department_id) if user.department_id else None
        resource = {
            'resourceType': 'Practitioner',
            'id': str(user.id),
            'name': [{'text': user.full_name}],
            'telecom': ([{'system': 'phone', 'value': user.phone}] if user.phone else [])
            + ([{'system': 'email', 'value': user.email}] if user.email else []),
            'qualification': [{'code': {'text': 'Doctor'}}],
            'extension': (
                [
                    {
                        'url': 'urn:medical-system:department',
                        'valueString': (dept.name_ar or dept.name),
                    }
                ]
                if dept
                else []
            ),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Practitioner']},
        }
        return jsonify(resource)
    except Exception as e:
        logging.exception(f'Error exporting FHIR Practitioner: {e!s}')
        return jsonify(
            {
                'resourceType': 'OperationOutcome',
                'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الطبيب حالياً'}],
            }
        ), 500


@reception_bp.route('/api/fhir/organization/<int:department_id>')
@login_required
def api_fhir_organization(department_id):
    try:
        from models.department import Department

        try:
            dept = get_tenant_record(Department, department_id)
        except TenantContextError:
            return jsonify(
                {
                    'resourceType': 'OperationOutcome',
                    'issue': [
                        {'severity': 'error', 'diagnostics': 'تعذر العثور على القسم المطلوب'}
                    ],
                }
            ), 404
        resource = {
            'resourceType': 'Organization',
            'id': str(dept.id),
            'name': (dept.name_ar or dept.name),
            'telecom': (
                [{'system': 'phone', 'value': dept.phone}] if getattr(dept, 'phone', None) else []
            )
            + ([{'system': 'email', 'value': dept.email}] if getattr(dept, 'email', None) else []),
            'address': (
                [{'text': getattr(dept, 'location', None)}]
                if getattr(dept, 'location', None)
                else []
            ),
            'active': bool(dept.is_active),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Organization']},
        }
        return jsonify(resource)
    except Exception as e:
        logging.exception(f'Error exporting FHIR Organization: {e!s}')
        return jsonify(
            {
                'resourceType': 'OperationOutcome',
                'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات القسم حالياً'}],
            }
        ), 500


@reception_bp.route('/api/patient-queue-position/<int:patient_id>/<int:department_id>')
@login_required
@role_required_json('reception')
def api_patient_queue_position(patient_id, department_id):
    """API لموقع المريض في الطابور"""

    try:
        from services.queue_management_service import QueueManagementService

        queue_service = QueueManagementService()
        position, message = queue_service.get_patient_queue_position(patient_id, department_id)

        if position:
            return jsonify({'success': True, 'position': position, 'message': message})
        return jsonify({'success': False, 'message': message})

    except Exception as e:
        logging.exception(f'Error getting queue position: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر جلب موقع المريض في الطابور حالياً'})


@reception_bp.route('/api/queue-snapshot')
@login_required
@role_required_json('reception', 'manager')
def api_queue_snapshot():
    try:
        active_queue_items = (
            db.session.execute(
                select(QueueManagement)
                .filter(
                    QueueManagement.status.in_(
                        [QueueState.WAITING, QueueState.CALLED, QueueState.IN_PROGRESS]
                    )
                )
                .order_by(QueueManagement.queued_at.asc())
                .limit(50)
            )
            .scalars()
            .all()
        )
        items = []
        for item in active_queue_items:
            items.append(
                {
                    'queue_number': item.queue_number,
                    'patient_name': item.patient.full_name if item.patient else '',
                    'department_name': item.department.name_ar if item.department else '',
                    'status': item.get_status_display(),
                    'priority': item.get_priority_display(),
                    'payment': item.get_payment_status_display(),
                }
            )
        stats = get_smart_queue_management()
        satisfaction = get_patient_satisfaction_ai()
        forecast = get_patient_demand_forecast()
        return jsonify(
            {
                'success': True,
                'items': items,
                'stats': stats,
                'satisfaction': satisfaction,
                'forecast': forecast,
            }
        )
    except Exception as e:
        logging.exception(f'Error getting queue snapshot: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر جلب بيانات الطابور حالياً'}), 500


@reception_bp.route('/api/display/waiting')
@login_required
@role_required_json('reception', 'manager')
def api_display_waiting():
    try:
        waiting = (
            db.session.execute(
                select(QueueManagement)
                .filter(QueueManagement.status == QueueState.WAITING)
                .order_by(QueueManagement.queued_at.asc())
                .limit(60)
            )
            .scalars()
            .all()
        )
        called = (
            db.session.execute(
                select(QueueManagement)
                .filter(QueueManagement.status == QueueState.CALLED)
                .order_by(QueueManagement.called_at.desc())
                .limit(12)
            )
            .scalars()
            .all()
        )
        current = (
            db.session.execute(
                select(QueueManagement)
                .filter(QueueManagement.status == QueueState.IN_PROGRESS)
                .order_by(QueueManagement.started_at.desc())
                .limit(6)
            )
            .scalars()
            .all()
        )

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
                'doctor_name': item.visit.doctor.full_name
                if item.visit and item.visit.doctor
                else '',
                'room_name': room_value,
                'status': item.get_status_display(),
            }

        return jsonify(
            {
                'success': True,
                'waiting': [_pack(i) for i in waiting],
                'called': [_pack(i) for i in called],
                'current': [_pack(i) for i in current],
            }
        )
    except Exception as e:
        logging.exception(f'Error getting waiting display: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر جلب شاشة الانتظار حالياً'}), 500


@reception_bp.route('/api/display/calls')
@login_required
@role_required_json('reception', 'manager')
def api_display_calls():
    try:
        called = (
            db.session.execute(
                select(QueueManagement)
                .filter(QueueManagement.status.in_([QueueState.CALLED, QueueState.IN_PROGRESS]))
                .order_by(QueueManagement.called_at.desc())
                .limit(24)
            )
            .scalars()
            .all()
        )
        items = []
        for item in called:
            room_value = ''
            if item.visit and item.visit.doctor and item.visit.doctor.doctor_room:
                room_value = item.visit.doctor.doctor_room
            elif item.department and item.department.location:
                room_value = item.department.location
            items.append(
                {
                    'queue_number': item.queue_number,
                    'patient_name': item.patient.full_name if item.patient else '',
                    'department_name': item.department.name_ar if item.department else '',
                    'doctor_name': item.visit.doctor.full_name
                    if item.visit and item.visit.doctor
                    else '',
                    'room_name': room_value,
                    'status': item.get_status_display(),
                }
            )
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        logging.exception(f'Error getting calls display: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر جلب شاشة النداء حالياً'}), 500


# ==================== الميزات الذكية للاستقبال ====================


def can_search_all_patients(user_role):
    """التحقق من صلاحية البحث في كل المرضى"""
    # الأدوار التي يمكنها البحث في كل المرضى
    return user_role in ['reception', 'doctor', 'emergency', 'super_admin', 'manager', 'accountant']


def get_accessible_departments_for_user(user_role, user_id=None, user_department_id=None):
    """الحصول على الأقسام المتاحة للمستخدم"""
    all_departments = (
        db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
    )
    try:
        from services.access_control_service import AccessControlService

        if user_id:
            from models.user import User

            try:
                user = get_tenant_record(User, user_id)
            except TenantContextError:
                user = None
        else:
            user = None
        if user:
            dept_ids = AccessControlService.get_accessible_department_ids(user)
            if dept_ids is None:
                return all_departments
            if dept_ids:
                return [d for d in all_departments if d.id in set(dept_ids)]
            return []
    except Exception as e:
        logging.warning(f'Error in {__name__}: {e}')
    if user_role in ['reception', 'super_admin', 'manager', 'doctor', 'emergency', 'accountant']:
        return all_departments
    if user_role in ['lab', 'radiology', 'nurse'] and user_department_id:
        return [d for d in all_departments if d.id == user_department_id]
    return []


# ===== وظائف مساعدة لسيناريو الزيارة =====
