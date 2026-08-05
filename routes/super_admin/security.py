"""security routes - extracted from monolithic super_admin.py"""

import logging
from datetime import UTC, datetime, timedelta

# Imports
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func, select

from app.extensions import db
from routes.super_admin import super_admin_bp
from utils.decorators import super_admin_required

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
        logging.exception(f'Security logs error: {e!s}')
        flash('حدث خطأ في تحميل سجلات الأمان', 'error')
        return redirect(url_for('super_admin.dashboard'))


@super_admin_bp.route('/audit-trail')
@login_required
@super_admin_required
def audit_trail():
    """سجل التدقيق - PHI Audit Log Viewer"""
    page = request.args.get('page', 1, type=int)
    per_page = 25

    # Filter parameters
    action_filter = request.args.get('action_filter', '')
    user_filter = request.args.get('user_filter', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    model_filter = request.args.get('model_filter', '')
    patient_id_filter = request.args.get('patient_id_filter', '')

    try:
        from datetime import datetime

        from sqlalchemy import func, select

        from models.phi_audit_log import PHIAuditLog
        from models.user import User

        query = select(PHIAuditLog)

        # Apply filters
        if action_filter:
            query = query.filter(PHIAuditLog.action == action_filter)
        if user_filter:
            query = query.filter(PHIAuditLog.actor_id == int(user_filter))
        if model_filter:
            query = query.filter(PHIAuditLog.target_model == model_filter)
        if patient_id_filter:
            # Join with target_id for patient-specific logs
            query = query.filter(PHIAuditLog.target_id == int(patient_id_filter))
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(PHIAuditLog.created_at >= dt_from)
            except ValueError:
                pass
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(PHIAuditLog.created_at <= dt_to)
            except ValueError:
                pass

        # Order by most recent first
        query = query.order_by(PHIAuditLog.created_at.desc())

        total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar()
        pages = (total + per_page - 1) // per_page

        audit_logs = (
            db.session.execute(query.offset((page - 1) * per_page).limit(per_page)).scalars().all()
        )

        # Get unique users for filter dropdown
        users = db.session.execute(select(User).order_by(User.full_name)).scalars().all()

        # Get unique actions and models for filter dropdowns
        actions = db.session.execute(select(PHIAuditLog.action).distinct()).scalars().all()
        models = db.session.execute(select(PHIAuditLog.target_model).distinct()).scalars().all()

    except Exception as e:
        logging.exception(f'PHI Audit trail error: {e!s}')
        audit_logs = []
        total = 0
        pages = 0
        users = []
        actions = []
        models = []

    audit_logs_json = [
        {
            'id': log.id,
            'timestamp': log.created_at.isoformat() if log.created_at else None,
            'actor': {'full_name': log.actor.full_name, 'id': log.actor.id} if log.actor else None,
            'action': log.action,
            'target_model': log.target_model,
            'target_id': log.target_id,
            'ip_address': log.ip_address,
            'changes': log.changes,
            'request_id': log.request_id,
        }
        for log in audit_logs
    ]

    return render_template(
        'super_admin/audit_trail.html',
        audit_logs=audit_logs,
        audit_logs_json=audit_logs_json,
        page=page,
        pages=pages,
        total=total,
        users=users,
        actions=actions,
        models=models,
        filters={
            'action_filter': action_filter,
            'user_filter': user_filter,
            'date_from': date_from,
            'date_to': date_to,
            'model_filter': model_filter,
            'patient_id_filter': patient_id_filter,
        },
    )


@super_admin_bp.route('/security-center')
@login_required
@super_admin_required
def security_center():
    try:
        from models.audit_trail import LoginAttempt, SecurityEvent, SystemLog

        start_24h = datetime.now(UTC) - timedelta(hours=24)
        failed_logins = db.session.execute(
            select(func.count())
            .select_from(LoginAttempt)
            .filter(not LoginAttempt.success, LoginAttempt.created_at >= start_24h)
        ).scalar()
        critical_logs = db.session.execute(
            select(func.count())
            .select_from(SystemLog)
            .filter(
                SystemLog.log_level.in_(['ERROR', 'CRITICAL']), SystemLog.created_at >= start_24h
            )
        ).scalar()
        unresolved = db.session.execute(
            select(func.count())
            .select_from(SecurityEvent)
            .filter(not SecurityEvent.is_resolved)
        ).scalar()
        latest_events = (
            db.session.execute(
                select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(20)
            )
            .scalars()
            .all()
        )
        stats = {
            'failed_logins_24h': int(failed_logins or 0),
            'critical_logs_24h': int(critical_logs or 0),
            'unresolved_security_events': int(unresolved or 0),
            'latest_security_events': latest_events,
        }
        return render_template('super_admin/security_center.html', stats=stats)
    except Exception as e:
        logging.exception(f'Security center error: {e!s}')
        return render_template('super_admin/security_center.html', stats={})
