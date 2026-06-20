"""Patient management routes - extracted from monolithic reception.py"""

# Import blueprint (absolute import avoids parent package requirement)
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
# PATIENT ROUTES
# ═══════════════════════════════════════

@reception_bp.route('/patients')
@login_required
@role_required('reception', 'super_admin', 'manager')
def patients():
    """قائمة المرضى - الوحدة المركزية"""
    def _normalize_phone(v):
        if not v:
            return None
        s = ''.join([ch for ch in str(v).strip() if ch not in {' ', '-', '(', ')', '.'}])
        if not s:
            return None
        if s.startswith('+'):
            digits = ''.join([c for c in s[1:] if c.isdigit()])
            return ('+' + digits) if digits else None
        digits = ''.join([c for c in s if c.isdigit()])
        return digits if digits else None

    def _normalize_national_id(v):
        if not v:
            return None
        s = ''.join([c for c in str(v).strip() if c.isdigit()])
        return s if s else None

    # البحث والفلترة
    search = request.args.get('search', '')
    department_id = request.args.get('department_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    query = Patient.query
    
    if search:
        search_norm_phone = _normalize_phone(search)
        search_norm_nid = _normalize_national_id(search)
        conditions = [
            Patient.first_name.ilike(f'%{search}%'),
            Patient.last_name.ilike(f'%{search}%'),
            Patient.phone.ilike(f'%{search}%'),
            Patient.national_id.ilike(f'%{search}%')
        ]
        if search_norm_phone:
            conditions.append(Patient.phone == search_norm_phone)
        if search_norm_nid:
            conditions.append(Patient.national_id == search_norm_nid)
        if search.isdigit():
            try:
                conditions.append(Patient.id == int(search))
            except Exception:

                logging.warning(f"Error in {__name__}: {e}")
        query = query.filter(db.or_(*conditions))
    
    if department_id:
        query = query.join(Visit, Visit.patient_id == Patient.id).filter(Visit.department_id == department_id).distinct()
    
    total = query.count()
    pages = (total + per_page - 1) // per_page
    
    patients = query.offset((page - 1) * per_page).limit(per_page).all()
    departments = Department.query.all()
    from models.insurance import InsuranceCompany
    insurance_companies = InsuranceCompany.query.filter_by(is_active=True).order_by(InsuranceCompany.name.asc()).all()
    
    return render_template('reception/patients.html', 
                         patients=patients, 
                         departments=departments,
                         insurance_companies=insurance_companies,
                         search=search,
                         selected_department=department_id,
                         page=page, pages=pages, total=total)

@reception_bp.route('/add_patient', methods=['GET', 'POST'])
@login_required
@role_required('reception')
def add_patient():
    """إضافة مريض جديد - الوحدة المركزية"""
    
    
    if request.method == 'POST':
        try:
            # حقول أساسية
            national_id_raw = (request.form.get('national_id') or '').strip() or None
            phone_raw = (request.form.get('phone') or '').strip() or None
            first_name = (request.form.get('first_name') or '').strip()
            last_name = (request.form.get('last_name') or '').strip()
            first_name_ar = (request.form.get('first_name_ar') or '').strip() or None
            last_name_ar = (request.form.get('last_name_ar') or '').strip() or None
            gender = request.form.get('gender') or None
            address = (request.form.get('address') or '').strip() or None
            notes = (request.form.get('notes') or '').strip() or None
            admin_notes = (request.form.get('admin_notes') or '').strip() or None
            insurance_company_id = request.form.get('insurance_company_id')
            insurance_company_id = int(insurance_company_id) if insurance_company_id and str(insurance_company_id).isdigit() else None
            insurance_member_number = (request.form.get('insurance_member_number') or '').strip() or None
            marital_status = (request.form.get('marital_status') or '').strip() or None
            is_pregnant = str(request.form.get('is_pregnant') or '').lower() in ['true', 'on', '1', 'yes']
            pregnancy_weeks_raw = request.form.get('pregnancy_weeks')
            pregnancy_weeks = int(pregnancy_weeks_raw) if pregnancy_weeks_raw and pregnancy_weeks_raw.isdigit() else None
            last_menstruation_date_raw = request.form.get('last_menstruation_date')
            last_menstruation_date = None
            if last_menstruation_date_raw:
                try:
                    from datetime import datetime
                    last_menstruation_date = datetime.strptime(last_menstruation_date_raw, '%Y-%m-%d').date()
                except Exception:
                    last_menstruation_date = None
            pregnancy_notes = (request.form.get('pregnancy_notes') or '').strip() or None

            def _normalize_phone(v):
                if not v:
                    return None
                s = ''.join([ch for ch in str(v).strip() if ch not in {' ', '-', '(', ')', '.'}])
                if not s:
                    return None
                if s.startswith('+'):
                    digits = ''.join([c for c in s[1:] if c.isdigit()])
                    return ('+' + digits) if digits else None
                digits = ''.join([c for c in s if c.isdigit()])
                return digits if digits else None

            def _normalize_national_id(v):
                if not v:
                    return None
                s = ''.join([c for c in str(v).strip() if c.isdigit()])
                return s if s else None

            def _validate_phone(v):
                if not v:
                    return False
                vv = v[1:] if v.startswith('+') else v
                return vv.isdigit() and (7 <= len(vv) <= 20)

            def _validate_national_id(v):
                if not v:
                    return True
                return v.isdigit() and (6 <= len(v) <= 32)

            phone = _normalize_phone(phone_raw)
            national_id = _normalize_national_id(national_id_raw)
            if not _validate_phone(phone):
                message = 'رقم الهاتف غير صالح'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)
            if not _validate_national_id(national_id):
                message = 'رقم الهوية غير صالح'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)

            # تحقق الحقول المطلوبة
            if not first_name or not last_name or not phone:
                message = 'يرجى ملء الاسم الأول واسم العائلة ورقم الهاتف'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)

            # منع التكرار: رقم الهوية
            if national_id:
                existing_by_id = Patient.query.filter_by(national_id=national_id).first()
                if existing_by_id:
                    message = f"المريض موجود مسبقاً برقم الهوية {national_id}"
                    if _wants_json():
                        return jsonify({'success': False, 'message': message, 'patient_id': existing_by_id.id}), 409
                    flash(message, 'warning')
                    raise ValueError(message)

            # منع التكرار: رقم الهاتف (تحذير قوي)
            if phone:
                existing_by_phone = Patient.query.filter(Patient.phone == phone).first()
                if existing_by_phone:
                    message = f"يوجد مريض بنفس رقم الهاتف ({phone})"
                    if _wants_json():
                        return jsonify({'success': False, 'message': message, 'patient_id': existing_by_phone.id}), 409
                    flash(message, 'warning')
                    raise ValueError(message)

            # تحويل تاريخ الميلاد
            birth_date_raw = request.form.get('birth_date')
            birth_date = None
            if birth_date_raw:
                try:
                    from datetime import datetime
                    birth_date = datetime.strptime(birth_date_raw, '%Y-%m-%d').date()
                except Exception:
                    birth_date = None

            patient = Patient(
                national_id=national_id,
                first_name=first_name,
                last_name=last_name,
                first_name_ar=first_name_ar,
                last_name_ar=last_name_ar,
                phone=phone,
                birth_date=birth_date,
                gender=gender,
                address=address,
                notes=notes,
                admin_notes=admin_notes,
                insurance_company_id=insurance_company_id,
                insurance_member_number=insurance_member_number,
                marital_status=marital_status,
                is_pregnant=is_pregnant,
                pregnancy_weeks=pregnancy_weeks,
                last_menstruation_date=last_menstruation_date,
                pregnancy_notes=pregnancy_notes
            )
            
            db.session.add(patient)
            db.session.commit()
            
            if _wants_json():
                return jsonify({'success': True, 'patient_id': patient.id})
            flash('تم إضافة المريض بنجاح.', 'success')
            return redirect(url_for('reception.patients'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding patient: {str(e)}")
            if _wants_json():
                return jsonify({'success': False, 'message': 'تعذر إضافة المريض، يرجى التحقق من البيانات والمحاولة مرة أخرى'}), 400
            flash('تعذر إضافة المريض، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
    
    # في طلبات GET نعيد التوجيه إلى قائمة المرضى مع فتح نموذج الإضافة داخل نفس القالب
    return redirect(url_for('reception.patients', show_add=1))

@reception_bp.route('/view_patient/<int:patient_id>')
@login_required
def view_patient(patient_id):
    """عرض تفاصيل المريض - الوحدة المركزية"""
    allowed_roles = ['reception', 'manager']
    if current_user.role not in allowed_roles:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('reception.queue_management'))
    
    # تقييد الوصول حسب الدور للمختبر والأشعة
    try:
        if current_user.role in ['lab', 'radiology']:
            from services.access_control_service import AccessControlService
            accessible_patients = AccessControlService.get_user_accessible_patients(current_user.id)
            if not any(p.id == patient_id for p in accessible_patients):
                flash('لا تملك صلاحية عرض هذا المريض', 'warning')
                return redirect(url_for('main.dashboard'))
    except Exception as e:
        logging.warning(f"Access check failed in view_patient: {str(e)}")
    
    visits = Visit.query.filter_by(patient_id=patient_id).order_by(Visit.created_at.desc()).limit(10).all()
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.starts_at.desc()).limit(10).all()
    
    # جلب طلبات المختبر والأشعة
    from models.lab_request import LabRequest
    from models.radiology_request import RadiologyRequest
    
    lab_requests = LabRequest.query.filter_by(patient_id=patient_id).order_by(LabRequest.created_at.desc()).limit(10).all()
    radiology_requests = RadiologyRequest.query.filter_by(patient_id=patient_id).order_by(RadiologyRequest.created_at.desc()).limit(10).all()
    
    template = 'reception/view_patient.html'
    
    return render_template(template, 
                         patient=patient, 
                         visits=visits, 
                         appointments=appointments,
                         lab_requests=lab_requests,
                         radiology_requests=radiology_requests)

@reception_bp.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
@login_required
@can_modify_patient_data
def edit_patient(patient_id):
    """تعديل بيانات المريض - الوحدة المركزية"""
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('reception.queue_management'))
    
    if request.method == 'POST':
        try:
            national_id_raw = (request.form.get('national_id') or '').strip() or None
            phone_raw = (request.form.get('phone') or '').strip() or None
            first_name = (request.form.get('first_name') or '').strip()
            last_name = (request.form.get('last_name') or '').strip()
            first_name_ar = (request.form.get('first_name_ar') or '').strip() or None
            last_name_ar = (request.form.get('last_name_ar') or '').strip() or None
            gender = request.form.get('gender') or None
            address = (request.form.get('address') or '').strip() or None
            notes = (request.form.get('notes') or '').strip() or None
            admin_notes = (request.form.get('admin_notes') or '').strip() or None
            insurance_company_id = request.form.get('insurance_company_id')
            insurance_company_id = int(insurance_company_id) if insurance_company_id and str(insurance_company_id).isdigit() else None
            insurance_member_number = (request.form.get('insurance_member_number') or '').strip() or None
            marital_status = (request.form.get('marital_status') or '').strip() or None
            is_pregnant = str(request.form.get('is_pregnant') or '').lower() in ['true', 'on', '1', 'yes']
            pregnancy_weeks_raw = request.form.get('pregnancy_weeks')
            pregnancy_weeks = int(pregnancy_weeks_raw) if pregnancy_weeks_raw and pregnancy_weeks_raw.isdigit() else None
            last_menstruation_date_raw = request.form.get('last_menstruation_date')
            last_menstruation_date = None
            if last_menstruation_date_raw:
                try:
                    from datetime import datetime
                    last_menstruation_date = datetime.strptime(last_menstruation_date_raw, '%Y-%m-%d').date()
                except Exception:
                    last_menstruation_date = None
            pregnancy_notes = (request.form.get('pregnancy_notes') or '').strip() or None

            def _normalize_phone(v):
                if not v:
                    return None
                s = ''.join([ch for ch in str(v).strip() if ch not in {' ', '-', '(', ')', '.'}])
                if not s:
                    return None
                if s.startswith('+'):
                    digits = ''.join([c for c in s[1:] if c.isdigit()])
                    return ('+' + digits) if digits else None
                digits = ''.join([c for c in s if c.isdigit()])
                return digits if digits else None

            def _normalize_national_id(v):
                if not v:
                    return None
                s = ''.join([c for c in str(v).strip() if c.isdigit()])
                return s if s else None

            def _validate_phone(v):
                if not v:
                    return False
                vv = v[1:] if v.startswith('+') else v
                return vv.isdigit() and (7 <= len(vv) <= 20)

            def _validate_national_id(v):
                if not v:
                    return True
                return v.isdigit() and (6 <= len(v) <= 32)

            phone = _normalize_phone(phone_raw)
            national_id = _normalize_national_id(national_id_raw)
            if not _validate_phone(phone):
                message = 'رقم الهاتف غير صالح'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)
            if not _validate_national_id(national_id):
                message = 'رقم الهوية غير صالح'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)

            if not first_name or not last_name or not phone:
                message = 'يرجى ملء الاسم الأول واسم العائلة ورقم الهاتف'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)

            if national_id and national_id != (patient.national_id or None):
                existing_by_id = Patient.query.filter_by(national_id=national_id).first()
                if existing_by_id and existing_by_id.id != patient.id:
                    message = f"المريض موجود مسبقاً برقم الهوية {national_id}"
                    if _wants_json():
                        return jsonify({'success': False, 'message': message, 'patient_id': existing_by_id.id}), 409
                    flash(message, 'warning')
                    raise ValueError(message)

            if phone and phone != (patient.phone or None):
                existing_by_phone = Patient.query.filter(Patient.phone == phone, Patient.id != patient.id).first()
                if existing_by_phone:
                    message = f"يوجد مريض بنفس رقم الهاتف ({phone})"
                    if _wants_json():
                        return jsonify({'success': False, 'message': message, 'patient_id': existing_by_phone.id}), 409
                    flash(message, 'warning')
                    raise ValueError(message)

            birth_date_raw = request.form.get('birth_date')
            birth_date = None
            if birth_date_raw:
                try:
                    from datetime import datetime
                    birth_date = datetime.strptime(birth_date_raw, '%Y-%m-%d').date()
                except Exception:
                    birth_date = None

            patient.national_id = national_id
            patient.first_name = first_name
            patient.last_name = last_name
            patient.first_name_ar = first_name_ar
            patient.last_name_ar = last_name_ar
            patient.phone = phone
            patient.birth_date = birth_date
            patient.gender = gender
            patient.address = address
            patient.notes = notes
            patient.admin_notes = admin_notes
            patient.insurance_company_id = insurance_company_id
            patient.insurance_member_number = insurance_member_number
            patient.marital_status = marital_status
            patient.is_pregnant = is_pregnant
            patient.pregnancy_weeks = pregnancy_weeks
            patient.last_menstruation_date = last_menstruation_date
            patient.pregnancy_notes = pregnancy_notes
            
            db.session.commit()
            if _wants_json():
                return jsonify({'success': True, 'patient_id': patient.id})
            flash('تم تحديث بيانات المريض بنجاح.', 'success')
            return redirect(url_for('reception.view_patient', patient_id=patient_id))
            
        except Exception as e:
            db.session.rollback()
            if _wants_json():
                return jsonify({'success': False, 'message': 'تعذر تحديث بيانات المريض، يرجى التحقق من البيانات والمحاولة مرة أخرى'}), 400
            flash('تعذر تحديث بيانات المريض، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
            logging.error(f"Error updating patient: {str(e)}")
    
    patients = Patient.query.order_by(Patient.created_at.desc()).limit(200).all()
    departments = Department.query.all()
    from models.insurance import InsuranceCompany
    insurance_companies = InsuranceCompany.query.filter_by(is_active=True).order_by(InsuranceCompany.name.asc()).all()
    return render_template('reception/patients.html', 
                         patients=patients,
                         patient=patient,
                         departments=departments,
                         insurance_companies=insurance_companies,
                         mode='edit')

@reception_bp.route('/delete_patient/<int:patient_id>', methods=['POST'])
@login_required
@can_delete_patient
def delete_patient(patient_id):
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('reception.patients'))
    try:
        from models.receipt import Receipt
        from models.medication import Prescription
        has_receipts = db.session.query(Receipt.id).filter_by(patient_id=patient_id).first() is not None
        has_prescriptions = db.session.query(Prescription.id).filter_by(patient_id=patient_id).first() is not None
        if has_receipts or has_prescriptions:
            parts = []
            if has_receipts:
                parts.append('سندات قبض')
            if has_prescriptions:
                parts.append('روشتات')
            flash('لا يمكن حذف المريض لوجود ' + ' و '.join(parts) + '. يرجى أرشفة/حذف السجلات المرتبطة أولاً.', 'warning')
            return redirect(url_for('reception.patients'))
        db.session.delete(patient)
        db.session.commit()
        flash('تم حذف المريض بنجاح.', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting patient: {str(e)}")
        flash('حدث خطأ أثناء حذف المريض.', 'error')
    return redirect(url_for('reception.patients'))

@reception_bp.route('/api/smart-patient-search')
@login_required
def api_smart_patient_search():
    """API للبحث الذكي عن المرضى"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'error': 'ليس لديك الصلاحيات'}), 403
    
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify({'patients': []})
    
    try:
        from datetime import datetime
        parsed_date = None
        try:
            if len(search_term) >= 8:
                parsed_date = datetime.strptime(search_term, '%Y-%m-%d').date()
        except Exception:
            parsed_date = None
        filters = [
            Patient.first_name.ilike(f'%{search_term}%'),
            Patient.last_name.ilike(f'%{search_term}%'),
            Patient.national_id.ilike(f'%{search_term}%'),
            Patient.phone.ilike(f'%{search_term}%')
        ]
        query = Patient.query
        if parsed_date:
            query = query.filter(db.or_(*filters, Patient.birth_date == parsed_date))
        else:
            query = query.filter(db.or_(*filters))
        patients = query.order_by(Patient.created_at.desc()).limit(10).all()
        results = []
        for patient in patients:
            results.append({
                'id': patient.id,
                'full_name': patient.full_name,
                'national_id': patient.national_id,
                'phone': patient.phone,
                'birth_date': patient.birth_date.strftime('%Y-%m-%d') if patient.birth_date else None,
                'gender': patient.gender,
                'address': patient.address
            })
        return jsonify({'patients': results})
    except Exception as e:
        logging.error(f"Error in smart patient search: {str(e)}")
        return jsonify({'error': 'حدث خطأ في البحث'}), 500
