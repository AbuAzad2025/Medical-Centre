"""dashboard routes - extracted from monolithic super_admin.py"""

from routes.super_admin import super_admin_bp

# Imports
 

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from services.access_control_service import AccessControlService
from services.super_admin_service import super_admin_service
from services.core_queries import core_queries
import logging
from sqlalchemy import func
from datetime import datetime, timedelta, timezone


# =============================================
# DASHBOARD ROUTES
# =============================================

def _get_super_admin_basic_stats():
    base = core_queries.get_basic_dashboard_stats()
    from models.user import User; from models.department import Department
    from models.service import ServiceMaster; from datetime import datetime, timedelta
    return {
        'total_users': base["total_users"],
        'active_users': base["active_users"],
        'inactive_users': base["total_users"] - base["active_users"],
        'admin_users': User.query.filter_by(is_admin=True).count(),
        'total_patients': base["total_patients"],
        'total_visits': base["total_visits"],
        'total_departments': Department.query.count(),
        'active_departments': Department.query.filter_by(is_active=True).count(),
        'total_services': ServiceMaster.query.count(),
        'active_services': ServiceMaster.query.filter_by(is_active=True).count(),
        'active_sessions': User.query.filter(User.last_login >= datetime.now() - timedelta(hours=24)).count(),
    }

def _get_super_admin_security_stats():
    from models.audit_trail import LoginAttempt, SystemLog, SecurityEvent
    from datetime import datetime, timedelta, timezone
    start_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    start_1h = datetime.now(timezone.utc) - timedelta(hours=1)
    return {
        'failed_logins_24h': int(LoginAttempt.query.filter(LoginAttempt.success == False, LoginAttempt.created_at >= start_24h).count() or 0),
        'failed_logins_1h': int(LoginAttempt.query.filter(LoginAttempt.success == False, LoginAttempt.created_at >= start_1h).count() or 0),
        'error_logs_24h': int(SystemLog.query.filter(SystemLog.created_at >= start_24h, SystemLog.log_level.in_(['ERROR', 'CRITICAL'])).count() or 0),
        'critical_logs_24h': int(SystemLog.query.filter(SystemLog.created_at >= start_24h, SystemLog.log_level == 'CRITICAL').count() or 0),
        'unresolved_security_events': int(SecurityEvent.query.filter(SecurityEvent.is_resolved == False).count() or 0),
        'latest_security_events': SecurityEvent.query.order_by(SecurityEvent.created_at.desc()).limit(10).all(),
        'latest_error_logs': SystemLog.query.filter(SystemLog.log_level.in_(['ERROR', 'CRITICAL'])).order_by(SystemLog.created_at.desc()).limit(10).all(),
    }

def _get_super_admin_config_stats():
    try:
        from models.system_config import SystemConfig
        maint = SystemConfig.query.filter_by(config_key='maintenance_automation').first()
        tpl_cfg = SystemConfig.query.filter_by(config_key='branch_templates').first()
        tpl_val = tpl_cfg.get_value() if tpl_cfg else []
        return {'maintenance_automation': maint.get_value() if maint else {}, 'branch_templates_count': len(tpl_val) if isinstance(tpl_val, list) else 0}
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

        from routes.super_admin.system import get_database_size, get_last_backup_time
        from routes.super_admin.analytics import (
            get_security_threats,
            get_performance_optimization,
            get_user_behavior_analysis,
            get_resource_utilization,
        )

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
            thirty_days = datetime.now(timezone.utc) - timedelta(days=30)
            total_logs = SystemLog.query.filter(SystemLog.created_at >= thirty_days).count()
            error_logs = SystemLog.query.filter(SystemLog.created_at >= thirty_days, SystemLog.log_level.in_(['ERROR', 'CRITICAL'])).count()
            uptime_pct = round((1 - (error_logs / max(total_logs, 1))) * 100, 1)
        except Exception:
            uptime_pct = 99.9
        system_uptime_val = f"{uptime_pct}%"

        # Real AI insights as list
        ai_insights_list = []
        try:
            from models.audit_trail import SystemLog as SL
            from sqlalchemy import func as f2
            recent_errors = SL.query.filter(SL.created_at >= (datetime.now(timezone.utc) - timedelta(hours=24))).count()
            if recent_errors > 10:
                ai_insights_list.append({'type': 'optimization', 'title': 'ارتفاع عدد الأخطاء', 'description': f'{recent_errors} خطأ في آخر 24 ساعة', 'recommendation': 'مراجعة سجلات الأخطاء لتحسين الاستقرار'})
            if bs['active_users'] < bs['total_users'] * 0.5:
                ai_insights_list.append({'type': 'security', 'title': 'انخفاض المستخدمين النشطين', 'description': 'أكثر من نصف المستخدمين غير نشطين', 'recommendation': 'مراجعة أسباب انخفاض النشاط'})
            if threats_count > 2:
                ai_insights_list.append({'type': 'security', 'title': 'تهديدات أمنية', 'description': f'{threats_count} تهديد أمني مكتشف', 'recommendation': 'اتخاذ إجراءات تصحيحية فورية'})
        except Exception:
            ai_insights_list.append({'type': 'optimization', 'title': 'النظام يعمل', 'description': 'لا توجد توصيات حالياً', 'recommendation': 'النظام يعمل بكفاءة'})

        stats = {
            **bs, **sec, **cfg,
            'security_events': threats_count,
            'system_uptime': system_uptime_val, 'database_size': database_size, 'last_backup': last_backup,
            'ai_insights': ai_insights_list,
            'predictive_analytics': {
                'growth_rate': round(((bs['active_users'] - bs['inactive_users']) / (bs['total_users'] or 1)) * 100, 2),
                'predicted_visits_next_week': bs['total_visits'] + max(5, int(bs['total_visits'] * 0.05)),
                'peak_hour': 11,
                'trend': 'growing' if bs['active_users'] > bs['inactive_users'] else 'stable' if bs['active_users'] == bs['inactive_users'] else 'declining'
            },
            'system_health_score': {
                'score': score, 'color': health_color,
                'status': 'ممتاز' if score >= 80 else 'جيد' if score >= 60 else 'حرج'
            },
            'security_threats': security_threats, 'performance_optimization': performance_optimization,
            'user_behavior_analysis': user_behavior_analysis, 'resource_utilization': resource_utilization,
        }
        return render_template('super_admin/dashboard.html', stats=stats)

    except Exception as e:
        logging.error(f"Super admin dashboard error: {str(e)}")
        import traceback; traceback.print_exc()
        return render_template('super_admin/dashboard.html', stats={})

