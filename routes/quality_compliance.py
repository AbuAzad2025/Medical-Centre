"""
Quality & Compliance Routes — مركزية إدارة الجودة والامتثال
"""

import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import EmergencyStatus, OrderState, VisitArchiveStatus
from utils.decorators import role_required, role_required_json

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
        today - timedelta(days=30)

        from models.audit_trail import AuditTrail
        from models.emergency import EmergencyCase
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from models.visit import Visit

        total_audits = db.session.execute(select(func.count()).select_from(AuditTrail)).scalar()
        audits_today = db.session.execute(
            select(func.count())
            .select_from(AuditTrail)
            .filter(func.date(AuditTrail.created_at) == today)
        ).scalar()
        audits_week = db.session.execute(
            select(func.count()).select_from(AuditTrail).filter(AuditTrail.created_at >= week_ago)
        ).scalar()
        security_events = db.session.execute(
            select(func.count())
            .select_from(AuditTrail)
            .filter(
                AuditTrail.action.in_(['login_failed', 'unauthorized_access', 'permission_denied'])
            )
        ).scalar()

        lab_requests_today = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(func.date(LabRequest.created_at) == today)
        ).scalar()
        lab_done_today = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(
                LabRequest.status == OrderState.DONE, func.date(LabRequest.completed_at) == today
            )
        ).scalar()
        lab_quality = round((lab_done_today / max(lab_requests_today, 1)) * 100, 1)

        rad_requests_today = db.session.execute(
            select(func.count())
            .select_from(RadiologyRequest)
            .filter(func.date(RadiologyRequest.created_at) == today)
        ).scalar()
        rad_done_today = db.session.execute(
            select(func.count())
            .select_from(RadiologyRequest)
            .filter(
                RadiologyRequest.status == OrderState.DONE,
                func.date(RadiologyRequest.updated_at) == today,
            )
        ).scalar()
        rad_quality = round((rad_done_today / max(rad_requests_today, 1)) * 100, 1)

        visits_today = db.session.execute(
            select(func.count()).select_from(Visit).filter(func.date(Visit.created_at) == today)
        ).scalar()
        completed_visits_today = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.archive_status == VisitArchiveStatus.ARCHIVED,
                Visit.completed_at >= datetime.combine(today, datetime.min.time()),
            )
        ).scalar()
        visit_quality = round((completed_visits_today / max(visits_today, 1)) * 100, 1)

        emergency_today = db.session.execute(
            select(func.count())
            .select_from(EmergencyCase)
            .filter(EmergencyCase.created_at >= today)
        ).scalar()
        emergency_completed_today = db.session.execute(
            select(func.count())
            .select_from(EmergencyCase)
            .filter(
                EmergencyCase.status == EmergencyStatus.COMPLETED,
                EmergencyCase.completed_at >= today,
            )
        ).scalar()
        emergency_quality = round((emergency_completed_today / max(emergency_today, 1)) * 100, 1)

        recent_audits = (
            db.session.execute(select(AuditTrail).order_by(AuditTrail.created_at.desc()).limit(10))
            .scalars()
            .all()
        )

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

        return render_template(
            'quality_compliance/dashboard.html', stats=stats, recent_audits=recent_audits
        )
    except Exception:
        logging.exception("Error in quality dashboard: %s")
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
        return render_template(
            'quality_compliance/audits.html', pagination=pagination, action_filter=action_filter
        )
    except Exception:
        logging.exception("Error in audits list: %s")
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
        stmt = select(AuditTrail).order_by(AuditTrail.created_at.desc())
        pagination = db.paginate(stmt, page=page, per_page=25, error_out=False)
        return render_template('quality_compliance/incidents.html', pagination=pagination)
    except Exception:
        logging.exception("Error in incidents list: %s")
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
            lab_data.append(
                db.session.execute(
                    select(func.count())
                    .select_from(LabRequest)
                    .filter(func.date(LabRequest.created_at) == d)
                ).scalar()
            )
            rad_data.append(
                db.session.execute(
                    select(func.count())
                    .select_from(RadiologyRequest)
                    .filter(func.date(RadiologyRequest.created_at) == d)
                ).scalar()
            )
            visit_data.append(
                db.session.execute(
                    select(func.count()).select_from(Visit).filter(func.date(Visit.created_at) == d)
                ).scalar()
            )

        return jsonify(
            {'labels': labels, 'lab': lab_data, 'radiology': rad_data, 'visits': visit_data}
        )
    except Exception as e:
        logging.exception("Error in quality metrics API: %s")
        return jsonify({'error': str(e)}), 500
