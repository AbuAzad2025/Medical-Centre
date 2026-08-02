"""analytics routes - extracted from monolithic super_admin.py"""

import logging
from datetime import UTC, date, datetime, timedelta

# Imports
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func, select

from app.extensions import db
from routes.super_admin import super_admin_bp
from utils.db_safety import safe_rollback
from utils.decorators import super_admin_required

# =============================================
# ANALYTICS ROUTES
# =============================================


@super_admin_bp.route('/performance')
@login_required
@super_admin_required
def performance():
    """مراقبة الأداء"""
    try:
        return render_template('super_admin/performance.html')
    except Exception as e:
        logging.exception(f'Performance monitoring error: {e!s}')
        flash('حدث خطأ في تحميل مراقبة الأداء', 'error')
        return redirect(url_for('super_admin.dashboard'))


@super_admin_bp.route('/reports')
@login_required
@super_admin_required
def reports():
    """مركز التقارير الموحد"""
    try:
        from models.department import Department
        from models.user import User
        from services.report_center_service import ReportCenterService

        report = (request.args.get('report') or '').strip()
        start_raw = request.args.get('start_date')
        end_raw = request.args.get('end_date')
        department_id = request.args.get('department_id', type=int)

        start_date, end_date, start_dt, end_dt = ReportCenterService._parse_dates(
            start_raw, end_raw
        )
        result = None

        if report == 'compare_month':
            now = date.today()
            a_start = datetime(now.year, now.month, 1, tzinfo=UTC)
            a_end = datetime(now.year, now.month, 1, tzinfo=UTC)
            if now.month == 12:
                a_end = datetime(now.year + 1, 1, 1, tzinfo=UTC) - timedelta(seconds=1)
            else:
                a_end = datetime(now.year, now.month + 1, 1, tzinfo=UTC) - timedelta(seconds=1)
            if now.month == 1:
                p_year, p_month = now.year - 1, 12
            else:
                p_year, p_month = now.year, now.month - 1
            b_start = datetime(p_year, p_month, 1, tzinfo=UTC)
            if p_month == 12:
                b_end = datetime(p_year + 1, 1, 1, tzinfo=UTC) - timedelta(seconds=1)
            else:
                b_end = datetime(p_year, p_month + 1, 1, tzinfo=UTC) - timedelta(seconds=1)
            result = {
                'compare': ReportCenterService.compare_periods(
                    a_start, a_end, b_start, b_end, department_id=department_id
                )
            }
        elif report == 'compare_year':
            now = date.today()
            a_start = datetime(now.year, 1, 1, tzinfo=UTC)
            a_end = datetime(now.year + 1, 1, 1, tzinfo=UTC) - timedelta(seconds=1)
            b_start = datetime(now.year - 1, 1, 1, tzinfo=UTC)
            b_end = datetime(now.year, 1, 1, tzinfo=UTC) - timedelta(seconds=1)
            result = {
                'compare': ReportCenterService.compare_periods(
                    a_start, a_end, b_start, b_end, department_id=department_id
                )
            }
        elif report == 'transfers':
            result = {'transfers': ReportCenterService.department_transfers(start_dt, end_dt)}
        elif report == 'capacity':
            result = {'capacity': ReportCenterService.capacity_impact(start_date, end_date)}
        elif report == 'booking':
            booking = ReportCenterService.booking_report(start_dt, end_dt)
            dept_names = {
                d.id: (d.name_ar or d.name)
                for d in db.session.execute(select(Department)).scalars().all()
            }
            doctor_names = {
                u.id: u.full_name
                for u in db.session.execute(select(User).filter_by(role='doctor')).scalars().all()
            }
            booking['top_departments_named'] = [
                {'label': dept_names.get(did) or 'غير محدد', 'count': cnt}
                for did, cnt in booking.get('top_departments', [])
            ]
            booking['top_doctors_named'] = [
                {'label': doctor_names.get(did) or 'غير محدد', 'count': cnt}
                for did, cnt in booking.get('top_doctors', [])
            ]
            result = {'booking': booking}
        elif report == 'emergency_times':
            result = {
                'emergency_times': ReportCenterService.emergency_stage_times(start_dt, end_dt)
            }
        elif report == 'radiology_revision':
            result = {
                'radiology_revision': ReportCenterService.radiology_revision_rate(start_dt, end_dt)
            }

        departments = (
            db.session.execute(select(Department).filter_by(is_active=True)).scalars().all()
        )
        return render_template(
            'super_admin/reports.html',
            report=report,
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            departments=departments,
            result=result,
        )
    except Exception as e:
        logging.exception(f'Reports error: {e!s}')
        return render_template(
            'super_admin/reports.html',
            report='',
            start_date=None,
            end_date=None,
            departments=[],
            result=None,
        )


