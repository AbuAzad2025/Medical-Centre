"""patients routes - extracted from monolithic doctor.py"""

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
# PATIENTS ROUTES
# =============================================

# مسارات إضافية للطبيب الاحترافي

@doctor_bp.route('/medical-history/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def medical_history(patient_id):
    """السجل الطبي للمريض"""
    
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب السجل الطبي الكامل
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == patient_id
        ).order_by(desc(MedicalRecord.created_at)).all()
        
        previous_visits = Visit.query.filter(
            Visit.patient_id == patient_id
        ).order_by(desc(Visit.visit_date)).limit(10).all()
        
        return render_template('doctor/medical_history.html',
                             patient=patient,
                             medical_records=medical_records,
                             previous_visits=previous_visits)
    except Exception as e:
        logging.error(f"Error loading medical history: {str(e)}")
        flash('حدث خطأ في تحميل السجل الطبي', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/prescriptions-history/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def prescriptions_history(patient_id):
    """تاريخ الوصفات الطبية للمريض"""
    
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب الوصفات السابقة
        prescriptions = Prescription.query.filter(
            Prescription.patient_id == patient_id
        ).order_by(desc(Prescription.created_at)).all()
        
        return render_template('doctor/prescriptions_history.html',
                             patient=patient,
                             prescriptions=prescriptions)
    except Exception as e:
        logging.error(f"Error loading prescriptions history: {str(e)}")
        flash('حدث خطأ في تحميل تاريخ الوصفات', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/print-medical-report/<int:visit_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def print_medical_report(visit_id):
    """طباعة التقرير الطبي"""
    
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        return render_template('doctor/print_medical_report.html',
                             visit=visit)
    except Exception as e:
        logging.error(f"Error printing medical report: {str(e)}")
        flash('حدث خطأ في طباعة التقرير الطبي', 'error')
        return redirect(url_for('doctor.patient_queue'))

# ==================== الميزات الذكية للطبيب ====================

@doctor_bp.route('/patients')
@login_required
@role_required('doctor', 'admin', 'manager')
def patients():
    """بحث المرضى للطبيب (قراءة فقط)"""

    try:
        q = (request.args.get('q') or '').strip()
        from sqlalchemy import or_, func

        base_query = Patient.query
        if q:
            like = f"%{q}%"
            base_query = base_query.filter(
                or_(
                    Patient.first_name.ilike(like),
                    Patient.last_name.ilike(like),
                    Patient.phone.ilike(like),
                    Patient.national_id.ilike(like),
                    Patient.first_name_ar.ilike(like),
                    Patient.last_name_ar.ilike(like)
                )
            )

        # إحصائيات الزيارات: العدد وآخر زيارة
        visits_count_sub = db.session.query(
            Visit.patient_id.label('pid'),
            func.count(Visit.id).label('visits_count'),
            func.max(Visit.visit_date).label('last_visit')
        ).group_by(Visit.patient_id).subquery()

        patients = base_query.outerjoin(
            visits_count_sub, visits_count_sub.c.pid == Patient.id
        ).add_columns(
            visits_count_sub.c.visits_count, visits_count_sub.c.last_visit
        ).order_by(Patient.id.desc()).limit(100).all()

        # صياغة النتائج لواجهة العرض
        results = []
        for p, visits_count, last_visit in patients:
            results.append({
                'id': p.id,
                'full_name': p.full_name,
                'phone': p.phone,
                'national_id': p.national_id,
                'age': p.age,
                'visits_count': int(visits_count or 0),
                'last_visit': last_visit,
            })

        return render_template('doctor/patients.html', q=q, results=results)
    except Exception as e:
        logging.error(f"Error loading doctor patients search: {str(e)}")
        flash('حدث خطأ في تحميل البحث عن المرضى', 'error')
        return redirect(url_for('doctor.patient_queue'))


@doctor_bp.route('/patient-timeline/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def patient_timeline(patient_id: int):
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patients'))

        filter_type = (request.args.get('type') or '').strip().lower()
        events = []

        visits = Visit.query.filter(Visit.patient_id == patient_id).order_by(Visit.visit_date.desc(), Visit.created_at.desc()).limit(200).all()
        for v in visits:
            dt = None
            if getattr(v, 'visit_date', None) and getattr(v, 'visit_time', None):
                try:
                    dt = datetime.combine(v.visit_date, v.visit_time)
                except Exception:
                    dt = None
            if dt is None:
                dt = v.created_at or datetime.now()
            events.append({
                'type': 'visit',
                'dt': dt,
                'title': f"زيارة ({v.visit_type_display})",
                'status': v.status,
                'details': (v.diagnosis or v.symptoms or v.notes or ''),
                'link': url_for('doctor.patient_details', visit_id=v.id) if v.doctor_id == current_user.id else None
            })

        prescriptions = Prescription.query.filter(Prescription.patient_id == patient_id).order_by(Prescription.created_at.desc()).limit(200).all()
        for rx in prescriptions:
            events.append({
                'type': 'prescription',
                'dt': rx.created_at or datetime.now(),
                'title': 'وصفة طبية',
                'status': getattr(rx, 'status', None),
                'details': (getattr(rx, 'additional_notes', None) or getattr(rx, 'notes', None) or ''),
                'link': url_for('doctor.prescriptions_history', patient_id=patient_id)
            })

        lab_reqs = LabRequest.query.filter(LabRequest.patient_id == patient_id).order_by(LabRequest.created_at.desc()).limit(200).all()
        for lr in lab_reqs:
            events.append({
                'type': 'lab',
                'dt': lr.created_at or datetime.now(),
                'title': f"مختبر: {getattr(lr, 'test_name', None) or getattr(lr, 'test_type', None) or 'طلب'}",
                'status': lr.status,
                'details': (getattr(lr, 'reason', None) or getattr(lr, 'notes', None) or ''),
                'link': None
            })

        rad_reqs = RadiologyRequest.query.filter(RadiologyRequest.patient_id == patient_id).order_by(RadiologyRequest.created_at.desc()).limit(200).all()
        for rr in rad_reqs:
            events.append({
                'type': 'radiology',
                'dt': rr.created_at or datetime.now(),
                'title': f"أشعة: {getattr(rr, 'test_name', None) or getattr(rr, 'modality', None) or 'طلب'}",
                'status': rr.status,
                'details': (getattr(rr, 'clinical_info', None) or getattr(rr, 'notes', None) or ''),
                'link': None
            })

        records = MedicalRecord.query.filter(MedicalRecord.patient_id == patient_id).order_by(MedicalRecord.created_at.desc()).limit(200).all()
        for mr in records:
            events.append({
                'type': 'record',
                'dt': mr.created_at or datetime.now(),
                'title': mr.title or 'سجل طبي',
                'status': None,
                'details': mr.details or '',
                'link': url_for('doctor.medical_history', patient_id=patient_id)
            })

        follow_ups = FollowUpRequest.query.filter(FollowUpRequest.patient_id == patient_id).order_by(FollowUpRequest.created_at.desc()).limit(200).all()
        for fu in follow_ups:
            events.append({
                'type': 'follow_up',
                'dt': datetime.combine(fu.suggested_date, datetime.min.time()) if fu.suggested_date else (fu.created_at or datetime.now()),
                'title': 'متابعة مقترحة',
                'status': fu.status,
                'details': fu.notes or '',
                'link': None
            })

        appointments = Appointment.query.filter(Appointment.patient_id == patient_id).order_by(Appointment.starts_at.desc()).limit(200).all()
        for ap in appointments:
            events.append({
                'type': 'appointment',
                'dt': ap.starts_at or datetime.now(),
                'title': 'موعد',
                'status': ap.status,
                'details': ap.notes or '',
                'link': None
            })

        if filter_type:
            events = [e for e in events if e.get('type') == filter_type]
        events.sort(key=lambda e: e.get('dt') or datetime.now(), reverse=True)

        return render_template('doctor/patient_timeline.html', patient=patient, events=events, filter_type=filter_type)
    except Exception as e:
        logging.error(f"Error in patient timeline: {str(e)}")
        flash('حدث خطأ في تحميل الخط الزمني', 'error')
        return redirect(url_for('doctor.patients'))

@doctor_bp.route('/medical-records')
@login_required
@role_required('doctor', 'admin', 'manager')
def medical_records():
    """السجلات الطبية — تُحوِّل لقائمة المرضى لاختيار مريض (لا قالب تفاصيل بلا بيانات)."""
    return redirect(url_for('doctor.patients'))

@doctor_bp.route('/api/patient-search')
@login_required
@role_required_json('doctor', 'admin', 'manager')
def api_patient_search():
    q = request.args.get('q', '').strip()
    query = Patient.query
    if q:
        query = query.filter(
            db.or_(
                Patient.first_name.ilike(f'%{q}%'),
                Patient.last_name.ilike(f'%{q}%'),
                Patient.national_id.ilike(f'%{q}%'),
                Patient.phone.ilike(f'%{q}%')
            )
        )
    patients = query.order_by(Patient.created_at.desc()).limit(10).all()
    results = []
    for p in patients:
        results.append({
            'id': p.id,
            'full_name': p.full_name,
            'national_id': p.national_id,
            'phone': p.phone,
            'visit_count': getattr(p, 'visit_count', 0)
        })
    return jsonify({'patients': results})

@doctor_bp.route('/dental-chart/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def dental_chart(patient_id):
    """خريطة الأسنان التفاعلية"""
    from models.patient import Patient
    from models.dental import DentalChart, DentalTooth, TOOTH_STATES
    import json

    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('doctor.patients'))

    upper_right = [{'fdi': f'1{i}', 'x': i*38, 'y': 0} for i in range(8, 0, -1)]
    upper_left = [{'fdi': f'2{i}', 'x': 160 + i*38, 'y': 0} for i in range(1, 9)]
    lower_left = [{'fdi': f'3{i}', 'x': i*38, 'y': 0} for i in range(8, 0, -1)]
    lower_right = [{'fdi': f'4{i}', 'x': 160 + i*38, 'y': 0} for i in range(1, 9)]

    chart = DentalChart.query.filter_by(patient_id=patient_id).order_by(DentalChart.created_at.desc()).first()
    teeth_map = {}
    if chart:
        for tooth in chart.teeth:
            teeth_map[tooth.fdi_number] = {
                'state': tooth.state,
                'surfaces': tooth.surfaces or {},
                'notes': tooth.notes or ''
            }

    def make_tooth_list(layout):
        return [
            {
                'fdi': t['fdi'], 'x': t['x'], 'y': t['y'],
                'state': teeth_map.get(t['fdi'], {}).get('state', 'sound'),
                'color': TOOTH_STATES.get(teeth_map.get(t['fdi'], {}).get('state', 'sound'), {}).get('color', '#10b981')
            }
            for t in layout
        ]

    return render_template('doctor/dental_chart.html',
                           patient=patient, visit_id=None,
                           states=TOOTH_STATES, states_json=json.dumps(TOOTH_STATES),
                           teeth_json=json.dumps(teeth_map),
                           upper_teeth=make_tooth_list(upper_right + upper_left),
                           lower_teeth=make_tooth_list(lower_left + lower_right))


@doctor_bp.route('/dental-chart/save', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def save_dental_chart():
    """حفظ خريطة الأسنان"""
    from models.dental import DentalChart, DentalTooth
    data = request.get_json(silent=True) or request.form

    raw_patient_id = (data.get('patient_id') if hasattr(data, 'get') else None)
    try:
        patient_id = int(str(raw_patient_id).strip())
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'رقم المريض غير صالح'}), 422

    raw_visit_id = data.get('visit_id')
    visit_id = None
    if raw_visit_id not in (None, '', 'null'):
        try:
            visit_id = int(str(raw_visit_id).strip())
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'رقم الزيارة غير صالح'}), 422

    teeth_data = data.get('teeth', {}) or {}
    if not isinstance(teeth_data, dict):
        return jsonify({'success': False, 'message': 'بيانات الأسنان غير صالحة'}), 422
    notes = data.get('notes', '')

    try:
        chart = DentalChart(
            patient_id=patient_id,
            visit_id=visit_id,
            doctor_id=current_user.id,
            notes=notes
        )
        db.session.add(chart)
        db.session.flush()

        for fdi, info in teeth_data.items():
            if not isinstance(info, dict):
                continue
            if info.get('state') == 'sound' and not info.get('notes') and not info.get('surfaces'):
                continue
            tooth = DentalTooth(
                chart_id=chart.id,
                fdi_number=str(fdi),
                state=info.get('state', 'sound'),
                surfaces=info.get('surfaces') or {},
                notes=info.get('notes', '')
            )
            db.session.add(tooth)

        db.session.commit()
        return jsonify({'success': True, 'chart_id': chart.id})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving dental chart: {e}")
        return jsonify({'success': False, 'message': 'تعذّر حفظ خريطة الأسنان'}), 500
