"""
مسارات المدير - Manager Routes
Medical System Manager Routes
نسخة محسّنة مع موافقات الدفع القسري (الأسبوع الثاني)
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.payment import Payment
from models.invoice import Invoice
from services.gatekeeper_service import GatekeeperService
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval
from app_factory import db
import logging
from datetime import datetime, date, timedelta

manager_bp = Blueprint('manager', __name__)

@manager_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة تحكم المدير"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات شاملة
        today = date.today()
        this_month = today.replace(day=1)
        
        # إحصائيات المرضى
        total_patients = Patient.query.count()
        new_patients_today = Patient.query.filter(
            Patient.created_at >= datetime.combine(today, datetime.min.time())
        ).count()
        
        # إحصائيات الزيارات
        total_visits = Visit.query.count()
        visits_today = Visit.query.filter(
            Visit.created_at >= today
        ).count()
        completed_visits_today = Visit.query.filter(
            Visit.status == 'ARCHIVED',
            Visit.completed_at >= datetime.combine(today, datetime.min.time())
        ).count()
        
        # إحصائيات المالية
        today_payments = Payment.query.filter(
            Payment.payment_date == today
        ).all()
        today_revenue = sum(payment.amount for payment in today_payments)
        
        month_payments = Payment.query.filter(
            Payment.payment_date >= this_month
        ).all()
        month_revenue = sum(payment.amount for payment in month_payments)
        
        # إحصائيات المستخدمين
        total_users = User.query.count()
        active_users = User.query.filter(User.is_active == True).count()
        
        # إحصائيات الأقسام
        departments = Department.query.all()
        
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
            'departments': departments
        }
        
        return render_template('manager/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in manager dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@manager_bp.route('/monitoring')
@login_required
def monitoring():
    """مراقبة النظام"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # مراقبة الوحدات
        units_status = {
            'reception': {
                'name': 'الاستقبال',
                'status': 'active',
                'pending_visits': Visit.query.filter(
                    Visit.status == 'PENDING'
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
                    Visit.destination == 'emergency',
                    Visit.status.in_(['READY', 'IN_PROGRESS'])
                ).count()
            },
            'lab': {
                'name': 'المختبر',
                'status': 'active',
                'lab_requests': 0  # سيتم تحديثه عند إضافة نموذج LabRequest
            },
            'radiology': {
                'name': 'الأشعة',
                'status': 'active',
                'radiology_requests': 0  # سيتم تحديثه عند إضافة نموذج RadiologyRequest
            },
            'accountant': {
                'name': 'المحاسب',
                'status': 'active',
                'open_invoices': Invoice.query.filter(
                    Invoice.payment_status.in_(['PENDING', 'PARTIAL'])
                ).count()
            }
        }
        
        return render_template('manager/monitoring.html', units_status=units_status)
    except Exception as e:
        logging.error(f"Error in monitoring: {str(e)}")
        flash('حدث خطأ في تحميل مراقبة النظام', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/pricing')
@login_required
def pricing():
    """إدارة الأسعار"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # جلب خدمات التسعير
        from models.service import ServiceMaster
        services = ServiceMaster.query.all()
        
        return render_template('manager/pricing.html', services=services)
    except Exception as e:
        logging.error(f"Error loading pricing: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الأسعار', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/unit-control')
@login_required
def unit_control():
    """التحكم في الوحدات"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
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
    
    try:
        # جلب المستخدمين (باستثناء السوبر أدمن)
        users = User.query.filter(User.role != 'super_admin').all()
        
        return render_template('manager/user_management.html', users=users)
    except Exception as e:
        logging.error(f"Error in user management: {str(e)}")
        flash('حدث خطأ في تحميل إدارة المستخدمين', 'error')
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
            Payment.payment_date >= week_ago
        ).scalar() or 0
        
        revenue_last_week = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= week_ago - timedelta(days=7),
            Payment.payment_date < week_ago
        ).scalar() or 0
        
        revenue_growth = ((revenue_this_week - revenue_last_week) / revenue_last_week * 100) if revenue_last_week > 0 else 0
        
        # تحليل الأداء
        avg_visit_duration = db.session.query(func.avg(Visit.duration)).scalar() or 0
        completion_rate = (Visit.query.filter(Visit.status == 'ARCHIVED').count() / Visit.query.count() * 100) if Visit.query.count() > 0 else 0
        
        return {
            'patient_growth_rate': round(growth_rate, 2),
            'revenue_growth_rate': round(revenue_growth, 2),
            'avg_visit_duration': round(avg_visit_duration, 2),
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
        completed_appointments = Appointment.query.filter(Appointment.status == 'completed').count()
        appointment_rate = (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0
        
        # متوسط وقت الانتظار
        avg_wait_time = db.session.query(func.avg(Visit.duration)).scalar() or 0
        
        # معدل الرضا (محاكاة)
        satisfaction_rate = min(100, max(0, completion_rate + (100 - completion_rate) * 0.3))
        
        return {
            'completion_rate': round(completion_rate, 2),
            'appointment_rate': round(appointment_rate, 2),
            'avg_wait_time': round(avg_wait_time, 2),
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
            Payment.payment_date >= month_ago
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
        department_efficiency = db.session.query(
            func.count(Visit.id).label('visits'),
            func.avg(Visit.duration).label('avg_duration'),
            User.department_id
        ).join(User, Visit.doctor_id == User.id).group_by(User.department_id).all()
        
        # تحليل استخدام الموارد
        resource_utilization = {
            'total_doctors': User.query.filter(User.role == 'doctor').count(),
            'active_doctors': User.query.filter(
                User.role == 'doctor',
                User.last_login >= datetime.now() - timedelta(days=7)
            ).count(),
            'total_visits_today': Visit.query.filter(Visit.created_at >= datetime.now().date()).count()
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
        visit = Visit.query.get_or_404(visit_id)
        
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
        visit.force_payment_approved_at = datetime.utcnow()
        visit.payment_status = 'DEBT'  # تحديد كدين معتمد
        
        db.session.commit()
        
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
        flash(f'حدث خطأ: {str(e)}', 'error')
        return redirect(url_for('manager.force_payment_approvals'))

@manager_bp.route('/reject-force-payment/<int:visit_id>', methods=['POST'])
@login_required
@can_approve_force_payment
def reject_force_payment(visit_id):
    """رفض دفع قسري"""
    try:
        visit = Visit.query.get_or_404(visit_id)
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
        visit.payment_method = 'cash'  # تحويل لدفع نقدي
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
        flash(f'حدث خطأ: {str(e)}', 'error')
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


