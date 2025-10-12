"""
مسارات الطبيب الاحترافية - Professional Doctor Routes
Medical System Professional Doctor Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from models.appointment import Appointment
from app_factory import db
import logging
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_, desc

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة تحكم الطبيب الاحترافية"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات متقدمة للطبيب
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        # الزيارات اليوم
        today_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status.in_(['READY', 'IN_PROGRESS'])
        ).count()
        
        # الزيارات المعلقة
        pending_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status == 'READY'
        ).count()
        
        # الزيارات المكتملة اليوم
        completed_today = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status == 'READY_FOR_ARCHIVE'
        ).count()
        
        # الزيارات الأسبوع الماضي
        weekly_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date >= week_ago,
            Visit.status == 'READY_FOR_ARCHIVE'
        ).count()
        
        # الوصفات الطبية اليوم
        prescriptions_today = Prescription.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today
        ).count()
        
        # طلبات المختبر المعلقة
        pending_lab_requests = LabRequest.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            LabRequest.status == 'PENDING'
        ).count()
        
        # طلبات الأشعة المعلقة
        pending_radiology_requests = RadiologyRequest.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            RadiologyRequest.status == 'PENDING'
        ).count()
        
        # المرضى القادمين اليوم
        upcoming_patients = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status == 'READY'
        ).order_by(Visit.visit_time).limit(5).all()
        
        # الإحصائيات
        stats = {
            'today_visits': today_visits,
            'pending_visits': pending_visits,
            'completed_today': completed_today,
            'weekly_visits': weekly_visits,
            'prescriptions_today': prescriptions_today,
            'pending_lab_requests': pending_lab_requests,
            'pending_radiology_requests': pending_radiology_requests
        }
        
        return render_template('doctor/dashboard.html', 
                             stats=stats, 
                             upcoming_patients=upcoming_patients)
    except Exception as e:
        logging.error(f"Error in doctor dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@doctor_bp.route('/patient-queue')
@login_required
def patient_queue():
    """طابور المرضى للطبيب - إدارة متقدمة"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # جلب المرضى المخصصين للطبيب مع تفاصيل إضافية
        patients = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status.in_(['READY', 'IN_PROGRESS'])
        ).order_by(Visit.visit_time).all()
        
        # إحصائيات الطابور
        queue_stats = {
            'total_patients': len(patients),
            'ready_patients': len([p for p in patients if p.status == 'READY']),
            'in_progress': len([p for p in patients if p.status == 'IN_PROGRESS']),
            'average_wait_time': 15  # يمكن حسابها من البيانات الفعلية
        }
        
        return render_template('doctor/patient_queue.html', 
                             patients=patients, 
                             queue_stats=queue_stats)
    except Exception as e:
        logging.error(f"Error loading patient queue: {str(e)}")
        flash('حدث خطأ في تحميل طابور المرضى', 'error')
        return redirect(url_for('doctor.dashboard'))