@super_admin_bp.route('/analytics')
@login_required
@super_admin_required
def analytics():
    """التحليلات المتقدمة"""
    try:
        from models.patient import Patient
        from models.user import User
        from models.visit import Visit

        stats = {
            'total_users': db.session.execute(select(func.count()).select_from(User)).scalar(),
            'total_patients': db.session.execute(
                select(func.count()).select_from(Patient)
            ).scalar(),
            'total_visits': db.session.execute(select(func.count()).select_from(Visit)).scalar(),
        }
        return render_template('super_admin/analytics.html', stats=stats)
    except Exception as e:
        logging.exception(f'Analytics error: {e!s}')
        return render_template('super_admin/analytics.html', stats={})


# دوال مساعدة للإحصائيات
def get_total_users():
    """عدد المستخدمين الإجمالي"""
    try:
        from models.user import User

        return db.session.execute(select(func.count()).select_from(User)).scalar()
    except Exception as e:
        logging.exception(f'get_total_users failed: {e}')
        return 0


def get_active_sessions():
    """عدد الجلسات النشطة"""
    try:
        return get_active_users()
    except Exception as e:
        logging.exception(f'get_active_sessions failed: {e}')
        return 0


def get_security_events():
    """عدد أحداث الأمان"""
    try:
        from models.audit_trail import AuditTrail

        return db.session.execute(
            select(func.count())
            .select_from(AuditTrail)
            .filter(AuditTrail.action.in_(['login', 'logout', 'security']))
        ).scalar()
    except Exception as e:
        logging.exception(f'get_security_events failed: {e}')
        return 0


def get_system_uptime():
    """وقت تشغيل النظام"""
    return '99.9%'


def get_active_users():
    """عدد المستخدمين النشطين"""
    try:
        from models.user import User

        return db.session.execute(
            select(func.count()).select_from(User).filter_by(is_active=True)
        ).scalar()
    except Exception as e:
        logging.exception(f'get_active_users failed: {e}')
        return 0


def get_inactive_users():
    """عدد المستخدمين المعطلين"""
    try:
        from models.user import User

        return db.session.execute(
            select(func.count()).select_from(User).filter_by(is_active=False)
        ).scalar()
    except Exception as e:
        logging.exception(f'get_inactive_users failed: {e}')
        return 0


def get_admin_users():
    """عدد المستخدمين المديرين"""
    try:
        from models.user import User

        return db.session.execute(
            select(func.count()).select_from(User).filter_by(is_admin=True)
        ).scalar()
    except Exception as e:
        logging.exception(f'get_admin_users failed: {e}')
        return 0


def get_daily_usage():
    """استخدام النظام اليومي"""
    # يمكن تطوير هذا لاحقاً
    return [100, 95, 88, 92, 98]


# ==================== الميزات الذكية للسوبر أدمن ====================


def get_ai_insights():
    """رؤى الذكاء الاصطناعي للنظام"""
    try:
        from datetime import datetime, timedelta

        from models.ai_analytics import AIRecommendation

        insights = {
            'total_recommendations': db.session.execute(
                select(func.count()).select_from(AIRecommendation)
            ).scalar(),
            'pending_recommendations': db.session.execute(
                select(func.count())
                .select_from(AIRecommendation)
                .filter(AIRecommendation.is_accepted.is_(None))
            ).scalar(),
            'accepted_recommendations': db.session.execute(
                select(func.count())
                .select_from(AIRecommendation)
                .filter(AIRecommendation.is_accepted == True)
            ).scalar(),
            'high_confidence_recommendations': db.session.execute(
                select(func.count())
                .select_from(AIRecommendation)
                .filter(AIRecommendation.confidence_score >= 0.8)
            ).scalar(),
            'recent_insights': db.session.execute(
                select(func.count())
                .select_from(AIRecommendation)
                .filter(AIRecommendation.created_at >= datetime.now() - timedelta(days=7))
            ).scalar(),
        }

        return insights
    except Exception as e:
        logging.exception(f'Error getting AI insights: {e!s}')
        return {}


