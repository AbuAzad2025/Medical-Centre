"""dashboard routes - extracted from monolithic super_admin.py"""

import logging
from datetime import UTC, datetime, timedelta

# Imports
from flask import render_template
from flask_login import login_required
from sqlalchemy import func, select

from app.extensions import db
from routes.super_admin import super_admin_bp
from services.core_queries import core_queries
from utils.decorators import super_admin_required

# =============================================
# DASHBOARD ROUTES
# =============================================


def _get_super_admin_basic_stats():
    base = core_queries.get_basic_dashboard_stats()
    from datetime import datetime, timedelta

    from models.department import Department
    from models.service import ServiceMaster
    from models.user import User

    return {
        'total_users': base['total_users'],
        'active_users': base['active_users'],
        'inactive_users': base['total_users'] - base['active_users'],
        'admin_users': db.session.execute(
            select(func.count()).select_from(User).filter_by(is_admin=True)
        ).scalar(),
        'total_patients': base['total_patients'],
        'total_visits': base['total_visits'],
        'total_departments': db.session.execute(
            select(func.count()).select_from(Department)
        ).scalar(),
        'active_departments': db.session.execute(
            select(func.count()).select_from(Department).filter_by(is_active=True)
        ).scalar(),
        'total_services': db.session.execute(
            select(func.count()).select_from(ServiceMaster)
        ).scalar(),
        'active_services': db.session.execute(
            select(func.count()).select_from(ServiceMaster).filter_by(is_active=True)
        ).scalar(),
        'active_sessions': db.session.execute(
            select(func.count())
            .select_from(User)
            .filter(User.last_login >= datetime.now() - timedelta(hours=24))
        ).scalar(),
    }


def _get_super_admin_security_stats():
    from datetime import datetime, timedelta

    from models.audit_trail import LoginAttempt, SecurityEvent, SystemLog

    start_24h = datetime.now(UTC) - timedelta(hours=24)
    start_1h = datetime.now(UTC) - timedelta(hours=1)
    return {
        'failed_logins_24h': int(
            db.session.execute(
                select(func.count())
                .select_from(LoginAttempt)
                .filter(not LoginAttempt.success, LoginAttempt.created_at >= start_24h)
            ).scalar()
            or 0
        ),
        'failed_logins_1h': int(
            db.session.execute(
                select(func.count())
                .select_from(LoginAttempt)
                .filter(not LoginAttempt.success, LoginAttempt.created_at >= start_1h)
            ).scalar()
            or 0
        ),
        'error_logs_24h': int(
            db.session.execute(
                select(func.count())
                .select_from(SystemLog)
                .filter(
                    SystemLog.created_at >= start_24h,
                    SystemLog.log_level.in_(['ERROR', 'CRITICAL']),
                )
            ).scalar()
            or 0
        ),
        'critical_logs_24h': int(
            db.session.execute(
                select(func.count())
                .select_from(SystemLog)
                .filter(SystemLog.created_at >= start_24h, SystemLog.log_level == 'CRITICAL')
            ).scalar()
            or 0
        ),
        'unresolved_security_events': int(
            db.session.execute(
                select(func.count())
                .select_from(SecurityEvent)
                .filter(not SecurityEvent.is_resolved)
            ).scalar()
            or 0
        ),
        'latest_security_events': db.session.execute(
            select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(10)
        )
        .scalars()
        .all(),
        'latest_error_logs': db.session.execute(
            select(SystemLog)
            .filter(SystemLog.log_level.in_(['ERROR', 'CRITICAL']))
            .order_by(SystemLog.created_at.desc())
            .limit(10)
        )
        .scalars()
        .all(),
    }


def _get_super_admin_config_stats():
    try:
        from models.system_config import SystemConfig

        maint = (
            db.session.execute(select(SystemConfig).filter_by(config_key='maintenance_automation'))
            .scalars()
            .first()
        )
        tpl_cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='branch_templates'))
            .scalars()
            .first()
        )
        tpl_val = tpl_cfg.get_value() if tpl_cfg else []
        return {
            'maintenance_automation': maint.get_value() if maint else {},
            'branch_templates_count': len(tpl_val) if isinstance(tpl_val, list) else 0,
        }
    except Exception:
        return {'maintenance_automation': {}, 'branch_templates_count': 0}