@doctor_bp.route('/start-treatment/<int:visit_id>', methods=['POST'])
@login_required
def start_treatment(visit_id):
    """بدء علاج المريض"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # تحديث حالة الزيارة
        visit.status = 'IN_PROGRESS'
        visit.treatment_started_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('تم بدء العلاج بنجاح', 'success')
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))
    except Exception as e:
        logging.error(f"Error starting treatment: {str(e)}")
        flash('حدث خطأ في بدء العلاج', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/patient-details/<int:visit_id>')
@login_required
def patient_details(visit_id):
    """تفاصيل المريض والزيارة للطبيب"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب السجل الطبي للمريض
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == visit.patient_id
        ).order_by(desc(MedicalRecord.created_at)).limit(10).all()
        
        # جلب الوصفات السابقة
        previous_prescriptions = Prescription.query.filter(
            Prescription.patient_id == visit.patient_id
        ).order_by(desc(Prescription.created_at)).limit(5).all()
        
        # جلب طلبات المختبر والأشعة
        lab_requests = LabRequest.query.filter(
            LabRequest.visit_id == visit_id
        ).all()
        
        radiology_requests = RadiologyRequest.query.filter(
            RadiologyRequest.visit_id == visit_id
        ).all()
        
        return render_template('doctor/patient_details.html',
                             visit=visit,
                             medical_records=medical_records,
                             previous_prescriptions=previous_prescriptions,
                             lab_requests=lab_requests,
                             radiology_requests=radiology_requests)
    except Exception as e:
        logging.error(f"Error loading patient details: {str(e)}")
        flash('حدث خطأ في تحميل تفاصيل المريض', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/diagnosis/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def diagnosis(visit_id):
    """إدخال التشخيص"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        if request.method == 'POST':
            # البيانات الأساسية
            chief_complaint = request.form.get('chief_complaint')
            symptoms = request.form.get('symptoms')
            diagnosis = request.form.get('diagnosis')
            differential_diagnosis = request.form.get('differential_diagnosis')
            treatment_plan = request.form.get('treatment_plan')
            follow_up_notes = request.form.get('follow_up_notes')
            
            # الفحص السريري
            vital_signs = {
                'blood_pressure': request.form.get('blood_pressure'),
                'heart_rate': request.form.get('heart_rate'),
                'temperature': request.form.get('temperature'),
                'respiratory_rate': request.form.get('respiratory_rate')
            }
            
            # تحديث الزيارة
            visit.chief_complaint = chief_complaint
            visit.symptoms = symptoms
            visit.diagnosis = diagnosis
            visit.differential_diagnosis = differential_diagnosis
            visit.treatment_plan = treatment_plan
            visit.follow_up_notes = follow_up_notes
            visit.vital_signs = str(vital_signs)
            visit.status = 'IN_PROGRESS'
            visit.diagnosis_date = datetime.utcnow()
            
            # إنشاء سجل طبي
            medical_record = MedicalRecord(
                patient_id=visit.patient_id,
                visit_id=visit_id,
                record_type='DIAGNOSIS',
                title='تشخيص طبي',
                content=f"الشكوى الرئيسية: {chief_complaint}\nالأعراض: {symptoms}\nالتشخيص: {diagnosis}",
                created_by=current_user.id
            )
            
            db.session.add(medical_record)
            db.session.commit()
            
            flash('تم حفظ التشخيص بنجاح', 'success')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        
        return render_template('doctor/diagnosis.html', visit=visit)
    except Exception as e:
        logging.error(f"Error in diagnosis: {str(e)}")
        flash('حدث خطأ في حفظ التشخيص', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/prescription/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def prescription(visit_id):
    """كتابة الوصفة الطبية"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        if request.method == 'POST':
            medication_name = request.form.get('medication_name')
            dosage = request.form.get('dosage')
            frequency = request.form.get('frequency')
            duration = request.form.get('duration')
            instructions = request.form.get('instructions')
            
            # إنشاء الوصفة
            prescription = Prescription(
                visit_id=visit_id,
                patient_id=visit.patient_id,
                medication_name=medication_name,
                dosage=dosage,
                frequency=frequency,
                duration=duration,
                instructions=instructions,
                prescribed_by=current_user.id
            )
            
            db.session.add(prescription)
            db.session.commit()
            
            flash('تم حفظ الوصفة بنجاح', 'success')
            return redirect(url_for('doctor.view_patient', visit_id=visit_id))
        
        return render_template('doctor/prescription.html', visit=visit)
    except Exception as e:
        logging.error(f"Error in prescription: {str(e)}")
        flash('حدث خطأ في حفظ الوصفة', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/lab-request/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def lab_request(visit_id):
    """طلب فحص مختبر"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        if request.method == 'POST':
            test_name = request.form.get('test_name')
            test_description = request.form.get('test_description')
            urgency = request.form.get('urgency', 'normal')
            notes = request.form.get('notes')
            
            # إنشاء طلب المختبر
            lab_request = LabRequest(
                visit_id=visit_id,
                patient_id=visit.patient_id,
                test_name=test_name,
                test_description=test_description,
                urgency=urgency,
                notes=notes,
                requested_by=current_user.id
            )
            
            db.session.add(lab_request)
            db.session.commit()
            
            flash('تم حفظ طلب المختبر بنجاح', 'success')
            return redirect(url_for('doctor.view_patient', visit_id=visit_id))
        
        return render_template('doctor/lab_requests.html', visit=visit, mode='create')
    except Exception as e:
        logging.error(f"Error in lab request: {str(e)}")
        flash('حدث خطأ في حفظ طلب المختبر', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/radiology-request/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def radiology_request(visit_id):
    """طلب فحص أشعة"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        if request.method == 'POST':
            test_name = request.form.get('test_name')
            test_description = request.form.get('test_description')
            urgency = request.form.get('urgency', 'normal')
            notes = request.form.get('notes')
            
            # إنشاء طلب الأشعة
            radiology_request = RadiologyRequest(
                visit_id=visit_id,
                patient_id=visit.patient_id,
                test_name=test_name,
                test_description=test_description,
                urgency=urgency,
                notes=notes,
                requested_by=current_user.id
            )
            
            db.session.add(radiology_request)
            db.session.commit()
            
            flash('تم حفظ طلب الأشعة بنجاح', 'success')
            return redirect(url_for('doctor.view_patient', visit_id=visit_id))
        
        return render_template('doctor/radiology_requests.html', visit=visit, mode='create')
    except Exception as e:
        logging.error(f"Error in radiology request: {str(e)}")
        flash('حدث خطأ في حفظ طلب الأشعة', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/visit-summary/<int:visit_id>')
@login_required
def visit_summary(visit_id):
    """ملخص الزيارة"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        return render_template('doctor/visit_summary.html', visit=visit)
    except Exception as e:
        logging.error(f"Error in visit summary: {str(e)}")
        flash('حدث خطأ في عرض ملخص الزيارة', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/notes/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def notes(visit_id):
    """كتابة الملاحظات الطبية"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        if request.method == 'POST':
            medical_notes = request.form.get('medical_notes')
            if medical_notes:
                # إضافة الملاحظات الطبية
                if not visit.notes:
                    visit.notes = ""
                visit.notes += f"\n[ملاحظات طبية] - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} - الطبيب: {current_user.full_name}\n{medical_notes}"
                db.session.commit()
                flash('تم حفظ الملاحظات الطبية بنجاح', 'success')
                return redirect(url_for('doctor.patient_queue'))
        
        return render_template('doctor/notes.html', visit=visit)
    except Exception as e:
        logging.error(f"Error in notes: {str(e)}")
        flash('حدث خطأ في حفظ الملاحظات', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/end-treatment/<int:visit_id>', methods=['POST'])
@login_required
def end_treatment(visit_id):
    """إنهاء العلاج"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # تحديث حالة الزيارة
        visit.status = 'READY_FOR_ARCHIVE'
        visit.completed_at = datetime.utcnow()
        visit.completed_by = current_user.id
        
        # إنشاء سجل طبي لإنهاء العلاج
        medical_record = MedicalRecord(
            patient_id=visit.patient_id,
            visit_id=visit_id,
            record_type='TREATMENT_COMPLETED',
            title='إنهاء العلاج',
            content=f"تم إنهاء العلاج بنجاح من قبل الطبيب: {current_user.full_name}",
            created_by=current_user.id
        )
        
        db.session.add(medical_record)
        db.session.commit()
        
        flash('تم إنهاء العلاج بنجاح', 'success')
        return redirect(url_for('doctor.patient_queue'))
    except Exception as e:
        logging.error(f"Error ending treatment: {str(e)}")
        flash('حدث خطأ في إنهاء العلاج', 'error')
        return redirect(url_for('doctor.patient_queue'))

# مسارات إضافية للطبيب الاحترافي

@doctor_bp.route('/medical-history/<int:patient_id>')
@login_required
def medical_history(patient_id):
    """السجل الطبي للمريض"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب السجل الطبي الكامل
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == patient_id
        ).order_by(desc(MedicalRecord.created_at)).all()
        
        # جلب الزيارات السابقة
        previous_visits = Visit.query.filter(
            Visit.patient_id == patient_id,
            Visit.status == 'READY_FOR_ARCHIVE'
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
def prescriptions_history(patient_id):
    """تاريخ الوصفات الطبية للمريض"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = Patient.query.get(patient_id)
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

@doctor_bp.route('/lab-results/<int:patient_id>')
@login_required
def lab_results(patient_id):
    """نتائج المختبر للمريض"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب نتائج المختبر
        lab_requests = LabRequest.query.filter(
            LabRequest.patient_id == patient_id
        ).order_by(desc(LabRequest.created_at)).all()
        
        return render_template('doctor/lab_results.html',
                             patient=patient,
                             lab_requests=lab_requests)
    except Exception as e:
        logging.error(f"Error loading lab results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج المختبر', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/radiology-results/<int:patient_id>')
@login_required
def radiology_results(patient_id):
    """نتائج الأشعة للمريض"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب نتائج الأشعة
        radiology_requests = RadiologyRequest.query.filter(
            RadiologyRequest.patient_id == patient_id
        ).order_by(desc(RadiologyRequest.created_at)).all()
        
        return render_template('doctor/radiology_results.html',
                             patient=patient,
                             radiology_requests=radiology_requests)
    except Exception as e:
        logging.error(f"Error loading radiology results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج الأشعة', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/print-prescription/<int:prescription_id>')
@login_required
def print_prescription(prescription_id):
    """طباعة الوصفة الطبية"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            flash('الوصفة غير موجودة', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        return render_template('doctor/print_prescription.html',
                             prescription=prescription)
    except Exception as e:
        logging.error(f"Error printing prescription: {str(e)}")
        flash('حدث خطأ في طباعة الوصفة', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/print-medical-report/<int:visit_id>')
@login_required
def print_medical_report(visit_id):
    """طباعة التقرير الطبي"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        visit = Visit.query.get(visit_id)
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

def get_ai_diagnostic_assistant():
    """مساعد التشخيص بالذكاء الاصطناعي"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.prescription import Prescription
        from datetime import datetime, timedelta
        
        # تحليل التشخيصات الشائعة
        common_diagnoses = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('count')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            MedicalRecord.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(MedicalRecord.diagnosis).order_by(func.count(MedicalRecord.id).desc()).limit(5).all()
        
        # تحليل الأدوية الموصوفة
        common_medications = db.session.query(
            Prescription.medication_name,
            func.count(Prescription.id).label('count')
        ).join(Visit, Prescription.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(Prescription.medication_name).order_by(func.count(Prescription.id).desc()).limit(5).all()
        
        # اقتراحات التشخيص
        diagnostic_suggestions = []
        
        # تحليل الأعراض الشائعة
        if common_diagnoses:
            top_diagnosis = common_diagnoses[0]
            diagnostic_suggestions.append({
                'type': 'common_diagnosis',
                'title': 'التشخيص الأكثر شيوعاً',
                'diagnosis': top_diagnosis.diagnosis,
                'frequency': top_diagnosis.count,
                'suggestion': f'هذا التشخيص شائع في ممارستك ({top_diagnosis.count} مرة)'
            })
        
        # تحليل الأدوية
        if common_medications:
            top_medication = common_medications[0]
            diagnostic_suggestions.append({
                'type': 'common_medication',
                'title': 'الدواء الأكثر وصفاً',
                'medication': top_medication.medication_name,
                'frequency': top_medication.count,
                'suggestion': f'هذا الدواء شائع في وصفاتك ({top_medication.count} مرة)'
            })
        
        return {
            'common_diagnoses': [{'diagnosis': d.diagnosis, 'count': d.count} for d in common_diagnoses],
            'common_medications': [{'medication': m.medication_name, 'count': m.count} for m in common_medications],
            'diagnostic_suggestions': diagnostic_suggestions
        }
    except Exception as e:
        logging.error(f"Error getting AI diagnostic assistant: {str(e)}")
        return {}

def get_patient_medical_history_ai():
    """ذكاء اصطناعي لتاريخ المريض الطبي"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.prescription import Prescription
        from models.patient import Patient
        from datetime import datetime, timedelta
        
        # تحليل المرضى المتكررين
        frequent_patients = db.session.query(
            Visit.patient_id,
            func.count(Visit.id).label('visit_count'),
            func.max(Visit.visit_date).label('last_visit')
        ).filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date >= datetime.now().date() - timedelta(days=90)
        ).group_by(Visit.patient_id).having(func.count(Visit.id) > 2).all()
        
        # تحليل الحالات المزمنة
        chronic_conditions = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('frequency')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            MedicalRecord.diagnosis.in_(['السكري', 'الضغط', 'القلب', 'الربو', 'السرطان'])
        ).group_by(MedicalRecord.diagnosis).all()
        
        # تحليل الأدوية طويلة المدى
        long_term_medications = db.session.query(
            Prescription.medication_name,
            func.count(Prescription.id).label('frequency')
        ).join(Visit, Prescription.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=90)
        ).group_by(Prescription.medication_name).having(func.count(Prescription.id) > 3).all()
        
        return {
            'frequent_patients': [
                {
                    'patient_id': p.patient_id,
                    'visit_count': p.visit_count,
                    'last_visit': p.last_visit.strftime('%Y-%m-%d') if p.last_visit else None
                } for p in frequent_patients
            ],
            'chronic_conditions': [{'condition': c.diagnosis, 'frequency': c.frequency} for c in chronic_conditions],
            'long_term_medications': [{'medication': m.medication_name, 'frequency': m.frequency} for m in long_term_medications]
        }
    except Exception as e:
        logging.error(f"Error getting patient medical history AI: {str(e)}")
        return {}

def get_treatment_recommendations():
    """توصيات العلاج الذكية"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.prescription import Prescription
        from datetime import datetime, timedelta
        
        recommendations = []
        
        # تحليل نجاح العلاجات
        successful_treatments = db.session.query(
            MedicalRecord.diagnosis,
            Prescription.medication_name,
            func.count(MedicalRecord.id).label('success_count')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).join(
            Prescription, Visit.id == Prescription.visit_id
        ).filter(
            Visit.doctor_id == current_user.id,
            Visit.status == 'ARCHIVED',
            MedicalRecord.created_at >= datetime.now() - timedelta(days=60)
        ).group_by(MedicalRecord.diagnosis, Prescription.medication_name).all()
        
        # تحليل العلاجات الفعالة
        if successful_treatments:
            top_treatment = max(successful_treatments, key=lambda x: x.success_count)
            recommendations.append({
                'type': 'effective_treatment',
                'title': 'علاج فعال',
                'diagnosis': top_treatment.diagnosis,
                'medication': top_treatment.medication_name,
                'success_rate': top_treatment.success_count,
                'suggestion': f'هذا العلاج فعال للتشخيص: {top_treatment.diagnosis}'
            })
        
        # تحليل الأدوية المتفاعلة
        drug_interactions = check_drug_interactions()
        if drug_interactions:
            recommendations.append({
                'type': 'drug_interaction',
                'title': 'تفاعل دوائي',
                'interactions': drug_interactions,
                'suggestion': 'تحقق من التفاعلات الدوائية قبل الوصف'
            })
        
        return recommendations
    except Exception as e:
        logging.error(f"Error getting treatment recommendations: {str(e)}")
        return []

def get_drug_interaction_checker():
    """فحص التفاعلات الدوائية"""
    try:
        from models.prescription import Prescription
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        # قائمة التفاعلات المعروفة (مبسطة)
        known_interactions = {
            'وارفارين': ['أسبرين', 'إيبوبروفين'],
            'ديجوكسين': ['فوروسيميد', 'سبيرونولاكتون'],
            'ميثوتريكسات': ['فوليك أسيد', 'تريميثوبريم']
        }
        
        # فحص الوصفات الحديثة
        recent_prescriptions = Prescription.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        interactions_found = []
        
        for prescription in recent_prescriptions:
            medication = prescription.medication_name
            if medication in known_interactions:
                for other_med in known_interactions[medication]:
                    # فحص إذا كان المريض يتناول الدواء الآخر
                    other_prescription = Prescription.query.join(Visit).filter(
                        Visit.patient_id == prescription.visit.patient_id,
                        Prescription.medication_name == other_med,
                        Prescription.created_at >= datetime.now() - timedelta(days=30)
                    ).first()
                    
                    if other_prescription:
                        interactions_found.append({
                            'medication1': medication,
                            'medication2': other_med,
                            'severity': 'متوسط',
                            'description': f'تفاعل محتمل بين {medication} و {other_med}'
                        })
        
        return {
            'interactions_found': interactions_found,
            'total_prescriptions_checked': len(recent_prescriptions),
            'interaction_rate': len(interactions_found) / len(recent_prescriptions) * 100 if recent_prescriptions else 0
        }
    except Exception as e:
        logging.error(f"Error getting drug interaction checker: {str(e)}")
        return {}

def get_clinical_decision_support():
    """دعم القرارات السريرية"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.prescription import Prescription
        from datetime import datetime, timedelta
        
        support_recommendations = []
        
        # تحليل معدل نجاح التشخيصات
        diagnosis_success = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('total_cases'),
            func.sum(case([(Visit.status == 'ARCHIVED', 1)], else_=0)).label('successful_cases')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            MedicalRecord.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(MedicalRecord.diagnosis).all()
        
        for diagnosis in diagnosis_success:
            success_rate = (diagnosis.successful_cases / diagnosis.total_cases * 100) if diagnosis.total_cases > 0 else 0
            if success_rate < 70:
                support_recommendations.append({
                    'type': 'diagnosis_improvement',
                    'title': 'تحسين التشخيص',
                    'diagnosis': diagnosis.diagnosis,
                    'success_rate': round(success_rate, 2),
                    'suggestion': f'معدل نجاح التشخيص {diagnosis.diagnosis} منخفض - يحتاج مراجعة'
                })
        
        # تحليل فعالية الأدوية
        medication_effectiveness = db.session.query(
            Prescription.medication_name,
            func.count(Prescription.id).label('total_prescriptions'),
            func.sum(case([(Visit.status == 'ARCHIVED', 1)], else_=0)).label('successful_treatments')
        ).join(Visit, Prescription.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(Prescription.medication_name).all()
        
        for medication in medication_effectiveness:
            effectiveness_rate = (medication.successful_treatments / medication.total_prescriptions * 100) if medication.total_prescriptions > 0 else 0
            if effectiveness_rate < 60:
                support_recommendations.append({
                    'type': 'medication_effectiveness',
                    'title': 'فعالية الدواء',
                    'medication': medication.medication_name,
                    'effectiveness_rate': round(effectiveness_rate, 2),
                    'suggestion': f'فعالية الدواء {medication.medication_name} منخفضة - يحتاج مراجعة'
                })
        
        return support_recommendations
    except Exception as e:
        logging.error(f"Error getting clinical decision support: {str(e)}")
        return []

def get_medical_analytics():
    """التحليلات الطبية"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.prescription import Prescription
        from datetime import datetime, timedelta
        
        # تحليل الأداء الطبي
        total_visits = Visit.query.filter(Visit.doctor_id == current_user.id).count()
        completed_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status == 'ARCHIVED'
        ).count()
        
        completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
        
        # تحليل متوسط مدة الزيارة
        avg_visit_duration = db.session.query(func.avg(Visit.duration)).filter(
            Visit.doctor_id == current_user.id
        ).scalar() or 0
        
        # تحليل التشخيصات
        diagnosis_distribution = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('count')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            MedicalRecord.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(MedicalRecord.diagnosis).all()
        
        # تحليل الأدوية
        medication_distribution = db.session.query(
            Prescription.medication_name,
            func.count(Prescription.id).label('count')
        ).join(Visit, Prescription.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(Prescription.medication_name).all()
        
        return {
            'completion_rate': round(completion_rate, 2),
            'avg_visit_duration': round(avg_visit_duration, 2),
            'diagnosis_distribution': [{'diagnosis': d.diagnosis, 'count': d.count} for d in diagnosis_distribution],
            'medication_distribution': [{'medication': m.medication_name, 'count': m.count} for m in medication_distribution],
            'performance_score': calculate_medical_performance_score(completion_rate, avg_visit_duration)
        }
    except Exception as e:
        logging.error(f"Error getting medical analytics: {str(e)}")
        return {}

def get_workflow_optimization():
    """تحسين سير العمل"""
    try:
        from models.visit import Visit
        from models.appointment import Appointment
        from datetime import datetime, timedelta
        
        optimizations = []
        
        # تحليل أوقات الذروة
        peak_hours = db.session.query(
            func.strftime('%H', Visit.visit_time).label('hour'),
            func.count(Visit.id).label('count')
        ).filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date >= datetime.now().date() - timedelta(days=30)
        ).group_by(func.strftime('%H', Visit.visit_time)).all()
        
        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 10:
                optimizations.append({
                    'type': 'peak_hours',
                    'title': 'ساعات الذروة',
                    'description': f'الساعة {max_hour.hour}:00 هي الأكثر ازدحاماً ({max_hour.count} زيارة)',
                    'suggestion': 'توزيع المواعيد على ساعات أخرى'
                })
        
        # تحليل المواعيد
        today = datetime.now().date()
        tomorrow_appointments = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            Appointment.appointment_date == today + timedelta(days=1)
        ).count()
        
        if tomorrow_appointments > 15:
            optimizations.append({
                'type': 'appointment_load',
                'title': 'عبء المواعيد',
                'description': f'لديك {tomorrow_appointments} موعد غداً',
                'suggestion': 'مراجعة توزيع المواعيد'
            })
        
        # تحليل الكفاءة
        avg_duration = db.session.query(func.avg(Visit.duration)).filter(
            Visit.doctor_id == current_user.id
        ).scalar() or 0
        
        if avg_duration > 45:
            optimizations.append({
                'type': 'efficiency',
                'title': 'تحسين الكفاءة',
                'description': f'متوسط مدة الزيارة: {avg_duration:.1f} دقيقة',
                'suggestion': 'تحسين العمليات لتقليل مدة الزيارة'
            })
        
        return optimizations
    except Exception as e:
        logging.error(f"Error getting workflow optimization: {str(e)}")
        return []

def get_smart_reminders():
    """التذكيرات الذكية"""
    try:
        from models.visit import Visit
        from models.appointment import Appointment
        from models.prescription import Prescription
        from datetime import datetime, timedelta
        
        reminders = []
        
        # تذكيرات المواعيد
        today = datetime.now().date()
        tomorrow_appointments = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            Appointment.appointment_date == today + timedelta(days=1)
        ).count()
        
        if tomorrow_appointments > 0:
            reminders.append({
                'type': 'appointments',
                'title': 'مواعيد غداً',
                'message': f'لديك {tomorrow_appointments} موعد غداً',
                'priority': 'medium'
            })
        
        # تذكيرات المتابعة
        follow_up_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status == 'ARCHIVED',
            Visit.completed_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        if follow_up_visits > 5:
            reminders.append({
                'type': 'follow_up',
                'title': 'متابعة المرضى',
                'message': f'تم إنجاز {follow_up_visits} زيارة هذا الأسبوع - يحتاج متابعة',
                'priority': 'low'
            })
        
        # تذكيرات الأدوية
        recent_prescriptions = Prescription.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=3)
        ).count()
        
        if recent_prescriptions > 10:
            reminders.append({
                'type': 'medications',
                'title': 'مراجعة الأدوية',
                'message': f'تم وصف {recent_prescriptions} دواء في آخر 3 أيام',
                'priority': 'low'
            })
        
        return reminders
    except Exception as e:
        logging.error(f"Error getting smart reminders: {str(e)}")
        return []

# دوال مساعدة
def check_drug_interactions():
    """فحص التفاعلات الدوائية"""
    # قائمة مبسطة للتفاعلات المعروفة
    interactions = [
        {'drug1': 'وارفارين', 'drug2': 'أسبرين', 'severity': 'عالي'},
        {'drug1': 'ديجوكسين', 'drug2': 'فوروسيميد', 'severity': 'متوسط'},
        {'drug1': 'ميثوتريكسات', 'drug2': 'تريميثوبريم', 'severity': 'عالي'}
    ]
    return interactions

def calculate_medical_performance_score(completion_rate, avg_duration):
    """حساب نقاط الأداء الطبي"""
    # نقاط الإنجاز
    completion_score = completion_rate
    
    # نقاط الكفاءة (كلما قل الوقت كلما زادت النقاط)
    efficiency_score = max(0, 100 - (avg_duration / 60 * 20))
    
    return (completion_score + efficiency_score) / 2

@doctor_bp.route('/patients')
@login_required
def patients():
    """قائمة المرضى"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('doctor/patient_queue.html')

@doctor_bp.route('/lab-requests')
@login_required
def lab_requests():
    """طلبات المختبر"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('doctor/lab_requests.html')

@doctor_bp.route('/radiology-requests')
@login_required
def radiology_requests():
    """طلبات الأشعة"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('doctor/radiology_requests.html')

@doctor_bp.route('/visits')
@login_required
def visits():
    """قائمة الزيارات"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('doctor/visit_summary.html')

@doctor_bp.route('/medical-records')
@login_required
def medical_records():
    """السجلات الطبية"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('doctor/patient_details.html')

@doctor_bp.route('/prescriptions')
@login_required
def prescriptions():
    """الوصفات الطبية"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('doctor/prescriptions.html')

@doctor_bp.route('/appointments')
@login_required
def appointments():
    """المواعيد"""
    if current_user.role not in ['doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        from models.appointment import Appointment
        
        # جلب مواعيد الطبيب
        appointments = Appointment.query.filter_by(doctor_id=current_user.id).order_by(Appointment.appointment_date.desc()).all()
        
        return render_template('doctor/appointments.html', appointments=appointments)
    except Exception as e:
        logging.error(f"Error loading appointments: {str(e)}")
        flash('حدث خطأ في تحميل المواعيد', 'error')
        return redirect(url_for('doctor.dashboard'))