def get_smart_recommendations():
    """التوصيات الذكية للنظام"""
    try:
        from datetime import datetime, timedelta

        from models.user import User
        from models.visit import Visit

        recommendations = []

        # تحليل الأداء
        total_visits = db.session.execute(select(func.count()).select_from(Visit)).scalar()
        if total_visits > 100:
            recommendations.append(
                {
                    'type': 'performance',
                    'title': 'تحسين الأداء',
                    'description': f'تم تسجيل {total_visits} زيارة - النظام يعمل بكفاءة عالية',
                    'priority': 'info',
                }
            )

        # تحليل المستخدمين
        inactive_users = db.session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.last_login < datetime.now() - timedelta(days=30))
        ).scalar()

        if inactive_users > 5:
            recommendations.append(
                {
                    'type': 'users',
                    'title': 'إدارة المستخدمين',
                    'description': f'يوجد {inactive_users} مستخدم غير نشط - يحتاج مراجعة',
                    'priority': 'warning',
                }
            )

        # تحليل الأمان
        from models.audit_trail import AuditTrail

        failed_logins = db.session.execute(
            select(func.count())
            .select_from(AuditTrail)
            .filter(
                AuditTrail.action == 'login_failed',
                AuditTrail.created_at >= datetime.now() - timedelta(hours=24),
            )
        ).scalar()

        if failed_logins > 10:
            recommendations.append(
                {
                    'type': 'security',
                    'title': 'تنبيه أمني',
                    'description': f'محاولات تسجيل دخول فاشلة: {failed_logins} - يحتاج مراجعة',
                    'priority': 'danger',
                }
            )

        return recommendations
    except Exception as e:
        logging.exception(f'Error getting smart recommendations: {e!s}')
        return []


def get_predictive_analytics():
    """التحليلات التنبؤية"""
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import func

        from models.patient import Patient
        from models.visit import Visit

        # تحليل النمو
        week_ago = datetime.now() - timedelta(days=7)
        month_ago = datetime.now() - timedelta(days=30)

        patients_this_week = db.session.execute(
            select(func.count()).select_from(Patient).filter(Patient.created_at >= week_ago)
        ).scalar()
        patients_last_week = db.session.execute(
            select(func.count())
            .select_from(Patient)
            .filter(
                Patient.created_at >= week_ago - timedelta(days=7), Patient.created_at < week_ago
            )
        ).scalar()

        growth_rate = (
            ((patients_this_week - patients_last_week) / patients_last_week * 100)
            if patients_last_week > 0
            else 0
        )

        # التنبؤ بالزيارات
        visits_this_week = db.session.execute(
            select(func.count()).select_from(Visit).filter(Visit.created_at >= week_ago)
        ).scalar()
        predicted_next_week = int(visits_this_week * (1 + growth_rate / 100))

        # تحليل ساعات الذروة
        try:
            peak_hours = (
                db.session.execute(
                    select(
                        func.extract('hour', Visit.created_at).label('hour'),
                        func.count(Visit.id).label('count'),
                    ).group_by(func.extract('hour', Visit.created_at))
                )
                .scalars()
                .all()
            )
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            peak_hours = []

        peak_hour = max(peak_hours, key=lambda x: x.count) if peak_hours else None

        return {
            'growth_rate': round(growth_rate, 2),
            'predicted_visits_next_week': predicted_next_week,
            'peak_hour': peak_hour.hour if peak_hour else None,
            'peak_visits': peak_hour.count if peak_hour else 0,
            'trend': 'growing'
            if growth_rate > 0
            else 'stable'
            if growth_rate == 0
            else 'declining',
        }
    except Exception as e:
        logging.exception(f'Error getting predictive analytics: {e!s}')
        return {}