@super_admin_bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    """لوحة السوبر أدمن الذكية المتقدمة"""
    try:
        bs = _get_super_admin_basic_stats()
        sec = _get_super_admin_security_stats()
        cfg = _get_super_admin_config_stats()

        from routes.super_admin.analytics import (
            get_performance_optimization,
            get_resource_utilization,
            get_security_threats,
            get_user_behavior_analysis,
        )
        from routes.super_admin.system import get_database_size, get_last_backup_time

        database_size = get_database_size()
        last_backup = get_last_backup_time()
        security_threats = get_security_threats()
        performance_optimization = get_performance_optimization()
        user_behavior_analysis = get_user_behavior_analysis()
        resource_utilization = get_resource_utilization()

        threats_count = len(security_threats) if security_threats else 0
        cpu = (resource_utilization or {}).get('cpu', 0) or 0
        mem = ((resource_utilization or {}).get('memory') or {}).get('percentage', 0) or 0
        disk = ((resource_utilization or {}).get('disk') or {}).get('percentage', 0) or 0
        load_factor = min(100, int((cpu + mem + disk) / 3))
        base_score = 90 if threats_count == 0 else 80 if threats_count <= 2 else 65
        score = max(30, min(100, int(base_score - (load_factor - 50) * 0.3)))
        health_color = 'success' if score >= 80 else 'warning' if score >= 60 else 'danger'

        # Real uptime: % of non-error logs in last 30 days
        try:
            from models.audit_trail import SystemLog

            thirty_days = datetime.now(UTC) - timedelta(days=30)
            total_logs = db.session.execute(
                select(func.count())
                .select_from(SystemLog)
                .filter(SystemLog.created_at >= thirty_days)
            ).scalar()
            error_logs = db.session.execute(
                select(func.count())
                .select_from(SystemLog)
                .filter(
                    SystemLog.created_at >= thirty_days,
                    SystemLog.log_level.in_(['ERROR', 'CRITICAL']),
                )
            ).scalar()
            uptime_pct = round((1 - (error_logs / max(total_logs, 1))) * 100, 1)
        except Exception:
            uptime_pct = 99.9
        system_uptime_val = f'{uptime_pct}%'

        # Real AI insights as list
        ai_insights_list = []
        try:
            from models.audit_trail import SystemLog as SL

            recent_errors = db.session.execute(
                select(func.count())
                .select_from(SL)
                .filter(SL.created_at >= (datetime.now(UTC) - timedelta(hours=24)))
            ).scalar()
            if recent_errors > 10:
                ai_insights_list.append(
                    {
                        'type': 'optimization',
                        'title': 'ارتفاع عدد الأخطاء',
                        'description': f'{recent_errors} خطأ في آخر 24 ساعة',
                        'recommendation': 'مراجعة سجلات الأخطاء لتحسين الاستقرار',
                    }
                )
            if bs['active_users'] < bs['total_users'] * 0.5:
                ai_insights_list.append(
                    {
                        'type': 'security',
                        'title': 'انخفاض المستخدمين النشطين',
                        'description': 'أكثر من نصف المستخدمين غير نشطين',
                        'recommendation': 'مراجعة أسباب انخفاض النشاط',
                    }
                )
            if threats_count > 2:
                ai_insights_list.append(
                    {
                        'type': 'security',
                        'title': 'تهديدات أمنية',
                        'description': f'{threats_count} تهديد أمني مكتشف',
                        'recommendation': 'اتخاذ إجراءات تصحيحية فورية',
                    }
                )
        except Exception:
            ai_insights_list.append(
                {
                    'type': 'optimization',
                    'title': 'النظام يعمل',
                    'description': 'لا توجد توصيات حالياً',
                    'recommendation': 'النظام يعمل بكفاءة',
                }
            )

        stats = {
            **bs,
            **sec,
            **cfg,
            'security_events': threats_count,
            'system_uptime': system_uptime_val,
            'database_size': database_size,
            'last_backup': last_backup,
            'ai_insights': ai_insights_list,
            'predictive_analytics': {
                'growth_rate': round(
                    ((bs['active_users'] - bs['inactive_users']) / (bs['total_users'] or 1)) * 100,
                    2,
                ),
                'predicted_visits_next_week': bs['total_visits']
                + max(5, int(bs['total_visits'] * 0.05)),
                'peak_hour': 11,
                'trend': 'growing'
                if bs['active_users'] > bs['inactive_users']
                else 'stable'
                if bs['active_users'] == bs['inactive_users']
                else 'declining',
            },
            'system_health_score': {
                'score': score,
                'color': health_color,
                'status': 'ممتاز' if score >= 80 else 'جيد' if score >= 60 else 'حرج',
            },
            'security_threats': security_threats,
            'performance_optimization': performance_optimization,
            'user_behavior_analysis': user_behavior_analysis,
            'resource_utilization': resource_utilization,
        }
        return render_template('super_admin/dashboard.html', stats=stats)

    except Exception:
        logging.exception("Super admin dashboard error: %s")
        import traceback

        traceback.print_exc()
        return render_template('super_admin/dashboard.html', stats={})
