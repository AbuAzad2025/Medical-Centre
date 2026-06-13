 

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.patient import Patient
from models.visit import Visit
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.department import Department
from models.payment import Payment
from models.invoice import Invoice
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from services.gatekeeper_service import GatekeeperService
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval, role_required, role_required_json
from app_factory import db
import logging
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP

manager_bp = Blueprint('manager', __name__)

@manager_bp.route('/')
@login_required
def index():
    """توجيه تلقائي إلى لوحة التحكم"""
    return redirect(url_for('manager.dashboard'))

@manager_bp.route('/dashboard')
@login_required
@role_required('manager', 'admin', 'super_admin')
def dashboard():
    """لوحة تحكم المدير"""
    
    
    try:
        # إحصائيات شاملة
        today = date.today()
        this_month = today.replace(day=1)
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        # إحصائيات المرضى
        total_patients = Patient.query.count()
        new_patients_today = Patient.query.filter(
            Patient.created_at >= start_of_day,
            Patient.created_at <= end_of_day
        ).count()
        
        # إحصائيات الزيارات
        total_visits = Visit.query.count()
        visits_today = Visit.query.filter(
            Visit.created_at >= start_of_day,
            Visit.created_at <= end_of_day
        ).count()
        completed_visits_today = Visit.query.filter(
            Visit.status == 'ARCHIVED',
            Visit.completed_at >= datetime.combine(today, datetime.min.time())
        ).count()
        
        # إحصائيات المالية
        today_revenue = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) == today
        ).scalar() or 0
        
        month_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= this_month
        ).scalar() or 0
        
        # إحصائيات المستخدمين
        total_users = User.query.count()
        active_users = User.query.filter(User.is_active == True).count()
        
        # إحصائيات الأقسام
        departments = Department.query.all()

        smart_analytics = get_smart_analytics()
        business_insights = get_business_insights()
        performance_metrics = get_performance_metrics()
        financial_forecasting = get_financial_forecasting()
        bi_insights = get_bi_insights()

        start_30d = datetime.now(timezone.utc) - timedelta(days=30)
        end_now = datetime.now(timezone.utc)

        department_performance = []
        for dept in departments:
            dept_id = getattr(dept, 'id', None)
            if not dept_id:
                continue
            open_count = Visit.query.filter(Visit.department_id == dept_id, Visit.status.in_(['OPEN', 'IN_PROGRESS'])).count()
            done_30d = Visit.query.filter(Visit.department_id == dept_id, Visit.status == 'ARCHIVED', Visit.created_at >= start_30d).count()
            avg_sec = None
            try:
                avg_sec = db.session.query(
                    func.avg(
                        func.extract('epoch', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.extract('epoch', Visit.created_at)
                    )
                ).filter(
                    Visit.department_id == dept_id,
                    Visit.status == 'ARCHIVED',
                    Visit.created_at >= start_30d,
                    func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
                ).scalar()
            except Exception:
                db.session.rollback()
                avg_sec = None
            department_performance.append({
                'department_id': dept_id,
                'department_name': getattr(dept, 'name_ar', None) or getattr(dept, 'name', None) or str(dept_id),
                'open_visits': int(open_count or 0),
                'archived_30d': int(done_30d or 0),
                'avg_minutes_30d': (float(avg_sec or 0) / 60.0) if avg_sec is not None else 0.0
            })
        department_performance.sort(key=lambda x: (x.get('open_visits', 0), x.get('archived_30d', 0)), reverse=True)

        doctor_performance = []
        try:
            rows = db.session.query(
                User.id.label('doctor_id'),
                User.full_name.label('doctor_name'),
                func.count(Visit.id).label('archived_count'),
                func.avg(
                    func.extract('epoch', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.extract('epoch', Visit.created_at)
                ).label('avg_sec')
            ).join(
                Visit, Visit.doctor_id == User.id
            ).filter(
                User.role == 'doctor',
                Visit.status == 'ARCHIVED',
                Visit.created_at >= start_30d
            ).group_by(User.id, User.full_name).order_by(func.count(Visit.id).desc()).limit(10).all()
            for r in rows:
                doctor_performance.append({
                    'doctor_id': int(r.doctor_id),
                    'doctor_name': r.doctor_name,
                    'archived_30d': int(r.archived_count or 0),
                    'avg_minutes_30d': float(r.avg_sec or 0) / 60.0
                })
        except Exception:
            db.session.rollback()
            doctor_performance = []
        
        # موافقات معلّقة (الدفع القسري/الإدخال بدون دفع)
        pending_force_payment_approvals = Visit.query.filter(
            Visit.is_force_payment == True,
            Visit.force_payment_approved_by.is_(None)
        ).count()
        
        stats = {
            'total_patients': total_patients,
            'new_patients_today': new_patients_today,
            'total_visits': total_visits,
            'visits_today': visits_today,
            'completed_visits_today': completed_visits_today,
            'today_revenue': float(today_revenue),
            'month_revenue': float(month_revenue),
            'total_users': total_users,
            'active_users': active_users,
            'departments': departments,
            'pending_force_payment_approvals': pending_force_payment_approvals,
            'smart_analytics': smart_analytics,
            'business_insights': business_insights,
            'performance_metrics': performance_metrics,
            'financial_forecasting': financial_forecasting,
            'bi_insights': bi_insights,
            'department_performance': department_performance,
            'doctor_performance': doctor_performance
        }
        
        return render_template('manager/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in manager dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@manager_bp.route('/monitoring')
@login_required
@role_required('manager', 'admin')
def monitoring():
    """مراقبة النظام"""
    
    
    try:
        # مراقبة الوحدات
        units_status = {
            'reception': {
                'name': 'الاستقبال',
                'status': 'active',
                'pending_visits': Visit.query.filter(
                    Visit.status == 'OPEN'
                ).count()
            },
            'doctor': {
                'name': 'الطبيب',
                'status': 'active',
                'in_progress_visits': Visit.query.filter(
                    Visit.status == 'IN_PROGRESS'
                ).count()
            },
            'emergency': {
                'name': 'الطوارئ',
                'status': 'active',
                'emergency_visits': Visit.query.filter(
                    Visit.visit_type == 'EMERGENCY',
                    Visit.status.in_(['OPEN', 'IN_PROGRESS'])
                ).count()
            },
            'lab': {
                'name': 'المختبر',
                'status': 'active',
                'lab_requests': LabRequest.query.filter(
                    LabRequest.status.in_(['REQUESTED', 'IN_PROGRESS'])
                ).count()
            },
            'radiology': {
                'name': 'الأشعة',
                'status': 'active',
                'radiology_requests': RadiologyRequest.query.filter(
                    RadiologyRequest.status.in_(['REQUESTED', 'IN_PROGRESS'])
                ).count()
            },
            'accountant': {
                'name': 'المحاسب',
                'status': 'active',
                'open_invoices': Invoice.query.filter(
                    Invoice.status.in_(['ISSUED', 'DRAFT'])
                ).count()
            }
        }
        if request.args.get('ajax'):
            return jsonify({'success': True, 'units_status': units_status})
        return render_template('manager/monitoring.html', units_status=units_status)
    except Exception as e:
        logging.error(f"Error in monitoring: {str(e)}")
        flash('حدث خطأ في تحميل مراقبة النظام', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/pricing')
@login_required
@role_required('manager', 'admin', 'super_admin')
def pricing():
    """إدارة الأسعار"""
    
    
    try:
        # جلب خدمات التسعير
        from models.service import ServiceMaster
        from models.department import Department
        
        services = ServiceMaster.query.order_by(ServiceMaster.updated_at.desc()).all()
        departments = Department.query.filter_by(is_active=True).all()
        
        return render_template('manager/pricing.html', services=services, departments=departments)
    except Exception as e:
        logging.error(f"Error loading pricing: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الأسعار', 'error')
        return redirect(url_for('manager.dashboard'))

# --- API Endpoints for Pricing Management ---

@manager_bp.route('/api/pricing/services', methods=['GET'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def get_services_api():
    """API لجلب كافة الخدمات"""
    try:
        from models.service import ServiceMaster
        services = ServiceMaster.query.order_by(ServiceMaster.updated_at.desc()).all()
        return jsonify({
            'success': True,
            'data': [{
                'id': s.id,
                'code': s.code,
                'name': s.name,
                'name_ar': s.name_ar,
                'category': s.category,
                'base_price': float(s.base_price),
                'emergency_price': float(s.emergency_price) if s.emergency_price is not None else None,
                'insurance_price': float(s.insurance_price) if s.insurance_price is not None else None,
                'currency': s.currency,
                'department_id': s.department_id,
                'department_name': s.department.name_ar if s.department else None,
                'duration': s.duration,
                'max_daily': s.max_daily,
                'is_active': s.is_active,
                'description': s.description,
                'updated_at': s.updated_at.strftime('%Y-%m-%d')
            } for s in services]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': 'تعذر جلب البيانات حالياً'}), 500

@manager_bp.route('/api/pricing/services', methods=['POST'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def add_service_api():
    """API لإضافة خدمة جديدة"""
    try:
        from models.service import ServiceMaster
        data = request.get_json()
        
        # Validation
        if not data.get('name') or not data.get('code'):
            return jsonify({'success': False, 'message': 'الاسم وكود الخدمة مطلوبان'}), 400
            
        existing = ServiceMaster.query.filter_by(code=data['code']).first()
        if existing:
            return jsonify({'success': False, 'message': 'كود الخدمة موجود مسبقاً'}), 400

        new_service = ServiceMaster(
            code=data['code'],
            name=data['name'],
            name_ar=data.get('name_ar'),
            description=data.get('description'),
            category=data.get('category', 'general'),
            base_price=data.get('base_price', 0),
            emergency_price=data.get('emergency_price'),
            insurance_price=data.get('insurance_price'),
            currency=data.get('currency', 'شيكل'),
            department_id=data.get('department_id'),
            duration=data.get('duration'),
            max_daily=data.get('max_daily'),
            is_active=data.get('is_active', True)
        )
        db.session.add(new_service)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إضافة الخدمة بنجاح', 'id': new_service.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'تعذر إضافة الخدمة حالياً'}), 500

@manager_bp.route('/api/pricing/services/<int:id>', methods=['PUT'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def update_service_api(id):
    """API لتحديث خدمة"""
    try:
        from models.service import ServiceMaster
        service = db.session.get(ServiceMaster, id)
        if not service:
            return jsonify({'success': False, 'message': 'الخدمة غير موجودة'}), 404
            
        data = request.get_json()
        
        if 'name' in data: service.name = data['name']
        if 'name_ar' in data: service.name_ar = data['name_ar']
        if 'description' in data: service.description = data['description']
        if 'category' in data: service.category = data['category']
        if 'base_price' in data: service.base_price = data['base_price']
        if 'emergency_price' in data: service.emergency_price = data['emergency_price']
        if 'insurance_price' in data: service.insurance_price = data['insurance_price']
        if 'currency' in data: service.currency = data['currency']
        if 'department_id' in data: service.department_id = data['department_id']
        if 'duration' in data: service.duration = data['duration']
        if 'max_daily' in data: service.max_daily = data['max_daily']
        if 'is_active' in data: service.is_active = data['is_active']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم تحديث الخدمة بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'تعذر تحديث الخدمة حالياً'}), 500

@manager_bp.route('/api/pricing/services/<int:id>', methods=['DELETE'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def delete_service_api(id):
    """API لحذف خدمة"""
    try:
        from models.service import ServiceMaster
        service = db.session.get(ServiceMaster, id)
        if not service:
            return jsonify({'success': False, 'message': 'الخدمة غير موجودة'}), 404
            
        db.session.delete(service)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم حذف الخدمة بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'تعذر حذف الخدمة حالياً'}), 500


@manager_bp.route('/seed-pricing', methods=['POST'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def seed_pricing():
    """إضافة مجموعة أسعار مقترحة"""
    
    try:
        from services.pricing_service import PricingService
        res = PricingService.seed_all()
        status = 200 if res.get('success') else 400
        return jsonify({'success': res.get('success', False), 'message': res.get('message', '' )}), status
    except Exception as e:
        logging.error(f"Error seeding pricing: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ في إضافة الأسعار المقترحة'}), 500

@manager_bp.route('/unit-control')
@login_required
@role_required('manager', 'admin')
def unit_control():
    """التحكم في الوحدات"""
    
    
    try:
        # جلب معلومات الوحدات
        units = [
            {'name': 'الاستقبال', 'status': 'active', 'users': User.query.filter_by(role='reception').count()},
            {'name': 'الطبيب', 'status': 'active', 'users': User.query.filter_by(role='doctor').count()},
            {'name': 'الطوارئ', 'status': 'active', 'users': User.query.filter_by(role='emergency').count()},
            {'name': 'المختبر', 'status': 'active', 'users': User.query.filter_by(role='lab').count()},
            {'name': 'الأشعة', 'status': 'active', 'users': User.query.filter_by(role='radiology').count()},
            {'name': 'المحاسب', 'status': 'active', 'users': User.query.filter_by(role='accountant').count()}
        ]
        
        return render_template('manager/unit_control.html', units=units)
    except Exception as e:
        logging.error(f"Error in unit control: {str(e)}")
        flash('حدث خطأ في تحميل التحكم في الوحدات', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/user-management')
@login_required
def user_management():
    """إدارة المستخدمين"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))

@manager_bp.route('/settlements')
@login_required
@role_required('manager', 'admin', 'super_admin', 'accountant')
def settlements():
    """تسويات شهرية/فترية حسب القسم أو الطبيب"""
    try:
        # مصادر الفلاتر
        doctors = User.query.filter_by(role='doctor', is_active=True).order_by(User.full_name.asc()).all()
        departments = Department.query.filter_by(is_active=True).order_by(Department.name.asc()).all()

        mode = (request.args.get('mode') or 'doctor').lower()  # doctor | department
        doctor_id = request.args.get('doctor_id', type=int)
        department_id = request.args.get('department_id', type=int)
        month = request.args.get('month')  # yyyy-mm
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # تحديد المدى الزمني
        today = date.today()
        if month:
            try:
                y, m = map(int, month.split('-'))
                period_start = date(y, m, 1)
            except Exception:
                period_start = date(today.year, today.month, 1)
        else:
            period_start = date(today.year, today.month, 1)
        if end_date:
            try:
                period_end = datetime.strptime(end_date, '%Y-%m-%d').date()
            except Exception:
                period_end = date(period_start.year, period_start.month, 28)
        else:
            # نهاية الشهر
            next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            period_end = next_month - timedelta(days=1)

        # استعلام الزيارات ضمن الفترة
        q = Visit.query.filter(
            Visit.visit_date >= period_start,
            Visit.visit_date <= period_end,
            Visit.status == 'COMPLETED'
        )
        target_name = None
        if mode == 'doctor' and doctor_id:
            q = q.filter(Visit.doctor_id == doctor_id)
            d = db.session.get(User, doctor_id)
            target_name = d.full_name if d else None
        elif mode == 'department' and department_id:
            q = q.filter(Visit.department_id == department_id)
            dep = db.session.get(Department, department_id)
            target_name = dep.name_ar or dep.name if dep else None

        visits = q.order_by(Visit.visit_date.asc()).all()

        # حساب التسوية
        def compute_doctor_fee(v: Visit) -> Decimal:
            total = Decimal(str(v.total_amount or 0))
            fee = None
            try:
                from models.pricing import DoctorPricing
                pricing = DoctorPricing.query.filter(
                    DoctorPricing.doctor_id == v.doctor_id,
                    DoctorPricing.department_id == v.department_id,
                    DoctorPricing.is_active == True
                ).order_by(DoctorPricing.effective_from.desc()).first()
            except Exception:
                pricing = None
            vt = (v.visit_type or '').upper()
            if pricing:
                if vt in ['FIRST','CONSULTATION'] and pricing.consultation_price:
                    fee = Decimal(str(pricing.consultation_price))
                elif vt in ['FOLLOW_UP'] and pricing.follow_up_price:
                    fee = Decimal(str(pricing.follow_up_price))
                elif getattr(v, 'is_emergency', False) and pricing.emergency_price:
                    fee = Decimal(str(pricing.emergency_price))
            if fee is None:
                fee = total * Decimal('0.30')
            if fee > total:
                fee = total
            return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        items = []
        for v in visits:
            tot = Decimal(str(v.total_amount or 0))
            paid = Decimal(str(v.paid_amount or 0))
            fee = compute_doctor_fee(v)
            center = (tot - fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            items.append({
                'visit': v,
                'total': float(tot),
                'paid': float(paid),
                'remaining': float((tot - paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'doctor_fee': float(fee),
                'center_share': float(center)
            })
        total_amount = sum(Decimal(str(i['total'])) for i in items) if items else Decimal('0.00')
        paid_amount = sum(Decimal(str(i['paid'])) for i in items) if items else Decimal('0.00')
        doctor_fee_total = sum(Decimal(str(i['doctor_fee'])) for i in items) if items else Decimal('0.00')
        service_share_total = (total_amount - doctor_fee_total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        remaining_amount = (total_amount - paid_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        stats = {
            'period_start': period_start,
            'period_end': period_end,
            'mode': mode,
            'target_name': target_name,
            'count': len(visits),
            'total_amount': float(total_amount),
            'paid_amount': float(paid_amount),
            'remaining_amount': float(remaining_amount),
            'doctor_fee_total': float(doctor_fee_total),
            'service_share_total': float(service_share_total)
        }

        return render_template(
            'manager/settlements.html',
            doctors=doctors,
            departments=departments,
            stats=stats,
            visits=visits,
            items=items,
            selected_doctor_id=doctor_id,
            selected_department_id=department_id,
            selected_month=month
        )
    except Exception as e:
        logging.error(f"Error in settlements: {str(e)}")
        flash('حدث خطأ في تحميل التسويات', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/settlements/export')
@login_required
@role_required('manager', 'admin', 'super_admin', 'accountant')
def settlements_export():
    """تصدير التسوية CSV طبقاً للفلاتر"""
    try:
        # إعادة استخدام نفس منطق الفلاتر
        mode = (request.args.get('mode') or 'doctor').lower()
        doctor_id = request.args.get('doctor_id', type=int)
        department_id = request.args.get('department_id', type=int)
        month = request.args.get('month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        today = date.today()
        if month:
            try:
                y, m = map(int, month.split('-'))
                period_start = date(y, m, 1)
            except Exception:
                period_start = date(today.year, today.month, 1)
        else:
            period_start = date(today.year, today.month, 1)
        if end_date:
            try:
                period_end = datetime.strptime(end_date, '%Y-%m-%d').date()
            except Exception:
                period_end = date(period_start.year, period_start.month, 28)
        else:
            next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            period_end = next_month - timedelta(days=1)

        q = Visit.query.filter(Visit.visit_date >= period_start, Visit.visit_date <= period_end, Visit.status == 'COMPLETED')
        if mode == 'doctor' and doctor_id:
            q = q.filter(Visit.doctor_id == doctor_id)
        elif mode == 'department' and department_id:
            q = q.filter(Visit.department_id == department_id)
        visits = q.order_by(Visit.visit_date.asc()).all()

        def compute_doctor_fee(v: Visit) -> Decimal:
            total = Decimal(str(v.total_amount or 0))
            fee = None
            try:
                from models.pricing import DoctorPricing
                pricing = DoctorPricing.query.filter(DoctorPricing.doctor_id == v.doctor_id, DoctorPricing.department_id == v.department_id, DoctorPricing.is_active == True).order_by(DoctorPricing.effective_from.desc()).first()
            except Exception:
                pricing = None
            vt = (v.visit_type or '').upper()
            if pricing:
                if vt in ['FIRST','CONSULTATION'] and pricing.consultation_price:
                    fee = Decimal(str(pricing.consultation_price))
                elif vt in ['FOLLOW_UP'] and pricing.follow_up_price:
                    fee = Decimal(str(pricing.follow_up_price))
                elif getattr(v, 'is_emergency', False) and pricing.emergency_price:
                    fee = Decimal(str(pricing.emergency_price))
            if fee is None:
                fee = total * Decimal('0.30')
            if fee > total:
                fee = total
            return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        import io
        output = io.StringIO()
        output.write('رقم الزيارة,التاريخ,القسم,الطبيب,المريض,الإجمالي,المدفوع,المتبقي,حصة الطبيب,حصة المركز\n')
        for v in visits:
            total = Decimal(str(v.total_amount or 0))
            paid = Decimal(str(v.paid_amount or 0))
            remaining = (total - paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            fee = compute_doctor_fee(v)
            center = (total - fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            output.write(','.join([
                str(v.id),
                (v.visit_date.strftime('%Y-%m-%d') if v.visit_date else ''),
                (v.department.name_ar if v.department else ''),
                (v.doctor.full_name if v.doctor else ''),
                (v.patient.full_name if v.patient else ''),
                f"{float(total):.2f}",
                f"{float(paid):.2f}",
                f"{float(remaining):.2f}",
                f"{float(fee):.2f}",
                f"{float(center):.2f}"
            ]) + '\n')
        from flask import Response
        filename = f"settlements_{mode}_{(doctor_id or department_id or 'all')}_{period_start}_{period_end}.csv"
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})
    except Exception as e:
        logging.error(f"Error exporting settlements: {str(e)}")
        flash('حدث خطأ في تصدير التسويات', 'error')
        return redirect(url_for('manager.dashboard'))
    
    try:
        # جلب المستخدمين (باستثناء السوبر أدمن)
        users = User.query.filter(User.role != 'super_admin').all()
        
        return render_template('manager/user_management.html', users=users)
    except Exception as e:
        logging.error(f"Error in user management: {str(e)}")
        flash('حدث خطأ في تحميل إدارة المستخدمين', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/staff/schedule', methods=['GET', 'POST'])
@login_required
def staff_schedule():
    if current_user.role not in ['manager', 'admin', 'super_admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('manager.dashboard'))
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            day_of_week = request.form.get('day_of_week', type=int)
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            is_active = request.form.get('is_active') == 'on'
            if not user_id or day_of_week is None or not start_time or not end_time:
                flash('الحقول مطلوبة', 'error')
                return redirect(url_for('manager.staff_schedule', user_id=user_id))
            from datetime import datetime as _dt
            st = _dt.strptime(start_time, '%H:%M').time()
            et = _dt.strptime(end_time, '%H:%M').time()
            s = StaffWorkSchedule.query.filter_by(user_id=user_id, day_of_week=day_of_week).first()
            if s:
                s.start_time = st
                s.end_time = et
                s.is_active = is_active
            else:
                s = StaffWorkSchedule(user_id=user_id, day_of_week=day_of_week, start_time=st, end_time=et, is_active=is_active)
                db.session.add(s)
            db.session.commit()
            flash('تم حفظ جدول العمل', 'success')
            return redirect(url_for('manager.staff_schedule', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(str(e))
            flash('حدث خطأ في حفظ الجدول', 'error')
    users = User.query.filter(User.role.in_(['doctor','lab','radiology']), User.is_active == True).all()
    user_id = request.args.get('user_id', type=int)
    schedules = []
    if user_id:
        schedules = StaffWorkSchedule.query.filter_by(user_id=user_id).order_by(StaffWorkSchedule.day_of_week.asc()).all()
    return render_template('manager/staff_schedule.html', users=users, schedules=schedules, selected_user_id=user_id)

@manager_bp.route('/staff/absence', methods=['GET', 'POST'])
@login_required
def staff_absence():
    if current_user.role not in ['manager', 'admin', 'super_admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('manager.dashboard'))
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            reason = (request.form.get('reason') or '').strip() or None
            if not user_id or not start_date or not end_date:
                flash('الحقول مطلوبة', 'error')
                return redirect(url_for('manager.staff_absence', user_id=user_id))
            from datetime import datetime as _dt
            sd = _dt.strptime(start_date, '%Y-%m-%d').date()
            ed = _dt.strptime(end_date, '%Y-%m-%d').date()
            a = StaffAbsence(user_id=user_id, start_date=sd, end_date=ed, reason=reason)
            db.session.add(a)
            db.session.commit()
            flash('تم إضافة الغياب', 'success')
            return redirect(url_for('manager.staff_absence', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(str(e))
            flash('حدث خطأ في إضافة الغياب', 'error')
    users = User.query.filter(User.role.in_(['doctor','lab','radiology']), User.is_active == True).all()
    user_id = request.args.get('user_id', type=int)
    absences = []
    if user_id:
        absences = StaffAbsence.query.filter_by(user_id=user_id).order_by(StaffAbsence.start_date.desc()).all()
    return render_template('manager/staff_absence.html', users=users, absences=absences, selected_user_id=user_id)


@manager_bp.route('/staff/capacity')
@login_required
def staff_capacity():
    if current_user.role not in ['manager', 'admin', 'super_admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('manager.dashboard'))

    try:
        start_raw = (request.args.get('start_date') or '').strip()
        end_raw = (request.args.get('end_date') or '').strip()
        department_id = request.args.get('department_id', type=int)
        days = request.args.get('days', type=int)
        days = max(1, min(days or 14, 60))

        from datetime import datetime as _dt
        if start_raw:
            try:
                start_date = _dt.strptime(start_raw, '%Y-%m-%d').date()
            except Exception:
                start_date = date.today()
        else:
            start_date = date.today()

        if end_raw:
            try:
                end_date = _dt.strptime(end_raw, '%Y-%m-%d').date()
            except Exception:
                end_date = start_date + timedelta(days=days - 1)
        else:
            end_date = start_date + timedelta(days=days - 1)

        if end_date < start_date:
            end_date = start_date

        departments = Department.query.filter_by(is_active=True).order_by(Department.name_ar.asc()).all()
        dept_ids = [department_id] if department_id else [d.id for d in departments]

        doctors_q = User.query.filter(User.role == 'doctor', User.is_active == True)
        if dept_ids:
            doctors_q = doctors_q.filter(User.department_id.in_(dept_ids))
        doctors = doctors_q.all()

        schedules = StaffWorkSchedule.query.filter(StaffWorkSchedule.user_id.in_([u.id for u in doctors])).all() if doctors else []
        sched_map = {}
        for s in schedules:
            sched_map.setdefault(s.user_id, {})[int(s.day_of_week)] = s

        abs_q = StaffAbsence.query.filter(
            StaffAbsence.user_id.in_([u.id for u in doctors]) if doctors else False,
            StaffAbsence.start_date <= end_date,
            StaffAbsence.end_date >= start_date
        )
        absences = abs_q.all() if doctors else []
        abs_map = {}
        for a in absences:
            abs_map.setdefault(a.user_id, []).append(a)

        by_day = []
        cur = start_date
        while cur <= end_date:
            day_row = {'date': cur, 'departments': []}
            for did in dept_ids:
                dept = next((d for d in departments if d.id == did), None)
                dept_doctors = [u for u in doctors if u.department_id == did]
                scheduled_slots = 0
                effective_slots = 0
                absent_count = 0
                for u in dept_doctors:
                    dow = cur.weekday()
                    s = sched_map.get(u.id, {}).get(dow)
                    if s and not s.is_active:
                        continue
                    start_hour = (s.start_time.hour if s else 9)
                    end_hour = (s.end_time.hour if s else 17)
                    slots = max(0, end_hour - start_hour)
                    scheduled_slots += slots
                    user_abs = False
                    for a in abs_map.get(u.id, []):
                        if a.start_date <= cur <= a.end_date:
                            user_abs = True
                            break
                    if user_abs:
                        absent_count += 1
                        continue
                    effective_slots += slots
                day_row['departments'].append({
                    'department_id': did,
                    'department_name': (dept.name_ar or dept.name) if dept else str(did),
                    'doctors': len(dept_doctors),
                    'absent_doctors': absent_count,
                    'scheduled_slots': scheduled_slots,
                    'effective_slots': effective_slots,
                    'lost_slots': max(0, scheduled_slots - effective_slots),
                })
            by_day.append(day_row)
            cur = cur + timedelta(days=1)

        return render_template(
            'manager/staff_capacity.html',
            departments=departments,
            selected_department_id=department_id,
            start_date=start_date,
            end_date=end_date,
            days=days,
            by_day=by_day
        )
    except Exception as e:
        logging.error(f"Staff capacity error: {str(e)}")
        flash('حدث خطأ في تحميل تقرير الاستيعاب', 'error')
        return redirect(url_for('manager.dashboard'))

# تم نقل /reports إلى admin.py - المدير يستخدم admin/reports

# ==================== الميزات الذكية للمانجر ====================

def get_smart_analytics():
    """التحليلات الذكية للمانجر"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.payment import Payment
        from models.appointment import Appointment
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # تحليل النمو
        patients_this_week = Patient.query.filter(Patient.created_at >= week_ago).count()
        patients_last_week = Patient.query.filter(
            Patient.created_at >= week_ago - timedelta(days=7),
            Patient.created_at < week_ago
        ).count()
        
        growth_rate = ((patients_this_week - patients_last_week) / patients_last_week * 100) if patients_last_week > 0 else 0
        
        # تحليل الإيرادات
        revenue_this_week = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) >= week_ago
        ).scalar() or 0
        
        revenue_last_week = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) >= (week_ago - timedelta(days=7)),
            func.date(Payment.payment_date) < week_ago
        ).scalar() or 0
        
        revenue_growth = ((revenue_this_week - revenue_last_week) / revenue_last_week * 100) if revenue_last_week > 0 else 0
        
        completion_rate = (Visit.query.filter(Visit.status == 'ARCHIVED').count() / Visit.query.count() * 100) if Visit.query.count() > 0 else 0
        avg_visit_minutes = 0.0
        try:
            avg_seconds = db.session.query(
                func.avg(func.extract('epoch', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at) - Visit.created_at))
            ).filter(
                Visit.created_at.isnot(None),
                func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
            ).scalar()
            avg_visit_minutes = float(avg_seconds or 0) / 60.0
        except Exception:
            try:
                avg_days = db.session.query(
                    func.avg(func.julianday(func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.julianday(Visit.created_at))
                ).filter(
                    Visit.created_at.isnot(None),
                    func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
                ).scalar()
                avg_visit_minutes = float((avg_days or 0) * 1440)
            except Exception:
                avg_visit_minutes = 0.0
        
        return {
            'patient_growth_rate': round(growth_rate, 2),
            'revenue_growth_rate': round(revenue_growth, 2),
            'avg_visit_duration': round(avg_visit_minutes, 2),
            'completion_rate': round(completion_rate, 2),
            'trend': 'growing' if growth_rate > 0 else 'stable' if growth_rate == 0 else 'declining'
        }
    except Exception as e:
        logging.error(f"Error getting smart analytics: {str(e)}")
        return {}

def get_business_insights():
    """رؤى الأعمال الذكية"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.payment import Payment
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        insights = []
        
        # تحليل ساعات الذروة
        try:
            peak_hours = db.session.query(
                func.extract('hour', Visit.visit_time).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.extract('hour', Visit.visit_time)).all()
        except Exception:
            peak_hours = db.session.query(
                func.strftime('%H', Visit.visit_time).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.strftime('%H', Visit.visit_time)).all()
        
        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 10:
                insights.append({
                    'type': 'peak_hours',
                    'title': 'ساعات الذروة',
                    'description': f'الساعة {max_hour.hour}:00 هي الأكثر ازدحاماً مع {max_hour.count} زيارة',
                    'recommendation': 'توزيع المواعيد على ساعات أخرى لتقليل الازدحام'
                })
        
        # تحليل الأداء المالي
        total_revenue = db.session.query(func.sum(Payment.amount)).scalar() or 0
        avg_revenue_per_visit = total_revenue / Visit.query.count() if Visit.query.count() > 0 else 0
        
        if avg_revenue_per_visit > 100:
            insights.append({
                'type': 'financial',
                'title': 'الأداء المالي',
                'description': f'متوسط الإيراد لكل زيارة: {avg_revenue_per_visit:.2f} ريال',
                'recommendation': 'الأداء المالي ممتاز - يمكن زيادة الخدمات'
            })
        
        # تحليل الموظفين
        active_staff = User.query.filter(User.last_login >= datetime.now() - timedelta(days=7)).count()
        total_staff = User.query.count()
        staff_engagement = (active_staff / total_staff * 100) if total_staff > 0 else 0
        
        if staff_engagement < 70:
            insights.append({
                'type': 'staff',
                'title': 'مشاركة الموظفين',
                'description': f'معدل مشاركة الموظفين: {staff_engagement:.1f}%',
                'recommendation': 'تحسين مشاركة الموظفين من خلال التدريب والتطوير'
            })
        
        return insights
    except Exception as e:
        logging.error(f"Error getting business insights: {str(e)}")
        return []

def get_performance_metrics():
    """مقاييس الأداء الذكية"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.appointment import Appointment
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # معدل الإنجاز
        total_visits = Visit.query.count()
        completed_visits = Visit.query.filter(Visit.status == 'ARCHIVED').count()
        completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
        
        # معدل المواعيد
        total_appointments = Appointment.query.count()
        completed_appointments = Appointment.query.filter(Appointment.status == 'DONE').count()
        appointment_rate = (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0
        
        avg_wait_minutes = 0.0
        try:
            avg_seconds = db.session.query(
                func.avg(func.extract('epoch', Visit.completed_at - Visit.created_at))
            ).filter(Visit.completed_at.isnot(None)).scalar()
            avg_wait_minutes = float(avg_seconds or 0) / 60.0
        except Exception:
            avg_days = db.session.query(
                func.avg(func.julianday(Visit.completed_at) - func.julianday(Visit.created_at))
            ).filter(Visit.completed_at.isnot(None)).scalar()
            avg_wait_minutes = float((avg_days or 0) * 1440)
        
        # معدل الرضا (محاكاة)
        satisfaction_rate = min(100, max(0, completion_rate + (100 - completion_rate) * 0.3))
        
        return {
            'completion_rate': round(completion_rate, 2),
            'appointment_rate': round(appointment_rate, 2),
            'avg_wait_time': round(avg_wait_minutes, 2),
            'satisfaction_rate': round(satisfaction_rate, 2),
            'overall_score': round((completion_rate + appointment_rate + satisfaction_rate) / 3, 2)
        }
    except Exception as e:
        logging.error(f"Error getting performance metrics: {str(e)}")
        return {}

def get_financial_forecasting():
    """التنبؤ المالي الذكي"""
    try:
        from models.payment import Payment
        from models.visit import Visit
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل الإيرادات التاريخية
        week_ago = datetime.now().date() - timedelta(days=7)
        month_ago = datetime.now().date() - timedelta(days=30)
        
        revenue_this_week = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= week_ago
        ).scalar() or 0
        
        revenue_last_week = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= week_ago - timedelta(days=7),
            Payment.payment_date < week_ago
        ).scalar() or 0
        
        # حساب معدل النمو
        growth_rate = ((revenue_this_week - revenue_last_week) / revenue_last_week * 100) if revenue_last_week > 0 else 0
        
        # التنبؤ بالأسبوع القادم
        predicted_next_week = revenue_this_week * (1 + growth_rate/100)
        
        # التنبؤ الشهري
        monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) >= month_ago
        ).scalar() or 0
        
        predicted_monthly = monthly_revenue * (1 + growth_rate/100)
        
        return {
            'current_week_revenue': revenue_this_week,
            'growth_rate': round(growth_rate, 2),
            'predicted_next_week': round(predicted_next_week, 2),
            'monthly_revenue': monthly_revenue,
            'predicted_monthly': round(predicted_monthly, 2),
            'trend': 'growing' if growth_rate > 0 else 'stable' if growth_rate == 0 else 'declining'
        }
    except Exception as e:
        logging.error(f"Error getting financial forecasting: {str(e)}")
        return {}

def get_operational_efficiency():
    """كفاءة العمليات"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل الكفاءة حسب الأقسام
        try:
            department_efficiency = db.session.query(
                func.count(Visit.id).label('visits'),
                func.avg(func.extract('epoch', Visit.completed_at - Visit.created_at)).label('avg_seconds'),
                User.department_id
            ).join(User, Visit.doctor_id == User.id).filter(Visit.completed_at.isnot(None)).group_by(User.department_id).all()
            department_efficiency = [
                type('Row', (), {'visits': d.visits, 'avg_duration': float(d.avg_seconds or 0), 'department_id': d.department_id})
                for d in department_efficiency
            ]
        except Exception:
            dept_eff = db.session.query(
                func.count(Visit.id).label('visits'),
                func.avg(func.julianday(Visit.completed_at) - func.julianday(Visit.created_at)).label('avg_days'),
                User.department_id
            ).join(User, Visit.doctor_id == User.id).filter(Visit.completed_at.isnot(None)).group_by(User.department_id).all()
            department_efficiency = [
                type('Row', (), {'visits': d.visits, 'avg_duration': float((d.avg_days or 0) * 86400), 'department_id': d.department_id})
                for d in dept_eff
            ]
        
        # تحليل استخدام الموارد
        resource_utilization = {
            'total_doctors': User.query.filter(User.role == 'doctor').count(),
            'active_doctors': User.query.filter(
                User.role == 'doctor',
                User.last_login >= datetime.now() - timedelta(days=7)
            ).count(),
            'total_visits_today': Visit.query.filter(
                func.date(Visit.created_at) == datetime.now().date()
            ).count()
        }
        
        # حساب معدل الكفاءة
        if resource_utilization['total_doctors'] > 0:
            efficiency_rate = (resource_utilization['active_doctors'] / resource_utilization['total_doctors'] * 100)
        else:
            efficiency_rate = 0
        
        return {
            'department_efficiency': [
                {
                    'department_id': dept.department_id,
                    'visits': dept.visits,
                    'avg_duration': round(dept.avg_duration or 0, 2)
                } for dept in department_efficiency
            ],
            'resource_utilization': resource_utilization,
            'efficiency_rate': round(efficiency_rate, 2),
            'status': 'optimal' if efficiency_rate > 80 else 'good' if efficiency_rate > 60 else 'needs_improvement'
        }
    except Exception as e:
        logging.error(f"Error getting operational efficiency: {str(e)}")
        return {}

def get_staff_productivity():
    """إنتاجية الموظفين"""
    try:
        from models.user import User
        from models.visit import Visit
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل إنتاجية الأطباء
        doctor_productivity = db.session.query(
            User.id,
            User.full_name,
            func.count(Visit.id).label('total_visits'),
            func.avg(Visit.duration).label('avg_duration')
        ).join(Visit, User.id == Visit.doctor_id).filter(
            Visit.created_at >= datetime.now().date() - timedelta(days=30)
        ).group_by(User.id, User.full_name).all()
        
        # تحليل النشاط
        active_staff = User.query.filter(
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        total_staff = User.query.count()
        engagement_rate = (active_staff / total_staff * 100) if total_staff > 0 else 0
        
        return {
            'doctor_productivity': [
                {
                    'doctor_id': doc.id,
                    'doctor_name': doc.full_name,
                    'total_visits': doc.total_visits,
                    'avg_duration': round(doc.avg_duration or 0, 2)
                } for doc in doctor_productivity
            ],
            'engagement_rate': round(engagement_rate, 2),
            'active_staff': active_staff,
            'total_staff': total_staff,
            'status': 'excellent' if engagement_rate > 90 else 'good' if engagement_rate > 70 else 'needs_attention'
        }
    except Exception as e:
        logging.error(f"Error getting staff productivity: {str(e)}")
        return {}

def get_patient_satisfaction():
    """رضا المرضى (محاكاة)"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from datetime import datetime, timedelta
        
        # محاكاة معدل الرضا بناءً على البيانات المتاحة
        total_visits = Visit.query.count()
        completed_visits = Visit.query.filter(Visit.status == 'ARCHIVED').count()
        
        # حساب معدل الرضا بناءً على معدل الإنجاز
        base_satisfaction = (completed_visits / total_visits * 100) if total_visits > 0 else 0
        
        # إضافة عوامل أخرى
        avg_duration = db.session.query(func.avg(Visit.duration)).scalar() or 0
        duration_factor = max(0, 100 - (avg_duration / 60 * 10))  # تقليل الرضا مع زيادة الوقت
        
        # حساب الرضا النهائي
        satisfaction_score = (base_satisfaction + duration_factor) / 2
        
        return {
            'satisfaction_score': round(satisfaction_score, 2),
            'base_satisfaction': round(base_satisfaction, 2),
            'duration_factor': round(duration_factor, 2),
            'status': 'excellent' if satisfaction_score > 90 else 'good' if satisfaction_score > 70 else 'needs_improvement',
            'recommendations': [
                'تحسين أوقات الانتظار' if avg_duration > 30 else 'الأداء ممتاز',
                'زيادة معدل إنجاز الزيارات' if base_satisfaction < 80 else 'معدل الإنجاز جيد'
            ]
        }
    except Exception as e:
        logging.error(f"Error getting patient satisfaction: {str(e)}")
        return {}

def get_resource_optimization():
    """تحسين الموارد"""
    try:
        from models.visit import Visit
        from models.user import User
        from models.patient import Patient
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        optimizations = []
        
        # تحليل ساعات الذروة
        try:
            peak_hours = db.session.query(
                func.extract('hour', Visit.visit_time).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.extract('hour', Visit.visit_time)).all()
        except Exception:
            peak_hours = db.session.query(
                func.strftime('%H', Visit.visit_time).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.strftime('%H', Visit.visit_time)).all()
        
        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 15:
                optimizations.append({
                    'type': 'peak_hours',
                    'title': 'توزيع ساعات الذروة',
                    'description': f'الساعة {max_hour.hour}:00 مزدحمة جداً ({max_hour.count} زيارة)',
                    'suggestion': 'توزيع المواعيد على ساعات أخرى'
                })
        
        # تحليل الأقسام
        department_load = db.session.query(
            func.count(Visit.id).label('count'),
            User.department_id
        ).join(User, Visit.doctor_id == User.id).group_by(User.department_id).all()
        
        if department_load:
            max_dept = max(department_load, key=lambda x: x.count)
            if max_dept.count > 20:
                optimizations.append({
                    'type': 'department_load',
                    'title': 'توزيع الأحمال',
                    'description': f'القسم {max_dept.department_id} مزدحم ({max_dept.count} زيارة)',
                    'suggestion': 'إضافة موارد إضافية أو إعادة توزيع الأحمال'
                })
        
        # تحليل الموظفين
        active_doctors = User.query.filter(
            User.role == 'doctor',
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        total_doctors = User.query.filter(User.role == 'doctor').count()
        
        if active_doctors < total_doctors * 0.8:
            optimizations.append({
                'type': 'staff_utilization',
                'title': 'استخدام الموظفين',
                'description': f'فقط {active_doctors} من {total_doctors} طبيب نشط',
                'suggestion': 'تحفيز الموظفين أو إعادة توزيع المهام'
            })
        
        return optimizations
    except Exception as e:
        logging.error(f"Error getting resource optimization: {str(e)}")
        return []

@manager_bp.route('/reports')
@login_required
def reports():
    """التقارير"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('manager/reports.html')


@manager_bp.route('/reports-center')
@login_required
def reports_center():
    if current_user.role not in ['manager', 'admin', 'super_admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))

    try:
        from services.report_center_service import ReportCenterService
        from models.department import Department
        from models.user import User

        report = (request.args.get('report') or '').strip()
        start_raw = request.args.get('start_date')
        end_raw = request.args.get('end_date')
        department_id = request.args.get('department_id', type=int)

        start_date, end_date, start_dt, end_dt = ReportCenterService._parse_dates(start_raw, end_raw)
        result = None

        if report == 'compare_month':
            now = date.today()
            a_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            if now.month == 12:
                a_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                a_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            if now.month == 1:
                p_year, p_month = now.year - 1, 12
            else:
                p_year, p_month = now.year, now.month - 1
            b_start = datetime(p_year, p_month, 1, tzinfo=timezone.utc)
            if p_month == 12:
                b_end = datetime(p_year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                b_end = datetime(p_year, p_month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            result = {'compare': ReportCenterService.compare_periods(a_start, a_end, b_start, b_end, department_id=department_id)}
        elif report == 'compare_year':
            now = date.today()
            a_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
            a_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            b_start = datetime(now.year - 1, 1, 1, tzinfo=timezone.utc)
            b_end = datetime(now.year, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            result = {'compare': ReportCenterService.compare_periods(a_start, a_end, b_start, b_end, department_id=department_id)}
        elif report == 'transfers':
            result = {'transfers': ReportCenterService.department_transfers(start_dt, end_dt)}
        elif report == 'capacity':
            result = {'capacity': ReportCenterService.capacity_impact(start_date, end_date)}
        elif report == 'booking':
            booking = ReportCenterService.booking_report(start_dt, end_dt)
            dept_names = {d.id: (d.name_ar or d.name) for d in Department.query.all()}
            doctor_names = {u.id: u.full_name for u in User.query.filter_by(role='doctor').all()}
            booking['top_departments_named'] = [{'label': dept_names.get(did) or 'غير محدد', 'count': cnt} for did, cnt in booking.get('top_departments', [])]
            booking['top_doctors_named'] = [{'label': doctor_names.get(did) or 'غير محدد', 'count': cnt} for did, cnt in booking.get('top_doctors', [])]
            result = {'booking': booking}
        elif report == 'emergency_times':
            result = {'emergency_times': ReportCenterService.emergency_stage_times(start_dt, end_dt)}
        elif report == 'radiology_revision':
            result = {'radiology_revision': ReportCenterService.radiology_revision_rate(start_dt, end_dt)}

        departments = Department.query.filter_by(is_active=True).all()
        return render_template(
            'manager/reports_center.html',
            report=report,
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            departments=departments,
            result=result
        )
    except Exception as e:
        logging.error(f"Manager reports center error: {str(e)}")
        return render_template('manager/reports_center.html', report='', start_date=None, end_date=None, departments=[], result=None)


@manager_bp.route('/staff')
@login_required
def staff():
    """إدارة الموظفين"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('manager/user_management.html')

@manager_bp.route('/analytics')
@login_required
def analytics():
    """التحليلات"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('manager/monitoring.html')

@manager_bp.route('/api/what-if', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def api_what_if():
    try:
        data = request.get_json() or {}
        add_staff = int(data.get('add_staff') or 0)
        add_rooms = int(data.get('add_rooms') or 0)
        base_visits = Visit.query.filter(Visit.status.in_(['OPEN', 'IN_PROGRESS'])).count()
        capacity_gain = (add_staff * 6) + (add_rooms * 8)
        predicted_throughput = int(base_visits + capacity_gain)
        predicted_wait = max(5, int(30 - (capacity_gain / 2)))
        predicted_revenue = float(db.session.query(func.sum(Payment.amount)).scalar() or 0) * (1 + (capacity_gain / 100))
        return jsonify({
            'success': True,
            'predicted_throughput': predicted_throughput,
            'predicted_wait_minutes': predicted_wait,
            'predicted_revenue': round(predicted_revenue, 2)
        }), 200
    except Exception as e:
        logging.error(f"Error computing what-if: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر احتساب السيناريو'}), 500

@manager_bp.route('/self-service')
@login_required
@role_required('manager', 'admin', 'super_admin')
def self_service():
    try:
        from services.advanced_report_service import AdvancedReportService
        report_type = (request.args.get('type') or 'patients').strip()
        start_raw = (request.args.get('start_date') or '').strip()
        end_raw = (request.args.get('end_date') or '').strip()
        start_date = datetime.strptime(start_raw, '%Y-%m-%d') if start_raw else None
        end_date = datetime.strptime(end_raw, '%Y-%m-%d') if end_raw else None
        if report_type == 'visits':
            data = AdvancedReportService.generate_visit_analytics(start_date, end_date)
        elif report_type == 'financial':
            data = AdvancedReportService.generate_financial_analytics(start_date, end_date)
        elif report_type == 'departments':
            data = AdvancedReportService.generate_department_analytics(start_date, end_date)
        else:
            data = AdvancedReportService.generate_patient_analytics(start_date, end_date)
            report_type = 'patients'
        return render_template('manager/self_service.html', report_type=report_type, data=data, start_date=start_raw, end_date=end_raw)
    except Exception as e:
        logging.error(f"Error in self service analytics: {str(e)}")
        return render_template('manager/self_service.html', report_type='patients', data={}, start_date='', end_date='')

def get_bi_insights():
    try:
        start_30d = datetime.now(timezone.utc) - timedelta(days=30)
        visits_30d = Visit.query.filter(Visit.created_at >= start_30d).count()
        completed_30d = Visit.query.filter(Visit.status == 'ARCHIVED', Visit.created_at >= start_30d).count()
        appointments_30d = Appointment.query.filter(Appointment.starts_at >= start_30d).count()
        no_show = Appointment.query.filter(Appointment.status == 'no_show', Appointment.starts_at >= start_30d).count()
        cancel = Appointment.query.filter(Appointment.status == 'cancelled', Appointment.starts_at >= start_30d).count()
        conversion_rate = (completed_30d / visits_30d * 100) if visits_30d else 0
        no_show_rate = (no_show / appointments_30d * 100) if appointments_30d else 0
        cancel_rate = (cancel / appointments_30d * 100) if appointments_30d else 0
        return {
            'visits_30d': int(visits_30d or 0),
            'completed_30d': int(completed_30d or 0),
            'appointments_30d': int(appointments_30d or 0),
            'conversion_rate': round(conversion_rate, 2),
            'no_show_rate': round(no_show_rate, 2),
            'cancel_rate': round(cancel_rate, 2)
        }
    except Exception:
        return {}

@manager_bp.route('/financial-reports')
@login_required
def financial_reports():
    """التقارير المالية"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('manager/reports.html')

@manager_bp.route('/departments')
@login_required
def departments():
    """إدارة الأقسام"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        departments = Department.query.all()
        return render_template('manager/departments.html', departments=departments)
    except Exception as e:
        logging.error(f"Error loading departments: {str(e)}")
        flash('حدث خطأ في تحميل الأقسام', 'error')
        return redirect(url_for('manager.dashboard'))

# ==================== موافقات الدفع القسري (الأسبوع الثاني) ====================

@manager_bp.route('/force-payment-approvals')
@login_required
@manager_or_admin_only
def force_payment_approvals():
    """صفحة موافقات الدفع القسري"""
    try:
        # الدفعات القسرية المعلقة
        pending_approvals = Visit.query.filter(
            Visit.is_force_payment == True,
            Visit.force_payment_approved_by == None
        ).order_by(Visit.created_at.desc()).all()
        
        # الدفعات القسرية المعتمدة (آخر 30 يوم)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        approved_payments = Visit.query.filter(
            Visit.is_force_payment == True,
            Visit.force_payment_approved_by != None,
            Visit.force_payment_approved_at >= thirty_days_ago
        ).order_by(Visit.force_payment_approved_at.desc()).all()
        
        # إحصائيات
        stats = GatekeeperService.get_force_payment_statistics(days=30)
        
        return render_template('manager/force_payment_approvals.html',
                             pending_approvals=pending_approvals,
                             approved_payments=approved_payments,
                             stats=stats)
    
    except Exception as e:
        logging.error(f"Error loading force payment approvals: {str(e)}")
        flash('حدث خطأ في تحميل صفحة الموافقات', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/approve-force-payment/<int:visit_id>', methods=['POST'])
@login_required
@can_approve_force_payment
@prevent_self_approval
def approve_force_payment(visit_id):
    """الموافقة على دفع قسري"""
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # التحقق من أنها زيارة دفع قسري
        if not visit.is_force_payment:
            flash('هذه ليست زيارة دفع قسري', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # التحقق من أنها غير معتمدة
        if visit.force_payment_approved_by:
            flash('تم الموافقة على هذا الدفع مسبقاً', 'warning')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # التحقق من الصلاحية
        is_valid, message = GatekeeperService.validate_force_payment(
            visit_id,
            current_user.id,
            visit.force_payment_reason
        )
        
        if not is_valid:
            flash(message, 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # الموافقة
        visit.force_payment_approved_by = current_user.id
        visit.force_payment_approved_at = datetime.now(timezone.utc)
        visit.payment_status = 'DEBT'  # تحديد كدين معتمد
        
        db.session.commit()
        
        # إدراج الزيارة في طابور القسم تلقائياً إذا لم تكن مدرجة
        try:
            from models.queue_management import QueueManagement
            existing_ticket = QueueManagement.query.filter_by(visit_id=visit_id, department_id=visit.department_id).first()
            if not existing_ticket:
                from routes.reception import add_patient_to_queue_auto
                add_patient_to_queue_auto(visit_id=visit_id, department_id=visit.department_id, doctor_id=visit.doctor_id)
        except Exception:
            pass
        
        # تسجيل في التدقيق
        from models.audit_trail import AuditTrail
        audit = AuditTrail(
            user_id=current_user.id,
            action='APPROVE',
            entity_type='visit',
            entity_id=visit_id,
            description=f'موافقة على دفع قسري - {visit.force_payment_reason}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'تمت الموافقة على الدفع القسري للزيارة #{visit.id}', 'success')
        logging.info(f"Force payment approved: Visit {visit_id} by User {current_user.id}")
        
        return redirect(url_for('manager.force_payment_approvals'))
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error approving force payment: {str(e)}")
        flash('تعذر تنفيذ الموافقة حالياً، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('manager.force_payment_approvals'))

@manager_bp.route('/reject-force-payment/<int:visit_id>', methods=['POST'])
@login_required
@can_approve_force_payment
def reject_force_payment(visit_id):
    """رفض دفع قسري"""
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        rejection_reason = request.form.get('rejection_reason', '')
        
        # التحقق من أنها زيارة دفع قسري
        if not visit.is_force_payment:
            flash('هذه ليست زيارة دفع قسري', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # التحقق من السبب
        if not rejection_reason or len(rejection_reason.strip()) < 10:
            flash('يجب تقديم سبب واضح للرفض (10 أحرف على الأقل)', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # الرفض
        visit.is_force_payment = False
        visit.payment_method = 'CASH'
        visit.payment_status = 'PENDING'
        visit.force_payment_reason = f'[مرفوض] {visit.force_payment_reason}\nسبب الرفض: {rejection_reason}'
        
        db.session.commit()
        
        # تسجيل في التدقيق
        from models.audit_trail import AuditTrail
        audit = AuditTrail(
            user_id=current_user.id,
            action='REJECT',
            entity_type='visit',
            entity_id=visit_id,
            description=f'رفض دفع قسري - {rejection_reason}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'تم رفض الدفع القسري للزيارة #{visit.id}', 'warning')
        logging.info(f"Force payment rejected: Visit {visit_id} by User {current_user.id}")
        
        return redirect(url_for('manager.force_payment_approvals'))
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error rejecting force payment: {str(e)}")
        flash('تعذر تنفيذ الرفض حالياً، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('manager.force_payment_approvals'))

@manager_bp.route('/kpi-dashboard')
@login_required
@manager_or_admin_only
def kpi_dashboard():
    """لوحة مؤشرات الأداء"""
    try:
        from services.report_service import ReportService
        
        # الحصول على تقرير الشهر الحالي
        report = ReportService.get_monthly_audit_report()
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('manager.dashboard'))
        
        # الحصول على إحصائيات الدفع القسري
        force_stats = GatekeeperService.get_force_payment_statistics(days=30)
        
        return render_template('manager/kpi_dashboard.html',
                             report=report,
                             force_stats=force_stats)
    
    except Exception as e:
        logging.error(f"Error loading KPI dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة المؤشرات', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/budget', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def budget_dashboard():
    """إدارة الميزانية - Budget vs Actual"""
    from models.budget import Budget
    today = date.today()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))

    if request.method == 'POST':
        dept_id = request.form.get('department_id')
        dept_id = int(dept_id) if dept_id else None
        b = Budget.get_or_create(year, month, dept_id, current_user.id)
        b.revenue_target = Decimal(request.form.get('revenue_target', 0))
        b.visits_target = int(request.form.get('visits_target', 0))
        b.new_patients_target = int(request.form.get('new_patients_target', 0))
        b.expenses_target = Decimal(request.form.get('expenses_target', 0))
        b.notes = request.form.get('notes', '')
        db.session.commit()
        flash('تم حفظ الميزانية', 'success')
        return redirect(url_for('manager.budget_dashboard', year=year, month=month))

    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    actual_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date >= start, Payment.payment_date < end,
        Payment.status.in_(['COMPLETED', 'PAID'])
    ).scalar() or 0

    actual_visits = Visit.query.filter(Visit.visit_date >= start, Visit.visit_date < end).count()
    actual_new_patients = Patient.query.filter(Patient.created_at >= start, Patient.created_at < end).count()

    budgets = Budget.query.filter_by(year=year, month=month).all()
    dept_budgets = {b.department_id: b for b in budgets}

    return render_template('manager/budget.html',
                           year=year, month=month,
                           actual_revenue=float(actual_revenue),
                           actual_visits=actual_visits,
                           actual_new_patients=actual_new_patients,
                           dept_budgets=dept_budgets,
                           departments=Department.query.all())


@manager_bp.route('/monthly-comparison')
@login_required
@role_required('manager', 'admin', 'super_admin')
def monthly_comparison():
    """مقارنة شهرية - MoM / YoY"""
    today = date.today()
    months = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1)
        else:
            end = date(y, m + 1, 1)

        rev = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= start, Payment.payment_date < end
        ).scalar() or 0
        vis = Visit.query.filter(Visit.visit_date >= start, Visit.visit_date < end).count()
        newp = Patient.query.filter(Patient.created_at >= start, Patient.created_at < end).count()

        months.append({'label': f"{y}-{m:02d}", 'revenue': float(rev), 'visits': vis, 'new_patients': newp})

    for i in range(1, len(months)):
        prev = months[i - 1]
        curr = months[i]
        curr['revenue_growth'] = round(((curr['revenue'] - prev['revenue']) / (prev['revenue'] or 1)) * 100, 1)
        curr['visits_growth'] = round(((curr['visits'] - prev['visits']) / (prev['visits'] or 1)) * 100, 1)

    return render_template('manager/monthly_comparison.html', months=months)


@manager_bp.route('/drill-down/<report_type>')
@login_required
@role_required('manager', 'admin', 'super_admin')
def drill_down(report_type):
    """تقارير drill-down"""
    today = date.today()
    start = request.args.get('start', today.strftime('%Y-%m-%d'))
    end = request.args.get('end', today.strftime('%Y-%m-%d'))
    dept_id = request.args.get('department_id')
    try:
        start_dt = datetime.strptime(start, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end, '%Y-%m-%d').date()
    except ValueError:
        start_dt = end_dt = today

    if report_type == 'visits':
        title = 'تفاصيل الزيارات'
        q = Visit.query.filter(Visit.visit_date >= start_dt, Visit.visit_date <= end_dt)
        if dept_id:
            q = q.filter_by(department_id=int(dept_id))
        results = q.order_by(Visit.visit_date.desc()).limit(200).all()
    elif report_type == 'revenue':
        title = 'تفاصيل الإيرادات'
        q = Payment.query.filter(Payment.payment_date >= start_dt, Payment.payment_date <= end_dt)
        results = q.order_by(Payment.payment_date.desc()).limit(200).all()
    elif report_type == 'patients':
        title = 'المرضى الجدد'
        results = Patient.query.filter(Patient.created_at >= start_dt, Patient.created_at <= end_dt).order_by(Patient.created_at.desc()).limit(200).all()
    else:
        flash('نوع التقرير غير معروف', 'error')
        return redirect(url_for('manager.dashboard'))

    return render_template('manager/drill_down.html', report_type=report_type, title=title,
                           results=results, start=start, end=end, departments=Department.query.all())


@manager_bp.route('/patient-satisfaction')
@login_required
@role_required('manager', 'admin', 'super_admin')
def patient_satisfaction_dashboard():
    """لوحة رضا المرضى"""
    try:
        from models.patient_satisfaction import PatientSatisfactionSurvey
        surveys = PatientSatisfactionSurvey.query.order_by(PatientSatisfactionSurvey.created_at.desc()).limit(100).all()
        total = len(surveys) if surveys else 0
        if total > 0:
            avg_score = sum(float(s.overall_satisfaction or 0) for s in surveys) / total
            avg_recommend = sum(float(s.recommend_likelihood or 0) for s in surveys) / total
            promoters = sum(1 for s in surveys if float(s.recommend_likelihood or 0) >= 9)
            detractors = sum(1 for s in surveys if float(s.recommend_likelihood or 0) <= 6)
            nps = round(((promoters - detractors) / total) * 100, 1)
        else:
            avg_score = avg_recommend = nps = 0
        return render_template('manager/patient_satisfaction.html', surveys=surveys, total=total,
                               avg_score=round(avg_score, 1), avg_recommend=round(avg_recommend, 1), nps=nps)
    except Exception:
        return render_template('manager/patient_satisfaction.html', surveys=[], total=0,
                               avg_score=0, avg_recommend=0, nps=0)


@manager_bp.route('/exchange-rates', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def exchange_rates():
    """إدارة أسعار الصرف"""
    from models.exchange_rate import ExchangeRate, CurrencySettings
    from services.currency_service import CurrencyConverter
    from decimal import Decimal

    if request.method == 'POST':
        try:
            from_currency = request.form.get('from_currency', '').strip().upper()
            to_currency = request.form.get('to_currency', '').strip().upper()
            sell_rate = request.form.get('sell_rate', '').strip()
            buy_rate = request.form.get('buy_rate', '').strip() or sell_rate
            notes = request.form.get('notes', '').strip()

            if not from_currency or not to_currency or not sell_rate:
                flash('جميع الحقول المطلوبة يجب تعبئتها', 'error')
                return redirect(url_for('manager.exchange_rates'))

            CurrencyConverter.ensure_manual_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                sell_rate=Decimal(sell_rate),
                buy_rate=Decimal(buy_rate) if buy_rate else None,
                user_id=current_user.id,
            )
            flash(f'تم تحديث سعر الصرف {from_currency} → {to_currency}', 'success')
        except Exception as e:
            logging.error(f"Error saving exchange rate: {e}")
            flash('حدث خطأ أثناء حفظ سعر الصرف', 'error')
        return redirect(url_for('manager.exchange_rates'))

    active_rates = CurrencyConverter.get_all_active_rates()
    missing_pairs = CurrencyConverter.get_missing_pairs()
    currencies = CurrencySettings.get_all()
    return render_template('manager/exchange_rates.html',
                           rates=active_rates,
                           missing_pairs=missing_pairs,
                           currencies=currencies)


@manager_bp.route('/exchange-rates/fetch-api', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def fetch_api_exchange_rates():
    """جلب أسعار الصرف من API خارجي"""
    from models.exchange_rate import CurrencySettings
    from services.currency_service import CurrencyConverter
    base = request.form.get('base_currency', 'ILS').upper()
    imported = 0
    failed = 0
    for code in CurrencySettings.SUPPORTED_CURRENCIES:
        if code == base:
            continue
        try:
            rate = CurrencyConverter.fetch_external_rate(base, code)
            if rate:
                imported += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    flash(f'تم جلب {imported} سعر صرف | فشل {failed}', 'info' if failed == 0 else 'warning')
    return redirect(url_for('manager.exchange_rates'))


@manager_bp.route('/exchange-rates/deactivate/<int:rate_id>', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def deactivate_exchange_rate(rate_id):
    """تعطيل سعر صرف"""
    from models.exchange_rate import ExchangeRate
    rate = ExchangeRate.query.get_or_404(rate_id)
    rate.is_active = False
    db.session.commit()
    flash(f'تم تعطيل سعر {rate.from_currency} → {rate.to_currency}', 'success')
    return redirect(url_for('manager.exchange_rates'))