def get_system_health_score():
    """نقاط صحة النظام"""
    try:
        import os
        import shutil
        from datetime import datetime, timedelta

        from models.user import User

        score = 100

        # فحص قاعدة البيانات
        try:
            db.session.execute('SELECT 1')
        except Exception:
            score -= 20

        # فحص المساحة المتاحة
        try:
            disk_usage = shutil.disk_usage('/')
            free_space_percent = (disk_usage.free / disk_usage.total) * 100
            if free_space_percent < 10:
                score -= 20
            elif free_space_percent < 20:
                score -= 10
        except Exception:
            score -= 5

        # فحص الملفات المهمة
        critical_files = ['app.py', 'config.py', 'requirements.txt']
        for file in critical_files:
            if not os.path.exists(file):
                score -= 5

        # فحص المستخدمين النشطين
        active_users = db.session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.last_login >= datetime.now() - timedelta(days=7))
        ).scalar()
        if active_users == 0:
            score -= 15

        return {
            'score': max(0, score),
            'status': 'ممتاز' if score >= 90 else 'جيد' if score >= 70 else 'يحتاج انتباه',
            'color': 'success' if score >= 90 else 'warning' if score >= 70 else 'danger',
        }
    except Exception as e:
        logging.exception(f'Error getting system health score: {e!s}')
        return {'score': 0, 'status': 'غير محدد', 'color': 'secondary'}


def get_security_threats():
    """التهديدات الأمنية"""
    try:
        from datetime import datetime, timedelta

        from models.audit_trail import AuditTrail

        threats = []

        # محاولات تسجيل الدخول الفاشلة
        failed_logins = db.session.execute(
            select(func.count())
            .select_from(AuditTrail)
            .filter(
                AuditTrail.action == 'login_failed',
                AuditTrail.created_at >= datetime.now() - timedelta(hours=24),
            )
        ).scalar()

        if failed_logins > 20:
            threats.append(
                {
                    'type': 'high',
                    'title': 'محاولات تسجيل دخول مفرطة',
                    'description': f'{failed_logins} محاولة فاشلة في آخر 24 ساعة',
                    'action': 'مراجعة سجلات الأمان',
                }
            )
        elif failed_logins > 10:
            threats.append(
                {
                    'type': 'medium',
                    'title': 'محاولات تسجيل دخول عالية',
                    'description': f'{failed_logins} محاولة فاشلة في آخر 24 ساعة',
                    'action': 'مراقبة النشاط',
                }
            )

        # فحص الأنشطة المشبوهة
        suspicious_activities = db.session.execute(
            select(func.count())
            .select_from(AuditTrail)
            .filter(
                AuditTrail.action.in_(['unauthorized_access', 'privilege_escalation']),
                AuditTrail.created_at >= datetime.now() - timedelta(hours=24),
            )
        ).scalar()

        if suspicious_activities > 0:
            threats.append(
                {
                    'type': 'critical',
                    'title': 'أنشطة مشبوهة',
                    'description': f'{suspicious_activities} نشاط مشبوه تم اكتشافه',
                    'action': 'تحقيق فوري',
                }
            )

        return threats
    except Exception as e:
        logging.exception(f'Error getting security threats: {e!s}')
        return []


def get_performance_optimization():
    """تحسين الأداء"""
    try:
        from sqlalchemy import func

        from models.user import User
        from models.visit import Visit

        optimizations = []

        # تحليل ساعات الذروة
        try:
            peak_hours = (
                db.session.execute(
                    select(
                        func.extract('hour', Visit.created_at).label('hour'),
                        func.count(Visit.id).label('count'),
                    ).group_by(func.extract('hour', Visit.created_at))
                )
                .scalars()
                .all()
            )
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            peak_hours = []

        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 15:
                optimizations.append(
                    {
                        'type': 'load_balancing',
                        'title': 'توزيع الأحمال',
                        'description': f'ساعة الذروة: {max_hour.hour}:00 مع {max_hour.count} زيارة',
                        'suggestion': 'توزيع المواعيد على ساعات أخرى',
                    }
                )

        # تحليل الأداء حسب الأقسام
        department_load = (
            db.session.execute(
                select(func.count(Visit.id).label('count'), User.department_id)
                .join(User, Visit.doctor_id == User.id)
                .group_by(User.department_id)
            )
            .scalars()
            .all()
        )

        if department_load:
            max_dept = max(department_load, key=lambda x: x.count)
            if max_dept.count > 20:
                optimizations.append(
                    {
                        'type': 'resource_allocation',
                        'title': 'تخصيص الموارد',
                        'description': f'القسم {max_dept.department_id} يحتوي على {max_dept.count} زيارة',
                        'suggestion': 'إضافة موارد إضافية لهذا القسم',
                    }
                )

        return optimizations
    except Exception as e:
        logging.exception(f'Error getting performance optimization: {e!s}')
        return []


