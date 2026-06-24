"""security routes - extracted from monolithic super_admin.py"""

from routes.super_admin import super_admin_bp

# Imports
 

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from services.access_control_service import AccessControlService
from services.super_admin_service import super_admin_service
import logging
from sqlalchemy import func


# =============================================
# SECURITY ROUTES
# =============================================

@super_admin_bp.route('/security-logs')
@login_required
@super_admin_required
def security_logs():
    """سجلات الأمان"""
    try:
        return render_template('super_admin/security_logs.html')
    except Exception as e:
        logging.error(f"Security logs error: {str(e)}")
        flash('حدث خطأ في تحميل سجلات الأمان', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/audit-trail')
@login_required
@super_admin_required
def audit_trail():
    """سجل التدقيق"""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    try:
        from models.audit_trail import AuditTrail
        query = AuditTrail.query.order_by(AuditTrail.created_at.desc())
        
        total = query.count()
        pages = (total + per_page - 1) // per_page
        
        audit_logs = query.offset((page - 1) * per_page).limit(per_page).all()
    except Exception as e:
        logging.error(f"Audit trail error: {str(e)}")
        audit_logs = []
        total = 0
        pages = 0

    audit_logs_json = [
        {
            'id': log.id,
            'timestamp': log.created_at.isoformat() if log.created_at else None,
            'user': {'full_name': log.user.full_name} if log.user else None,
            'action': log.action,
            'entity_type': log.entity_type,
            'description': log.description,
            'status': log.action,
        }
        for log in audit_logs
    ]

    return render_template('super_admin/audit_trail.html', audit_logs=audit_logs,
                           audit_logs_json=audit_logs_json, page=page, pages=pages, total=total)


@super_admin_bp.route('/security-center')
@login_required
@super_admin_required
def security_center():
    try:
        from models.audit_trail import LoginAttempt, SystemLog, SecurityEvent
        start_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        failed_logins = LoginAttempt.query.filter(LoginAttempt.success == False, LoginAttempt.created_at >= start_24h).count()
        critical_logs = SystemLog.query.filter(SystemLog.log_level.in_(['ERROR', 'CRITICAL']), SystemLog.created_at >= start_24h).count()
        unresolved = SecurityEvent.query.filter(SecurityEvent.is_resolved == False).count()
        latest_events = SecurityEvent.query.order_by(SecurityEvent.created_at.desc()).limit(20).all()
        stats = {
            'failed_logins_24h': int(failed_logins or 0),
            'critical_logs_24h': int(critical_logs or 0),
            'unresolved_security_events': int(unresolved or 0),
            'latest_security_events': latest_events
        }
        return render_template('super_admin/security_center.html', stats=stats)
    except Exception as e:
        logging.error(f"Security center error: {str(e)}")
        return render_template('super_admin/security_center.html', stats={})

