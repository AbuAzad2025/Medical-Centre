"""vitals routes - extracted from monolithic nurse_routes.py"""

from routes.nurse_routes import nurse_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from services.nursing_service import nursing_service
from app_factory import db
import logging, json
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import func, and_, or_, desc


# =============================================
# VITALS ROUTES
# =============================================

@nurse_bp.route('/vital-signs')
@login_required
def vital_signs():
    """العلامات الحيوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        from models.nurse import VitalSigns

        visit_id = request.args.get('visit_id', type=int)
        patient_id = request.args.get('patient_id', type=int)
        if not patient_id and visit_id:
            visit = db.session.get(Visit, visit_id)
            if visit:
                patient_id = visit.patient_id
        vq = Visit.query.filter(Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]))
        dept_ids = _accessible_department_ids()
        if dept_ids is not None and dept_ids:
            vq = vq.filter(Visit.department_id.in_(dept_ids))
            vq = vq.filter(Visit.department_id.in_(dept_ids))
        active_patient_ids = [r.patient_id for r in vq.order_by(desc(Visit.created_at)).limit(50).all() if getattr(r, 'patient_id', None)]
        patients = []
        if active_patient_ids:
            patients = Patient.query.filter(Patient.id.in_(active_patient_ids)).order_by(desc(Patient.created_at)).all()
        else:
            patients = Patient.query.order_by(desc(Patient.created_at)).limit(20).all()

        selected_patient = db.session.get(Patient, patient_id) if patient_id else None
        vital_records = []
        if selected_patient:
            vital_records = VitalSigns.query.filter_by(patient_id=selected_patient.id).order_by(
                desc(VitalSigns.recorded_at)
            ).limit(20).all()
        
        return render_template(
            'nurse/vital_signs.html',
            patients=patients,
            selected_patient=selected_patient,
            vital_records=vital_records
        )
    except Exception as e:
        logging.error(f"Error loading vital signs: {str(e)}")
        flash('حدث خطأ في تحميل العلامات الحيوية', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/record-vital-signs/<int:patient_id>', methods=['POST'])
@login_required
def record_vital_signs(patient_id):
    """تسجيل العلامات الحيوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    
    try:
        from models.nurse import VitalSigns

        patient = db.session.get(Patient, patient_id)
        if not patient:
            return jsonify({'success': False, 'message': 'المريض غير موجود'}), 404

        nurse_profile = getattr(current_user, 'nurse_profile', None)
        if isinstance(nurse_profile, (list, tuple)):
            nurse_profile = nurse_profile[0] if nurse_profile else None
        nurse_profile = nurse_profile if nurse_profile else None
        if not nurse_profile:
            return jsonify({'success': False, 'message': 'لا يوجد ملف تمريض مرتبط بهذا المستخدم'}), 400

        bp_systolic_raw = request.form.get('blood_pressure_systolic')
        bp_diastolic_raw = request.form.get('blood_pressure_diastolic')
        bp_raw = (request.form.get('blood_pressure') or '').strip()
        if (not bp_systolic_raw and not bp_diastolic_raw) and bp_raw and '/' in bp_raw:
            parts = [p.strip() for p in bp_raw.split('/') if p.strip()]
            if len(parts) >= 2:
                bp_systolic_raw, bp_diastolic_raw = parts[0], parts[1]

        def _to_int(val):
            val = (val or '').strip()
            return int(val) if val else None

        def _to_float(val):
            val = (val or '').strip()
            return float(val) if val else None

        record = VitalSigns(
            patient_id=patient.id,
            nurse_id=nurse_profile.id,
            blood_pressure_systolic=_to_int(bp_systolic_raw),
            blood_pressure_diastolic=_to_int(bp_diastolic_raw),
            heart_rate=_to_int(request.form.get('heart_rate')),
            temperature=_to_float(request.form.get('temperature')),
            oxygen_saturation=_to_int(request.form.get('oxygen_saturation')),
            respiratory_rate=_to_int(request.form.get('respiratory_rate')),
            weight=_to_float(request.form.get('weight')),
            height=_to_float(request.form.get('height')),
            notes=(request.form.get('notes') or '').strip() or None
        )
        db.session.add(record)
        db.session.commit()

        return jsonify({'success': True, 'message': 'تم تسجيل العلامات الحيوية بنجاح', 'data': record.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error recording vital signs: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تسجيل العلامات الحيوية حالياً'})

@nurse_bp.route('/vitals')
@login_required
@role_required('nurse', 'admin', 'manager')
def vitals():
    """العلامات الحيوية"""
    
    
    return redirect(url_for('nurse.vital_signs'))