def get_user_behavior_analysis():
    """تحليل سلوك المستخدمين"""
    try:
        from datetime import datetime, timedelta

        from models.user import User

        analysis = {}

        # المستخدمون النشطون
        active_users = db.session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.last_login >= datetime.now() - timedelta(days=7))
        ).scalar()

        # المستخدمون غير النشطين
        inactive_users = db.session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.last_login < datetime.now() - timedelta(days=30))
        ).scalar()

        # تحليل الأدوار
        role_distribution = {}
        for user in db.session.execute(select(User)).scalars().all():
            role = user.role
            role_distribution[role] = role_distribution.get(role, 0) + 1

        # تحليل النشاط اليومي
        daily_activity = {}
        for user in select(User):
            day = user.last_login.strftime('%A')
            daily_activity[day] = daily_activity.get(day, 0) + 1

        return {
            'active_users': active_users,
            'inactive_users': inactive_users,
            'role_distribution': role_distribution,
            'daily_activity': daily_activity,
            'engagement_rate': (
                active_users
                / db.session.execute(select(func.count()).select_from(User)).scalar()
                * 100
            )
            if db.session.execute(select(func.count()).select_from(User)).scalar() > 0
            else 0,
        }
    except Exception as e:
        logging.exception(f'Error getting user behavior analysis: {e!s}')
        return {}


def get_resource_utilization():
    """استخدام الموارد"""
    try:
        try:
            import psutil

            memory = psutil.virtual_memory()
            memory_usage = {
                'total': memory.total,
                'used': memory.used,
                'free': memory.free,
                'percentage': memory.percent,
            }
            cpu_usage = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            disk_usage = {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percentage': (disk.used / disk.total) * 100,
            }
        except Exception:
            memory_usage = {'total': 0, 'used': 0, 'free': 0, 'percentage': 0}
            cpu_usage = 0
            disk_usage = {'total': 0, 'used': 0, 'free': 0, 'percentage': 0}

        # تحليل قاعدة البيانات
        from models.patient import Patient
        from models.user import User
        from models.visit import Visit

        db_stats = {
            'total_visits': db.session.execute(select(func.count()).select_from(Visit)).scalar(),
            'total_patients': db.session.execute(
                select(func.count()).select_from(Patient)
            ).scalar(),
            'total_users': db.session.execute(select(func.count()).select_from(User)).scalar(),
        }

        return {
            'memory': memory_usage,
            'cpu': cpu_usage,
            'disk': disk_usage,
            'database': db_stats,
            'status': 'optimal'
            if memory_usage['percentage'] < 80 and cpu_usage < 80
            else 'warning'
            if memory_usage['percentage'] < 90 and cpu_usage < 90
            else 'critical',
        }
    except Exception as e:
        logging.exception(f'Error getting resource utilization: {e!s}')
        return {}


@super_admin_bp.route('/system-monitor')
@login_required
@super_admin_required
def system_monitor():
    """مراقب النظام المتقدم"""
    try:
        import os

        try:
            import psutil

            drive = os.path.splitdrive(os.getcwd())[0]
            root_path = (drive + os.sep) if drive else os.path.abspath(os.sep)
            system_info = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage(root_path).percent,
                'process_count': len(psutil.pids()),
                'boot_time': psutil.boot_time(),
            }
        except Exception:
            system_info = {
                'cpu_percent': 0,
                'memory_percent': 0,
                'disk_usage': 0,
                'process_count': 0,
                'boot_time': 0,
            }

        return render_template('super_admin/system_monitor.html', system_info=system_info)

    except Exception as e:
        logging.exception(f'Error in system monitor: {e!s}')
        flash('حدث خطأ في مراقب النظام', 'error')
        return render_template('super_admin/system_monitor.html', system_info={})


# ============================================
# API Routes for AJAX Calls
# ============================================
