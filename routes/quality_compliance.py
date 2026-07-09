"""
Quality & Compliance Routes — مركزية إدارة الجودة والامتثال
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required, role_required_json
from app_factory import db
from datetime import datetime, date, timedelta
from sqlalchemy import func
import logging
from app.shared.enums import EmergencyStatus, OrderState, VisitState, VisitArchiveStatus

quality_bp = Blueprint('quality', __name__)

QUALITY_ROLES = ('manager', 'admin', 'super_admin')


@quality_bp.route('/dashboard')
@login_required
@role_required('manager', 'admin', 'super_admin')
def dashboard():
    """لوحة تحكم الجودة والامتثال المركزية"""
    try:
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        from models.audit_trail import AuditTrail
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from models.visit import Visit
        from models.emergency import EmergencyCase
        from models.user import User

        total_audits = AuditTrail.query.count()
        audits_today = AuditTrail.query.filter(
            func.date(AuditTrail.created_at) == today
        ).count()
        audits_week = AuditTrail.query.filter(
            AuditTrail.created_at >= week_ago
        ).count()
        security_events = AuditTrail.query.filter(
            AuditTrail.action.in_(['login_failed', 'unauthorized_access', 'permission_denied'])
        ).count()

        lab_requests_today = LabRequest.query.filter(
            func.date(LabRequest.created_at) == today
        ).count()
        lab_done_today = LabRequest.query.filter(
            LabRequest.status == OrderState.DONE,
            func.date(LabRequest.completed_at) == today
        ).count()
        lab_quality = round((lab_done_today / max(lab_requests_today, 1)) * 100, 1)

        rad_requests_today = RadiologyRequest.query.filter(
            func.date(RadiologyRequest.created_at) == today
        ).count()
        rad_done_today = RadiologyRequest.query.filter(
            RadiologyRequest.status == OrderState.DONE,
            func.date(RadiologyRequest.updated_at) == today
        ).count()
        rad_quality = round((rad_done_today / max(rad_requests_today, 1)) * 100, 1)

        visits_today = Visit.query.filter(
            func.date(Visit.created_at) == today
        ).count()
        completed_visits_today = Visit.query.filter(
            Visit.archive_status == VisitArchiveStatus.ARCHIVED,
            Visit.completed_at >= datetime.combine(today, datetime.min.time())
        ).count()
        visit_quality = round((completed_visits_today / max(visits_today, 1)) * 100, 1)

        emergency_today = EmergencyCase.query.filter(
            EmergencyCase.created_at >= today
        ).count()
        emergency_completed_today = EmergencyCase.query.filter(
            EmergencyCase.status == EmergencyStatus.COMPLETED,
            EmergencyCase.completed_at >= today
        ).count()
        emergency_quality = round((emergency_completed_today / max(emergency_today, 1)) * 100, 1)

        recent_audits = AuditTrail.query.order_by(
            AuditTrail.created_at.desc()
        ).limit(10).all()

        stats = {
            'total_audits': total_audits,
            'audits_today': audits_today,
            'audits_week': audits_week,
            'security_events': security_events,
            'lab_quality': lab_quality,
            'rad_quality': rad_quality,
            'visit_quality': visit_quality,
            'emergency_quality': emergency_quality,
        }

        return render_template('quality_compliance/dashboard.html',
                               stats=stats,
                               recent_audits=recent_audits)
    except Exception as e:
        logging.error(f"Error in quality dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة الجودة', 'error')
        return redirect(url_for('main.dashboard'))


@quality_bp.route('/audits')
@login_required
@role_required('manager', 'admin', 'super_admin')
def audits():
    """سجل التدقيق المركزي"""
    try:
        from models.audit_trail import AuditTrail
        page = request.args.get('page', 1, type=int)
        action_filter = request.args.get('action', '')

        q = AuditTrail.query
        if action_filter:
            q = q.filter(AuditTrail.action == action_filter)

        pagination = q.order_by(AuditTrail.created_at.desc()).paginate(
            page=page, per_page=25, error_out=False
        )
        return render_template('quality_compliance/audits.html',
                               pagination=pagination,
                               action_filter=action_filter)
    except Exception as e:
        logging.error(f"Error in audits list: {str(e)}")
        flash('حدث خطأ', 'error')
        return redirect(url_for('quality.dashboard'))


@quality_bp.route('/incidents')
@login_required
@role_required('manager', 'admin', 'super_admin')
def incidents():
    """إدارة الحوادث والأحداث السلبية (incidents placeholder)"""
    try:
        from models.audit_trail import AuditTrail
        page = request.args.get('page', 1, type=int)
        q = AuditTrail.query.filter(
            AuditTrail.action.in_([
                'login_failed', 'unauthorized_access',
                'permission_denied', 'force_logout'
            ])
        )
        pagination = q.order_by(AuditTrail.created_at.desc()).paginate(
            page=page, per_page=25, error_out=False
        )
        return render_template('quality_compliance/incidents.html',
                               pagination=pagination)
    except Exception as e:
        logging.error(f"Error in incidents list: {str(e)}")
        flash('حدث خطأ', 'error')
        return redirect(url_for('quality.dashboard'))


@quality_bp.route('/api/quality-metrics')
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def api_quality_metrics():
    """API لبيانات الجودة (للاستخدام في Charts)"""
    try:
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from models.visit import Visit
        today = date.today()
        week_ago = today - timedelta(days=7)

        labels = []
        lab_data = []
        rad_data = []
        visit_data = []

        for i in range(7):
            d = week_ago + timedelta(days=i)
            labels.append(d.strftime('%a'))
            lab_data.append(LabRequest.query.filter(
                func.date(LabRequest.created_at) == d
            ).count())
            rad_data.append(RadiologyRequest.query.filter(
                func.date(RadiologyRequest.created_at) == d
            ).count())
            visit_data.append(Visit.query.filter(
                func.date(Visit.created_at) == d
            ).count())

        return jsonify({
            'labels': labels,
            'lab': lab_data,
            'radiology': rad_data,
            'visits': visit_data
        })
    except Exception as e:
        logging.error(f"Error in quality metrics API: {str(e)}")
        return jsonify({'error': str(e)}), 500
