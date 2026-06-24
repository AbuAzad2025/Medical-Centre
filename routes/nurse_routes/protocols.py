"""protocols routes - extracted from monolithic nurse_routes.py"""

from routes.nurse_routes import (
    nurse_bp,
    _get_nursing_protocols,
    _default_nursing_protocols,
    _save_nursing_protocols,
)

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from services.nursing_service import nursing_service
from app_factory import db
from app.shared.enums import TaskState
import logging, json
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import func, and_, or_, desc


# =============================================
# PROTOCOLS ROUTES
# =============================================

@nurse_bp.route('/api/protocols', methods=['GET', 'POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
def api_nursing_protocols():
    if request.method == 'GET':
        return jsonify({'success': True, 'items': _get_nursing_protocols()}), 200
    data = request.get_json(silent=True) or {}
    items = data.get('items') or []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = (item.get('title') or '').strip()
        if not title:
            continue
        steps = item.get('steps') or []
        if isinstance(steps, str):
            steps = [s.strip() for s in steps.split(',') if s.strip()]
        normalized.append({
            'id': item.get('id') or f"p_{len(normalized) + 1}",
            'title': title,
            'steps': steps
        })
    if not normalized:
        normalized = _default_nursing_protocols()
    _save_nursing_protocols(normalized)
    return jsonify({'success': True, 'items': normalized}), 200

# ==================== الميزات الذكية للتمريض ====================

@nurse_bp.route('/reports')
@login_required
@role_required('nurse', 'admin', 'manager')
def reports():
    try:
        from models.task_management import Task
        from models.user import User
        from models.department import Department

        start_raw = (request.args.get('start_date') or '').strip()
        end_raw = (request.args.get('end_date') or '').strip()
        try:
            start_date = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else (date.today() - timedelta(days=30))
        except Exception:
            start_date = date.today() - timedelta(days=30)
        try:
            end_date = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else date.today()
        except Exception:
            end_date = date.today()

        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        base_q = db.session.query(Task, User).join(User, User.id == Task.assigned_to).filter(
            User.role == 'nurse',
            Task.created_at >= start_dt,
            Task.created_at <= end_dt
        )

        total_tasks = base_q.with_entities(func.count(Task.id)).scalar() or 0
        completed_tasks = base_q.with_entities(func.count(Task.id)).filter(Task.status == TaskState.COMPLETED).scalar() or 0
        overdue_tasks = base_q.with_entities(func.count(Task.id)).filter(Task.due_date.isnot(None), Task.due_date < now, Task.status.in_([TaskState.PENDING, TaskState.IN_PROGRESS, 'on_hold'])).scalar() or 0
        urgent_tasks = base_q.with_entities(func.count(Task.id)).filter(Task.priority == 'urgent').scalar() or 0

        by_status = db.session.query(Task.status, func.count(Task.id)).join(User, User.id == Task.assigned_to).filter(
            User.role == 'nurse',
            Task.created_at >= start_dt,
            Task.created_at <= end_dt
        ).group_by(Task.status).all()
        by_priority = db.session.query(Task.priority, func.count(Task.id)).join(User, User.id == Task.assigned_to).filter(
            User.role == 'nurse',
            Task.created_at >= start_dt,
            Task.created_at <= end_dt
        ).group_by(Task.priority).all()

        by_department = db.session.query(
            Department.name_ar,
            func.count(Task.id)
        ).join(
            User, User.id == Task.assigned_to
        ).outerjoin(
            Department, Department.id == User.department_id
        ).filter(
            User.role == 'nurse',
            Task.created_at >= start_dt,
            Task.created_at <= end_dt
        ).group_by(Department.name_ar).all()

        top_overdue = base_q.filter(
            Task.due_date.isnot(None),
            Task.due_date < now,
            Task.status.in_([TaskState.PENDING, TaskState.IN_PROGRESS, 'on_hold'])
        ).order_by(Task.due_date.asc()).limit(25).all()

        rows = []
        for t, u in top_overdue:
            rows.append({
                'title': t.title,
                'nurse_name': u.full_name if u else '',
                'priority': t.priority,
                'status': t.status,
                'due_date': t.due_date,
            })

        return render_template(
            'nurse/reports.html',
            start_date=start_date,
            end_date=end_date,
            total_tasks=int(total_tasks),
            completed_tasks=int(completed_tasks),
            overdue_tasks=int(overdue_tasks),
            urgent_tasks=int(urgent_tasks),
            by_status=by_status,
            by_priority=by_priority,
            by_department=by_department,
            overdue_rows=rows
        )
    except Exception as e:
        logging.error(f"Error loading nurse reports: {str(e)}")
        flash('حدث خطأ في تحميل تقرير التمريض', 'error')
        return redirect(url_for('nurse.dashboard'))
