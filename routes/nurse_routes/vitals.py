"""vitals routes - extracted from monolithic nurse_routes.py"""

import logging

# Imports
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, select

from app.extensions import db
from models.patient import Patient
from models.visit import Visit
from routes.nurse_routes import _accessible_department_ids, nurse_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required, role_required_json

# =============================================
# VITALS ROUTES
# =============================================


@nurse_bp.route('/vital-signs')
@login_required
@role_required('nurse', 'manager')
def vital_signs():
    """العلامات الحيوية"""

    try:
        from models.nurse import VitalSigns

        visit_id = request.args.get('visit_id', type=int)
        patient_id = request.args.get('patient_id', type=int)
        if not patient_id and visit_id:
            visit = (
                db.session.execute(
                    select(Visit).filter(
                        Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            patient_id = visit.patient_id if visit else None
        vq = select(Visit)
        dept_ids = _accessible_department_ids()
        if dept_ids is not None and dept_ids:
            vq = vq.filter(Visit.department_id.in_(dept_ids))
            vq = vq.filter(Visit.department_id.in_(dept_ids))
        active_patient_ids = [
            r.patient_id
            for r in db.session.execute(vq.order_by(desc(Visit.created_at)).limit(50))
            .scalars()
            .all()
            if getattr(r, 'patient_id', None)
        ]
        patients = []
        if active_patient_ids:
            patients = (
                db.session.execute(
                    select(Patient)
                    .filter(Patient.id.in_(active_patient_ids))
                    .order_by(desc(Patient.created_at))
                )
                .scalars()
                .all()
            )
        else:
            patients = (
                db.session.execute(select(Patient).order_by(desc(Patient.created_at)).limit(20))
                .scalars()
                .all()
            )

        selected_patient = (
            db.session.execute(
                select(Patient).filter(
                    Patient.id == patient_id, Patient.tenant_id == current_user.tenant_id
                )
            )
            .scalars()
            .first()
            if patient_id
            else None
        )
        vital_records = []
        if selected_patient:
            vital_records = (
                db.session.execute(
                    select(VitalSigns)
                    .filter_by(patient_id=selected_patient.id)
                    .order_by(desc(VitalSigns.recorded_at))
                    .limit(20)
                )
                .scalars()
                .all()
            )

        return render_template(
            'nurse/vital_signs.html',
            patients=patients,
            selected_patient=selected_patient,
            vital_records=vital_records,
        )
    except Exception:
        logging.exception('Error loading vital signs: %s')
        flash('حدث خطأ في تحميل العلامات الحيوية', 'error')
        return redirect(url_for('nurse.dashboard'))


@nurse_bp.route('/record-vital-signs/<int:patient_id>', methods=['POST'])
@login_required
@role_required_json('nurse', 'manager')
def record_vital_signs(patient_id):
    """تسجيل العلامات الحيوية"""

    try:
        from models.nurse import VitalSigns

        patient = (
            db.session.execute(
                select(Patient).filter(
                    Patient.id == patient_id, Patient.tenant_id == current_user.tenant_id
                )
            )
            .scalars()
            .first()
        )
        if not patient:
            return jsonify({'success': False, 'message': 'المريض غير موجود'}), 404

        nurse_profile = getattr(current_user, 'nurse_profile', None)
        if isinstance(nurse_profile, (list, tuple)):
            nurse_profile = nurse_profile[0] if nurse_profile else None
        nurse_profile = nurse_profile if nurse_profile else None
        if not nurse_profile:
            return jsonify(
                {'success': False, 'message': 'لا يوجد ملف تمريض مرتبط بهذا المستخدم'}
            ), 400

        bp_systolic_raw = request.form.get('blood_pressure_systolic')
        bp_diastolic_raw = request.form.get('blood_pressure_diastolic')
        bp_raw = (request.form.get('blood_pressure') or '').strip()
        if (not bp_systolic_raw and not bp_diastolic_raw) and bp_raw and '/' in bp_raw:
            parts = [p.strip() for p in bp_raw.split('/') if p.strip()]
            if len(parts) >= 2:
                bp_systolic_raw, bp_diastolic_raw = parts[0], parts[1]

        def _to_int(val):
            try:
                val = (val or '').strip()
                return int(val) if val else None
            except Exception:
                return None

        def _to_float(val):
            try:
                val = (val or '').strip()
                return float(val) if val else None
            except Exception:
                return None

        systolic = _to_int(bp_systolic_raw)
        diastolic = _to_int(bp_diastolic_raw)
        heart_rate = _to_int(request.form.get('heart_rate'))
        temperature = _to_float(request.form.get('temperature'))
        oxygen_saturation = _to_int(request.form.get('oxygen_saturation'))
        respiratory_rate = _to_int(request.form.get('respiratory_rate'))
        weight = _to_float(request.form.get('weight'))
        height = _to_float(request.form.get('height'))
        blood_sugar = _to_float(request.form.get('blood_sugar'))
        notes_val = (request.form.get('notes') or '').strip() or None
        if systolic is not None and diastolic is not None and diastolic >= systolic:
            return jsonify({'success': False, 'message': 'ضغط الدم غير منطقي'}), 400
        if temperature is not None and not 30 <= temperature <= 45:
            return jsonify({'success': False, 'message': 'درجة الحرارة خارج النطاق'}), 400
        if heart_rate is not None and not 20 <= heart_rate <= 250:
            return jsonify({'success': False, 'message': 'معدل النبض خارج النطاق'}), 400
        if oxygen_saturation is not None and not 50 <= oxygen_saturation <= 100:
            return jsonify({'success': False, 'message': 'تشبع الأكسجين خارج النطاق'}), 400
        if any(v is None for v in [systolic, diastolic, heart_rate, temperature, oxygen_saturation, respiratory_rate, weight, height, blood_sugar]) and not notes_val:
            has_any = any(v is not None for v in [systolic, diastolic, heart_rate, temperature, oxygen_saturation, respiratory_rate, weight, height, blood_sugar])
            if not has_any:
                return jsonify({'success': False, 'message': 'لا توجد علامات حيوية للإدخال'}), 400
        record = VitalSigns(
            patient_id=patient.id,
            nurse_id=nurse_profile.id,
            blood_pressure_systolic=systolic,
            blood_pressure_diastolic=diastolic,
            heart_rate=heart_rate,
            temperature=temperature,
            oxygen_saturation=oxygen_saturation,
            respiratory_rate=respiratory_rate,
            weight=weight,
            height=height,
            blood_sugar=blood_sugar,
            notes=notes_val,
        )
        db.session.add(record)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        return jsonify(
            {
                'success': True,
                'message': 'تم تسجيل العلامات الحيوية بنجاح',
                'data': record.to_dict(),
            }
        )

    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Error recording vital signs: %s')
        return jsonify({'success': False, 'message': 'تعذر تسجيل العلامات الحيوية حالياً'})


@nurse_bp.route('/vitals')
@login_required
@role_required('nurse', 'admin', 'manager')
def vitals():
    """العلامات الحيوية"""

    return redirect(url_for('nurse.vital_signs'))
