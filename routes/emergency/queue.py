"""queue routes - extracted from monolithic emergency.py"""

from routes.emergency import emergency_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.emergency import EmergencyCase
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from services.emergency_service import emergency_service
from app_factory import db
from sqlalchemy import and_, or_, desc, case
import logging, json
from datetime import datetime, date, timedelta, timezone


# =============================================
# QUEUE ROUTES
# =============================================

@emergency_bp.route('/patient-queue')
@login_required
def patient_queue():
    """طابور المرضى في الطوارئ - إدارة متقدمة"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    try:
        # جلب الحالات الطارئة مع تفاصيل إضافية
        severity_order = case(
            (EmergencyCase.severity == 'CRITICAL', 4),
            (EmergencyCase.severity == 'HIGH', 3),
            (EmergencyCase.severity == 'MODERATE', 2),
            (EmergencyCase.severity == 'LOW', 1),
            else_=0
        )
        query = EmergencyCase.query.filter(
            EmergencyCase.status.in_([EmergencyStatus.WAITING, EmergencyStatus.TRIAGE, EmergencyStatus.RESUSCITATION, EmergencyStatus.TREATMENT, EmergencyStatus.OBSERVATION])
        ).order_by(severity_order.desc(), EmergencyCase.created_at)
        
        total = query.count()
        pages = (total + per_page - 1) // per_page
        
        emergencies = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # إحصائيات الطابور
        queue_stats = {
            'total_cases': total,
            'triage_cases': len([e for e in emergencies if e.status in ['WAITING', 'TRIAGE', 'RESUSCITATION']]),
            'treatment_cases': len([e for e in emergencies if e.status == EmergencyStatus.TREATMENT]),
            'observation_cases': len([e for e in emergencies if e.status == EmergencyStatus.OBSERVATION]),
            'urgent_cases': len([e for e in emergencies if e.severity == 'HIGH']),
            'critical_cases': len([e for e in emergencies if e.severity == 'CRITICAL'])
        }
        
        return render_template('emergency/patient_queue.html', 
                             emergencies=emergencies, 
                             queue_stats=queue_stats,
                             page=page, pages=pages, total=total)
    except Exception as e:
        logging.error(f"Error loading emergency queue: {str(e)}")
        flash('حدث خطأ في تحميل طابور الطوارئ', 'error')
        return redirect(url_for('emergency.dashboard'))

# تم نقل مسار عرض المريض إلى routes/reception.py لتجنب التكرار
# يمكن الوصول إليه عبر /reception/view_patient/<patient_id> مع فلترة تلقائية للطوارئ

@emergency_bp.route('/triage')
@login_required
def triage_list():
    """قائمة الفرز"""
    if current_user.role not in ['emergency', 'doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        return redirect(url_for('emergency.patient_queue'))
    except Exception as e:
        logging.error(f"Error loading triage list: {str(e)}")
        flash('حدث خطأ في تحميل قائمة الفرز', 'error')
        return redirect(url_for('emergency.dashboard'))

@emergency_bp.route('/triage/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def triage(emergency_id):
    """تقييم حالة المريض (Triage)"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        visit = emergency.visit or (db.session.get(Visit, emergency.visit_id) if emergency.visit_id else None)

        if request.method == 'POST':
            triage_level = (request.form.get('triage_level') or '').upper().strip()
            priority = (request.form.get('priority') or '').upper().strip()

            severity_map = {
                'RED': 'CRITICAL',
                'YELLOW': 'HIGH',
                'GREEN': 'MODERATE',
                'CRITICAL': 'CRITICAL',
                'URGENT': 'HIGH',
                'HIGH': 'HIGH',
                'NORMAL': 'MODERATE',
                'MODERATE': 'MODERATE',
                'LOW': 'LOW'
            }
            severity = severity_map.get(triage_level) or severity_map.get(priority) or emergency.severity or 'MODERATE'

            vital_signs = None
            vital_signs_raw = request.form.get('vital_signs')
            if vital_signs_raw:
                try:
                    vital_signs = json.loads(vital_signs_raw)
                except Exception:
                    vital_signs = None
            if vital_signs is None:
                vital_signs = {
                    'blood_pressure': request.form.get('blood_pressure'),
                    'heart_rate': request.form.get('heart_rate'),
                    'temperature': request.form.get('temperature'),
                    'oxygen_saturation': request.form.get('oxygen_saturation'),
                    'respiratory_rate': request.form.get('respiratory_rate'),
                    'pain_level': request.form.get('pain_level')
                }

            emergency.severity = severity
            emergency.triage_notes = request.form.get('triage_notes')
            emergency.chief_complaint = request.form.get('chief_complaint') or emergency.chief_complaint
            try:
                emergency.vital_signs = json.dumps(vital_signs, ensure_ascii=False)
            except Exception as e:

                logging.warning(f"Error in {__name__}: {e}")
            if triage_level in ['RED', 'YELLOW', 'GREEN'] and visit is not None:
                visit.triage_level = triage_level
            elif visit is not None and visit.triage_level is None:
                reverse_map = {'CRITICAL': 'RED', 'HIGH': 'YELLOW', 'MODERATE': 'GREEN', 'LOW': 'GREEN'}
                visit.triage_level = reverse_map.get(severity, 'GREEN')

            if emergency.status in ['IN_PROGRESS', 'TRIAGE']:
                _set_emergency_status(emergency, 'TREATMENT')

            db.session.commit()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True})

            flash('تم تقييم حالة المريض بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/triage.html', emergency=emergency, visit=visit)
    except Exception as e:
        logging.error(f"Error in triage: {str(e)}")
        flash('حدث خطأ في تقييم حالة المريض', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/patients')
@login_required
def patients():
    """مرضى الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('emergency/patient_queue.html')

@emergency_bp.route('/queue')
@login_required
def queue():
    """طابور الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('emergency/patient_queue.html')