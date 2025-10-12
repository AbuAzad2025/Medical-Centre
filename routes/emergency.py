"""
مسارات الطوارئ الاحترافية - Professional Emergency Routes
Medical System Professional Emergency Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.emergency import EmergencyCase
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from app_factory import db
import logging
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_, desc

emergency_bp = Blueprint('emergency', __name__)

@emergency_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة تحكم الطوارئ الاحترافية"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات متقدمة للطوارئ
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        # حالات الطوارئ اليوم
        today_emergencies = EmergencyCase.query.filter(
            EmergencyCase.created_at >= today
        ).count()
        
        # الحالات النشطة
        active_emergencies = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['TRIAGE', 'TREATMENT', 'OBSERVATION'])
        ).count()
        
        # الحالات المكتملة اليوم
        completed_today = EmergencyCase.query.filter(
            EmergencyCase.status == 'COMPLETED',
            EmergencyCase.completed_at >= today
        ).count()
        
        # الحالات الأسبوع الماضي
        weekly_emergencies = EmergencyCase.query.filter(
            EmergencyCase.created_at >= week_ago,
            EmergencyCase.status == 'COMPLETED'
        ).count()
        
        # الحالات العاجلة
        urgent_cases = EmergencyCase.query.filter(
            EmergencyCase.priority == 'URGENT',
            EmergencyCase.status.in_(['TRIAGE', 'TREATMENT', 'OBSERVATION'])
        ).count()
        
        # الحالات الحرجة
        critical_cases = EmergencyCase.query.filter(
            EmergencyCase.priority == 'CRITICAL',
            EmergencyCase.status.in_(['TRIAGE', 'TREATMENT', 'OBSERVATION'])
        ).count()
        
        # الوصفات الطبية اليوم
        prescriptions_today = Prescription.query.join(EmergencyCase).filter(
            EmergencyCase.created_at >= today
        ).count()
        
        # طلبات المختبر المعلقة
        pending_lab_requests = LabRequest.query.join(EmergencyCase).filter(
            LabRequest.status == 'PENDING'
        ).count()
        
        # طلبات الأشعة المعلقة
        pending_radiology_requests = RadiologyRequest.query.join(EmergencyCase).filter(
            RadiologyRequest.status == 'PENDING'
        ).count()
        
        # الحالات القادمة (أولوية عالية)
        upcoming_cases = EmergencyCase.query.filter(
            EmergencyCase.status == 'TRIAGE',
            EmergencyCase.priority.in_(['URGENT', 'CRITICAL'])
        ).order_by(EmergencyCase.priority.desc(), EmergencyCase.created_at).limit(5).all()
        
        # الإحصائيات
        stats = {
            'today_emergencies': today_emergencies,
            'active_emergencies': active_emergencies,
            'completed_today': completed_today,
            'weekly_emergencies': weekly_emergencies,
            'urgent_cases': urgent_cases,
            'critical_cases': critical_cases,
            'prescriptions_today': prescriptions_today,
            'pending_lab_requests': pending_lab_requests,
            'pending_radiology_requests': pending_radiology_requests
        }
        
        return render_template('emergency/dashboard.html', 
                             stats=stats, 
                             upcoming_cases=upcoming_cases)
    except Exception as e:
        logging.error(f"Error in emergency dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@emergency_bp.route('/patient-queue')
@login_required
def patient_queue():
    """طابور المرضى في الطوارئ - إدارة متقدمة"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # جلب الحالات الطارئة مع تفاصيل إضافية
        emergencies = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['TRIAGE', 'TREATMENT', 'OBSERVATION'])
        ).order_by(EmergencyCase.priority.desc(), EmergencyCase.created_at).all()
        
        # إحصائيات الطابور
        queue_stats = {
            'total_cases': len(emergencies),
            'triage_cases': len([e for e in emergencies if e.status == 'TRIAGE']),
            'treatment_cases': len([e for e in emergencies if e.status == 'TREATMENT']),
            'observation_cases': len([e for e in emergencies if e.status == 'OBSERVATION']),
            'urgent_cases': len([e for e in emergencies if e.priority == 'URGENT']),
            'critical_cases': len([e for e in emergencies if e.priority == 'CRITICAL'])
        }
        
        return render_template('emergency/patient_queue.html', 
                             emergencies=emergencies, 
                             queue_stats=queue_stats)
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
        from models.emergency_case import EmergencyCase
        
        # جلب حالات الطوارئ التي تحتاج فرز
        cases = EmergencyCase.query.filter_by(status='PENDING').order_by(EmergencyCase.created_at.desc()).all()
        
        return render_template('emergency/triage.html', cases=cases)
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
        emergency = EmergencyCase.query.get_or_404(emergency_id)
        
        if request.method == 'POST':
            # جمع بيانات التقييم
            priority = request.form.get('priority')
            vital_signs = {
                'blood_pressure': request.form.get('blood_pressure'),
                'heart_rate': request.form.get('heart_rate'),
                'temperature': request.form.get('temperature'),
                'oxygen_saturation': request.form.get('oxygen_saturation'),
                'respiratory_rate': request.form.get('respiratory_rate')
            }
            triage_notes = request.form.get('triage_notes')
            
            # تحديث حالة الطوارئ
            emergency.priority = priority
            emergency.vital_signs = vital_signs
            emergency.triage_notes = triage_notes
            emergency.status = 'TREATMENT'
            emergency.triaged_by = current_user.id
            emergency.triaged_at = datetime.utcnow()
            
            db.session.commit()
            flash('تم تقييم حالة المريض بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/triage.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in triage: {str(e)}")
        flash('حدث خطأ في تقييم حالة المريض', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/treatment/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def treatment(emergency_id):
    """علاج الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get_or_404(emergency_id)
        
        if request.method == 'POST':
            # جمع بيانات العلاج
            chief_complaint = request.form.get('chief_complaint')
            diagnosis = request.form.get('diagnosis')
            treatment_given = request.form.get('treatment_given')
            medications = request.form.get('medications')
            procedures = request.form.get('procedures')
            treatment_notes = request.form.get('treatment_notes')
            
            # تحديث حالة الطوارئ
            emergency.chief_complaint = chief_complaint
            emergency.diagnosis = diagnosis
            emergency.treatment_given = treatment_given
            emergency.medications = medications
            emergency.procedures = procedures
            emergency.treatment_notes = treatment_notes
            emergency.status = 'OBSERVATION'
            emergency.treated_by = current_user.id
            emergency.treated_at = datetime.utcnow()
            
            db.session.commit()
            flash('تم تسجيل العلاج بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/emergency_treatment.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in emergency treatment: {str(e)}")
        flash('حدث خطأ في تسجيل العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/prescription/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def prescription(emergency_id):
    """وصفة طبية للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get_or_404(emergency_id)
        
        if request.method == 'POST':
            # جمع بيانات الوصفة
            medications = request.form.getlist('medications[]')
            dosages = request.form.getlist('dosages[]')
            frequencies = request.form.getlist('frequencies[]')
            durations = request.form.getlist('durations[]')
            instructions = request.form.getlist('instructions[]')
            
            # إنشاء الوصفة
            prescription_data = []
            for i, medication in enumerate(medications):
                if medication:
                    prescription_data.append({
                        'medication': medication,
                        'dosage': dosages[i] if i < len(dosages) else '',
                        'frequency': frequencies[i] if i < len(frequencies) else '',
                        'duration': durations[i] if i < len(durations) else '',
                        'instructions': instructions[i] if i < len(instructions) else ''
                    })
            
            emergency.prescription = prescription_data
            emergency.prescribed_by = current_user.id
            emergency.prescribed_at = datetime.utcnow()
            
            db.session.commit()
            flash('تم إنشاء الوصفة بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/prescription.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in emergency prescription: {str(e)}")
        flash('حدث خطأ في إنشاء الوصفة', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/lab-request/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def lab_request(emergency_id):
    """طلب فحوصات للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get_or_404(emergency_id)
        
        if request.method == 'POST':
            # جمع بيانات طلب الفحوصات
            tests_requested = request.form.getlist('tests[]')
            urgency = request.form.get('urgency')
            notes = request.form.get('notes')
            
            # إنشاء طلب الفحوصات
            lab_request_data = {
                'tests': tests_requested,
                'urgency': urgency,
                'notes': notes,
                'requested_by': current_user.id,
                'requested_at': datetime.utcnow()
            }
            
            emergency.lab_request = lab_request_data
            db.session.commit()
            flash('تم إرسال طلب الفحوصات بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/lab_request.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in emergency lab request: {str(e)}")
        flash('حدث خطأ في إرسال طلب الفحوصات', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/radiology-request/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def radiology_request(emergency_id):
    """طلب أشعة للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get_or_404(emergency_id)
        
        if request.method == 'POST':
            # جمع بيانات طلب الأشعة
            imaging_type = request.form.get('imaging_type')
            body_part = request.form.get('body_part')
            urgency = request.form.get('urgency')
            clinical_question = request.form.get('clinical_question')
            notes = request.form.get('notes')
            
            # إنشاء طلب الأشعة
            radiology_request_data = {
                'imaging_type': imaging_type,
                'body_part': body_part,
                'urgency': urgency,
                'clinical_question': clinical_question,
                'notes': notes,
                'requested_by': current_user.id,
                'requested_at': datetime.utcnow()
            }
            
            emergency.radiology_request = radiology_request_data
            db.session.commit()
            flash('تم إرسال طلب الأشعة بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/radiology_request.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in emergency radiology request: {str(e)}")
        flash('حدث خطأ في إرسال طلب الأشعة', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/emergency-report/<int:emergency_id>')
@login_required
def emergency_report(emergency_id):
    """تقرير الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get_or_404(emergency_id)
        return render_template('emergency/emergency_report.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error generating emergency report: {str(e)}")
        flash('حدث خطأ في إنشاء تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/end-treatment/<int:emergency_id>', methods=['POST'])
@login_required
def end_treatment(emergency_id):
    """إنهاء العلاج في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get_or_404(emergency_id)
        
        # إنهاء العلاج
        emergency.status = 'COMPLETED'
        emergency.completed_at = datetime.utcnow()
        emergency.completed_by = current_user.id
        
        # إرجاع الزيارة للاستقبال للأرشفة
        if emergency.visit:
            emergency.visit.status = 'READY_FOR_ARCHIVE'
            emergency.visit.completed_at = datetime.utcnow()
            emergency.visit.completed_by = current_user.id
        
        db.session.commit()
        flash('تم إنهاء العلاج بنجاح وإرجاع الزيارة للاستقبال', 'success')
        return redirect(url_for('emergency.patient_queue'))
    except Exception as e:
        logging.error(f"Error ending emergency treatment: {str(e)}")
        flash('حدث خطأ في إنهاء العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/start-treatment/<int:emergency_id>', methods=['POST'])
@login_required
def start_treatment(emergency_id):
    """بدء علاج حالة الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # تحديث حالة الطوارئ
        emergency.status = 'TREATMENT'
        emergency.treatment_started_at = datetime.utcnow()
        emergency.treated_by = current_user.id
        
        db.session.commit()
        
        flash('تم بدء العلاج بنجاح', 'success')
        return redirect(url_for('emergency.patient_details', emergency_id=emergency_id))
    except Exception as e:
        logging.error(f"Error starting treatment: {str(e)}")
        flash('حدث خطأ في بدء العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/patient-details/<int:emergency_id>')
@login_required
def patient_details(emergency_id):
    """تفاصيل حالة الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب السجل الطبي للمريض
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == emergency.patient_id
        ).order_by(desc(MedicalRecord.created_at)).limit(10).all()
        
        # جلب الوصفات السابقة
        previous_prescriptions = Prescription.query.filter(
            Prescription.patient_id == emergency.patient_id
        ).order_by(desc(Prescription.created_at)).limit(5).all()
        
        # جلب طلبات المختبر والأشعة
        lab_requests = LabRequest.query.filter(
            LabRequest.emergency_id == emergency_id
        ).all()
        
        radiology_requests = RadiologyRequest.query.filter(
            RadiologyRequest.emergency_id == emergency_id
        ).all()
        
        return render_template('emergency/patient_details.html',
                             emergency=emergency,
                             medical_records=medical_records,
                             previous_prescriptions=previous_prescriptions,
                             lab_requests=lab_requests,
                             radiology_requests=radiology_requests)
    except Exception as e:
        logging.error(f"Error loading patient details: {str(e)}")
        flash('حدث خطأ في تحميل تفاصيل المريض', 'error')
        return redirect(url_for('emergency.patient_queue'))

# مسارات إضافية للطوارئ الاحترافية

@emergency_bp.route('/medical-history/<int:patient_id>')
@login_required
def medical_history(patient_id):
    """السجل الطبي للمريض في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب السجل الطبي الكامل
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == patient_id
        ).order_by(desc(MedicalRecord.created_at)).all()
        
        # جلب حالات الطوارئ السابقة
        previous_emergencies = EmergencyCase.query.filter(
            EmergencyCase.patient_id == patient_id,
            EmergencyCase.status == 'COMPLETED'
        ).order_by(desc(EmergencyCase.created_at)).limit(10).all()
        
        return render_template('emergency/medical_history.html',
                             patient=patient,
                             medical_records=medical_records,
                             previous_emergencies=previous_emergencies)
    except Exception as e:
        logging.error(f"Error loading medical history: {str(e)}")
        flash('حدث خطأ في تحميل السجل الطبي', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/prescriptions-history/<int:patient_id>')
@login_required
def prescriptions_history(patient_id):
    """تاريخ الوصفات الطبية للمريض في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب الوصفات السابقة
        prescriptions = Prescription.query.filter(
            Prescription.patient_id == patient_id
        ).order_by(desc(Prescription.created_at)).all()
        
        return render_template('emergency/prescriptions_history.html',
                             patient=patient,
                             prescriptions=prescriptions)
    except Exception as e:
        logging.error(f"Error loading prescriptions history: {str(e)}")
        flash('حدث خطأ في تحميل تاريخ الوصفات', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/lab-results/<int:patient_id>')
@login_required
def lab_results(patient_id):
    """نتائج المختبر للمريض في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب نتائج المختبر
        lab_requests = LabRequest.query.filter(
            LabRequest.patient_id == patient_id
        ).order_by(desc(LabRequest.created_at)).all()
        
        return render_template('emergency/lab_results.html',
                             patient=patient,
                             lab_requests=lab_requests)
    except Exception as e:
        logging.error(f"Error loading lab results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج المختبر', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/radiology-results/<int:patient_id>')
@login_required
def radiology_results(patient_id):
    """نتائج الأشعة للمريض في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب نتائج الأشعة
        radiology_requests = RadiologyRequest.query.filter(
            RadiologyRequest.patient_id == patient_id
        ).order_by(desc(RadiologyRequest.created_at)).all()
        
        return render_template('emergency/radiology_results.html',
                             patient=patient,
                             radiology_requests=radiology_requests)
    except Exception as e:
        logging.error(f"Error loading radiology results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج الأشعة', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/print-prescription/<int:prescription_id>')
@login_required
def print_prescription(prescription_id):
    """طباعة الوصفة الطبية للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            flash('الوصفة غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/print_prescription.html',
                             prescription=prescription)
    except Exception as e:
        logging.error(f"Error printing prescription: {str(e)}")
        flash('حدث خطأ في طباعة الوصفة', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/print-emergency-report/<int:emergency_id>')
@login_required
def print_emergency_report(emergency_id):
    """طباعة تقرير الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = EmergencyCase.query.get(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/print_emergency_report.html',
                             emergency=emergency)
    except Exception as e:
        logging.error(f"Error printing emergency report: {str(e)}")
        flash('حدث خطأ في طباعة تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))

# ==================== الميزات الذكية للطوارئ ====================

def get_emergency_ai_triage():
    """ذكاء اصطناعي لتصنيف الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        # تحليل أولويات الحالات
        priority_analysis = {
            'critical': EmergencyCase.query.filter(EmergencyCase.priority == 'CRITICAL').count(),
            'urgent': EmergencyCase.query.filter(EmergencyCase.priority == 'URGENT').count(),
            'normal': EmergencyCase.query.filter(EmergencyCase.priority == 'NORMAL').count(),
            'low': EmergencyCase.query.filter(EmergencyCase.priority == 'LOW').count()
        }
        
        # تحليل أوقات الاستجابة
        response_times = []
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in recent_cases:
            if case.treated_at and case.created_at:
                response_time = (case.treated_at - case.created_at).total_seconds() / 60  # بالدقائق
                response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # اقتراحات التحسين
        triage_suggestions = []
        
        if avg_response_time > 30:  # أكثر من 30 دقيقة
            triage_suggestions.append({
                'type': 'response_time',
                'title': 'تحسين أوقات الاستجابة',
                'description': f'متوسط وقت الاستجابة: {avg_response_time:.1f} دقيقة',
                'suggestion': 'تحسين عملية التصنيف لتسريع الاستجابة'
            })
        
        if priority_analysis['critical'] > 5:
            triage_suggestions.append({
                'type': 'critical_cases',
                'title': 'حالات حرجة عالية',
                'description': f'عدد الحالات الحرجة: {priority_analysis["critical"]}',
                'suggestion': 'مراجعة الموارد المتاحة للحالات الحرجة'
            })
        
        return {
            'priority_analysis': priority_analysis,
            'avg_response_time': round(avg_response_time, 2),
            'triage_suggestions': triage_suggestions,
            'efficiency_score': calculate_triage_efficiency(avg_response_time, priority_analysis)
        }
    except Exception as e:
        logging.error(f"Error getting emergency AI triage: {str(e)}")
        return {}

def get_critical_alert_system():
    """نظام التنبيهات الحرجة"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        alerts = []
        
        # تنبيهات الحالات الحرجة
        critical_cases = EmergencyCase.query.filter(
            EmergencyCase.priority == 'CRITICAL',
            EmergencyCase.status.in_(['TRIAGE', 'TREATMENT'])
        ).count()
        
        if critical_cases > 0:
            alerts.append({
                'type': 'critical',
                'title': 'حالات حرجة',
                'message': f'يوجد {critical_cases} حالة حرجة تحتاج انتباه فوري',
                'priority': 'high',
                'action': 'مراجعة فورية'
            })
        
        # تنبيهات أوقات الانتظار الطويلة
        long_waiting = EmergencyCase.query.filter(
            EmergencyCase.status == 'TRIAGE',
            EmergencyCase.created_at < datetime.now() - timedelta(minutes=30)
        ).count()
        
        if long_waiting > 0:
            alerts.append({
                'type': 'waiting_time',
                'title': 'انتظار طويل',
                'message': f'يوجد {long_waiting} حالة تنتظر أكثر من 30 دقيقة',
                'priority': 'medium',
                'action': 'مراجعة الطابور'
            })
        
        # تنبيهات الموارد
        active_cases = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['TRIAGE', 'TREATMENT', 'OBSERVATION'])
        ).count()
        
        if active_cases > 20:
            alerts.append({
                'type': 'resource_usage',
                'title': 'استخدام الموارد',
                'message': f'عدد الحالات النشطة: {active_cases} - قريب من السعة القصوى',
                'priority': 'medium',
                'action': 'مراجعة الموارد'
            })
        
        return alerts
    except Exception as e:
        logging.error(f"Error getting critical alert system: {str(e)}")
        return []

def get_emergency_workflow_ai():
    """ذكاء اصطناعي لسير عمل الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        # تحليل مراحل العلاج
        workflow_analysis = {
            'triage': EmergencyCase.query.filter(EmergencyCase.status == 'TRIAGE').count(),
            'treatment': EmergencyCase.query.filter(EmergencyCase.status == 'TREATMENT').count(),
            'observation': EmergencyCase.query.filter(EmergencyCase.status == 'OBSERVATION').count(),
            'completed': EmergencyCase.query.filter(EmergencyCase.status == 'COMPLETED').count()
        }
        
        # تحليل أوقات المراحل
        stage_times = []
        completed_cases = EmergencyCase.query.filter(
            EmergencyCase.status == 'COMPLETED',
            EmergencyCase.completed_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in completed_cases:
            if case.treated_at and case.created_at:
                total_time = (case.treated_at - case.created_at).total_seconds() / 60
                stage_times.append(total_time)
        
        avg_total_time = sum(stage_times) / len(stage_times) if stage_times else 0
        
        # اقتراحات التحسين
        workflow_suggestions = []
        
        if workflow_analysis['triage'] > 10:
            workflow_suggestions.append({
                'type': 'triage_bottleneck',
                'title': 'عنق الزجاجة في التصنيف',
                'description': f'عدد الحالات في التصنيف: {workflow_analysis["triage"]}',
                'suggestion': 'زيادة الموارد في مرحلة التصنيف'
            })
        
        if avg_total_time > 60:  # أكثر من ساعة
            workflow_suggestions.append({
                'type': 'total_time',
                'title': 'تحسين الوقت الإجمالي',
                'description': f'متوسط الوقت الإجمالي: {avg_total_time:.1f} دقيقة',
                'suggestion': 'تحسين سير العمل لتقليل الوقت الإجمالي'
            })
        
        return {
            'workflow_analysis': workflow_analysis,
            'avg_total_time': round(avg_total_time, 2),
            'workflow_suggestions': workflow_suggestions,
            'efficiency_score': calculate_workflow_efficiency(workflow_analysis, avg_total_time)
        }
    except Exception as e:
        logging.error(f"Error getting emergency workflow AI: {str(e)}")
        return {}

def get_patient_vital_monitoring():
    """مراقبة العلامات الحيوية للمرضى"""
    try:
        from models.emergency import EmergencyCase
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        # تحليل العلامات الحيوية
        vital_signs_analysis = {
            'normal': 0,
            'abnormal': 0,
            'critical': 0
        }
        
        # تحليل الحالات حسب العلامات الحيوية
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in recent_cases:
            if case.vital_signs:
                # تحليل مبسط للعلامات الحيوية
                vital_data = case.vital_signs
                if 'critical' in str(vital_data).lower():
                    vital_signs_analysis['critical'] += 1
                elif 'abnormal' in str(vital_data).lower():
                    vital_signs_analysis['abnormal'] += 1
                else:
                    vital_signs_analysis['normal'] += 1
        
        # توصيات المراقبة
        monitoring_recommendations = []
        
        if vital_signs_analysis['critical'] > 0:
            monitoring_recommendations.append({
                'type': 'critical_vitals',
                'title': 'علامات حيوية حرجة',
                'description': f'عدد الحالات بعلامات حرجة: {vital_signs_analysis["critical"]}',
                'suggestion': 'مراقبة مستمرة للحالات الحرجة'
            })
        
        if vital_signs_analysis['abnormal'] > 5:
            monitoring_recommendations.append({
                'type': 'abnormal_vitals',
                'title': 'علامات حيوية غير طبيعية',
                'description': f'عدد الحالات بعلامات غير طبيعية: {vital_signs_analysis["abnormal"]}',
                'suggestion': 'مراجعة بروتوكولات المراقبة'
            })
        
        return {
            'vital_signs_analysis': vital_signs_analysis,
            'monitoring_recommendations': monitoring_recommendations,
            'total_cases_monitored': sum(vital_signs_analysis.values())
        }
    except Exception as e:
        logging.error(f"Error getting patient vital monitoring: {str(e)}")
        return {}

def get_emergency_resource_management():
    """إدارة موارد الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.user import User
        from datetime import datetime, timedelta
        
        # تحليل الموارد المتاحة
        total_staff = User.query.filter(User.role == 'emergency').count()
        active_staff = User.query.filter(
            User.role == 'emergency',
            User.last_login >= datetime.now() - timedelta(hours=24)
        ).count()
        
        # تحليل الأحمال
        today = datetime.now().date()
        today_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= today
        ).count()
        
        # تحليل الكفاءة
        efficiency_score = (active_staff / total_staff * 100) if total_staff > 0 else 0
        
        # توصيات إدارة الموارد
        resource_recommendations = []
        
        if efficiency_score < 70:
            resource_recommendations.append({
                'type': 'staff_efficiency',
                'title': 'كفاءة الموظفين',
                'description': f'معدل كفاءة الموظفين: {efficiency_score:.1f}%',
                'suggestion': 'تحسين مشاركة الموظفين أو إضافة موارد'
            })
        
        if today_cases > 30:
            resource_recommendations.append({
                'type': 'workload',
                'title': 'عبء العمل',
                'description': f'عدد الحالات اليوم: {today_cases}',
                'suggestion': 'مراجعة توزيع الأحمال أو إضافة موارد'
            })
        
        return {
            'total_staff': total_staff,
            'active_staff': active_staff,
            'today_cases': today_cases,
            'efficiency_score': round(efficiency_score, 2),
            'resource_recommendations': resource_recommendations
        }
    except Exception as e:
        logging.error(f"Error getting emergency resource management: {str(e)}")
        return {}

def get_trauma_protocols():
    """بروتوكولات الصدمات"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        # تحليل أنواع الصدمات
        trauma_analysis = {
            'trauma_cases': 0,
            'medical_emergencies': 0,
            'surgical_emergencies': 0,
            'other': 0
        }
        
        # تحليل الحالات الحديثة
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=30)
        ).all()
        
        for case in recent_cases:
            if case.chief_complaint:
                complaint = case.chief_complaint.lower()
                if any(word in complaint for word in ['حادث', 'سقوط', 'ضربة', 'جرح']):
                    trauma_analysis['trauma_cases'] += 1
                elif any(word in complaint for word in ['ألم', 'صدر', 'قلب', 'تنفس']):
                    trauma_analysis['medical_emergencies'] += 1
                elif any(word in complaint for word in ['جراحة', 'عملية', 'بطن']):
                    trauma_analysis['surgical_emergencies'] += 1
                else:
                    trauma_analysis['other'] += 1
        
        # توصيات البروتوكولات
        protocol_recommendations = []
        
        if trauma_analysis['trauma_cases'] > 10:
            protocol_recommendations.append({
                'type': 'trauma_protocol',
                'title': 'بروتوكول الصدمات',
                'description': f'عدد حالات الصدمات: {trauma_analysis["trauma_cases"]}',
                'suggestion': 'مراجعة بروتوكولات الصدمات وتدريب الفريق'
            })
        
        if trauma_analysis['medical_emergencies'] > 15:
            protocol_recommendations.append({
                'type': 'medical_protocol',
                'title': 'بروتوكول الطوارئ الطبية',
                'description': f'عدد الطوارئ الطبية: {trauma_analysis["medical_emergencies"]}',
                'suggestion': 'تحسين بروتوكولات الطوارئ الطبية'
            })
        
        return {
            'trauma_analysis': trauma_analysis,
            'protocol_recommendations': protocol_recommendations,
            'total_cases_analyzed': sum(trauma_analysis.values())
        }
    except Exception as e:
        logging.error(f"Error getting trauma protocols: {str(e)}")
        return {}

def get_emergency_analytics():
    """تحليلات الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.prescription import Prescription
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from datetime import datetime, timedelta
        
        # تحليل الأداء
        total_cases = EmergencyCase.query.count()
        completed_cases = EmergencyCase.query.filter(EmergencyCase.status == 'COMPLETED').count()
        completion_rate = (completed_cases / total_cases * 100) if total_cases > 0 else 0
        
        # تحليل الأوقات
        avg_treatment_time = db.session.query(func.avg(
            func.extract('epoch', EmergencyCase.treated_at - EmergencyCase.created_at) / 60
        )).filter(
            EmergencyCase.status == 'COMPLETED',
            EmergencyCase.treated_at.isnot(None)
        ).scalar() or 0
        
        # تحليل الموارد
        prescriptions_count = Prescription.query.join(EmergencyCase).count()
        lab_requests_count = LabRequest.query.join(EmergencyCase).count()
        radiology_requests_count = RadiologyRequest.query.join(EmergencyCase).count()
        
        return {
            'completion_rate': round(completion_rate, 2),
            'avg_treatment_time': round(avg_treatment_time, 2),
            'prescriptions_count': prescriptions_count,
            'lab_requests_count': lab_requests_count,
            'radiology_requests_count': radiology_requests_count,
            'performance_score': calculate_emergency_performance_score(completion_rate, avg_treatment_time)
        }
    except Exception as e:
        logging.error(f"Error getting emergency analytics: {str(e)}")
        return {}

def get_smart_emergency_recommendations():
    """التوصيات الذكية للطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.user import User
        from datetime import datetime, timedelta
        
        recommendations = []
        
        # تحليل النمو
        week_ago = datetime.now().date() - timedelta(days=7)
        cases_this_week = EmergencyCase.query.filter(
            EmergencyCase.created_at >= week_ago
        ).count()
        
        cases_last_week = EmergencyCase.query.filter(
            EmergencyCase.created_at >= week_ago - timedelta(days=7),
            EmergencyCase.created_at < week_ago
        ).count()
        
        growth_rate = ((cases_this_week - cases_last_week) / cases_last_week * 100) if cases_last_week > 0 else 0
        
        if growth_rate > 20:
            recommendations.append({
                'type': 'growth',
                'title': 'نمو سريع في الطوارئ',
                'description': f'زيادة {growth_rate:.1f}% في حالات الطوارئ',
                'suggestion': 'مراجعة الموارد والاستعداد للزيادة'
            })
        
        # تحليل الكفاءة
        avg_response_time = db.session.query(func.avg(
            func.extract('epoch', EmergencyCase.treated_at - EmergencyCase.created_at) / 60
        )).filter(
            EmergencyCase.status == 'COMPLETED',
            EmergencyCase.treated_at.isnot(None)
        ).scalar() or 0
        
        if avg_response_time > 45:
            recommendations.append({
                'type': 'efficiency',
                'title': 'تحسين الكفاءة',
                'description': f'متوسط وقت الاستجابة: {avg_response_time:.1f} دقيقة',
                'suggestion': 'تحسين العمليات لتسريع الاستجابة'
            })
        
        # تحليل الموظفين
        active_emergency_staff = User.query.filter(
            User.role == 'emergency',
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        total_emergency_staff = User.query.filter(User.role == 'emergency').count()
        
        if active_emergency_staff < total_emergency_staff * 0.8:
            recommendations.append({
                'type': 'staff_engagement',
                'title': 'مشاركة الموظفين',
                'description': f'فقط {active_emergency_staff} من {total_emergency_staff} موظف نشط',
                'suggestion': 'تحفيز الموظفين أو إعادة توزيع المهام'
            })
        
        return recommendations
    except Exception as e:
        logging.error(f"Error getting smart emergency recommendations: {str(e)}")
        return []

# دوال مساعدة
def calculate_triage_efficiency(avg_response_time, priority_analysis):
    """حساب كفاءة التصنيف"""
    # نقاط وقت الاستجابة (كلما قل الوقت كلما زادت النقاط)
    response_score = max(0, 100 - (avg_response_time / 10))
    
    # نقاط الأولوية (توازن في الأولويات)
    critical_ratio = priority_analysis['critical'] / sum(priority_analysis.values()) if sum(priority_analysis.values()) > 0 else 0
    priority_score = 100 - (critical_ratio * 50)  # تقليل النقاط مع زيادة الحالات الحرجة
    
    return (response_score + priority_score) / 2

def calculate_workflow_efficiency(workflow_analysis, avg_total_time):
    """حساب كفاءة سير العمل"""
    # نقاط التوزيع (توازن في المراحل)
    total_cases = sum(workflow_analysis.values())
    if total_cases == 0:
        return 0
    
    distribution_score = 100 - abs(workflow_analysis['triage'] - workflow_analysis['treatment']) / total_cases * 100
    
    # نقاط الوقت (كلما قل الوقت كلما زادت النقاط)
    time_score = max(0, 100 - (avg_total_time / 2))
    
    return (distribution_score + time_score) / 2

def calculate_emergency_performance_score(completion_rate, avg_treatment_time):
    """حساب نقاط أداء الطوارئ"""
    # نقاط الإنجاز
    completion_score = completion_rate
    
    # نقاط الوقت (كلما قل الوقت كلما زادت النقاط)
    time_score = max(0, 100 - (avg_treatment_time / 2))
    
    return (completion_score + time_score) / 2

@emergency_bp.route('/cases')
@login_required
def cases():
    """حالات الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('emergency/list.html')

@emergency_bp.route('/patients')
@login_required
def patients():
    """مرضى الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('emergency/patient_queue.html')

@emergency_bp.route('/reports')
@login_required
def reports():
    """تقارير الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('emergency/emergency_visits.html')

@emergency_bp.route('/queue')
@login_required
def queue():
    """طابور الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('emergency/patient_queue.html')



