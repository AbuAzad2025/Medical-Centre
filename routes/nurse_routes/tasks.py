"""tasks routes - extracted from monolithic nurse_routes.py"""

from routes.nurse_routes import nurse_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from app.shared.enums import VisitState
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from services.nursing_service import nursing_service
from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
import logging, json
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import func, and_, or_, desc, select


# =============================================
# TASKS ROUTES
# =============================================

@nurse_bp.route('/tasks')
@login_required
@role_required('nurse', 'admin', 'manager')
def tasks():
    """مهام التمريض"""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    try:
        from models.task_management import Task
        vq = select(Visit).filter(Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]))
        if getattr(current_user, 'department_id', None):
            vq = vq.filter(Visit.department_id == current_user.department_id)
        active_visits = db.session.execute(vq.limit(50)).scalars().all()
        
        # جلب مهام الممرضة مع pagination
        task_query = select(Task).filter_by(assigned_to=current_user.id)
        
        total = db.session.execute(select(func.count()).select_from(task_query.subquery())).scalar() or 0
        pages = (total + per_page - 1) // per_page
        
        tasks = db.session.execute(task_query.offset((page - 1) * per_page).limit(per_page)).scalars().all()
        
    except Exception as e:
        logging.error(f"Error loading nurse tasks: {str(e)}")
        tasks = []
        active_visits = []
        total = 0
        pages = 0

    return render_template('nurse/tasks.html', tasks=tasks, active_visits=active_visits, now=datetime.now(timezone.utc),
                           page=page, pages=pages, total=total)


@nurse_bp.route('/tasks/create', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
def create_task():
    try:
        from models.task_management import Task

        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip() or None
        priority = (request.form.get('priority') or 'medium').strip().lower()
        due_raw = (request.form.get('due_date') or '').strip()
        visit_id = request.form.get('visit_id', type=int)

        if not title:
            flash('يرجى إدخال عنوان المهمة', 'warning')
            return redirect(url_for('nurse.tasks'))
        if priority not in {'low', 'medium', 'high', 'urgent'}:
            priority = 'medium'

        due_date = None
        if due_raw:
            try:
                due_date = datetime.strptime(due_raw, '%Y-%m-%dT%H:%M')
                due_date = due_date.replace(tzinfo=timezone.utc)
            except Exception as e:
                due_date = None

        related_entity_type = None
        related_entity_id = None
        if visit_id:
            v = db.session.execute(select(Visit).filter(Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id)).scalars().first()
            if v:
                related_entity_type = 'visit'
                related_entity_id = v.id

        db.session.add(Task(
            title=title,
            description=description,
            task_type='patient_care',
            status='pending',
            priority=priority,
            assigned_to=current_user.id,
            assigned_by=current_user.id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            due_date=due_date,
        ))
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        flash('تمت إضافة المهمة', 'success')
        return redirect(url_for('nurse.tasks'))
    except Exception as e:
        safe_rollback(db.session, error_message="database rollback")
        logging.error(f"Error creating nurse task: {str(e)}")
        flash('حدث خطأ أثناء إنشاء المهمة', 'error')
        return redirect(url_for('nurse.tasks'))


@nurse_bp.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
def update_task_status(task_id: int):
    try:
        from models.task_management import Task

        t = db.session.execute(select(Task).filter(Task.id == task_id, Task.tenant_id == current_user.tenant_id)).scalars().first()
        if not t:
            flash('المهمة غير موجودة', 'error')
            return redirect(url_for('nurse.tasks'))
        if current_user.role == 'nurse' and t.assigned_to != current_user.id:
            flash('ليس لديك صلاحية لتعديل هذه المهمة', 'error')
            return redirect(url_for('nurse.tasks'))

        status_val = (request.form.get('status') or '').strip().lower()
        allowed = {'pending', 'in_progress', 'completed', 'cancelled', 'on_hold'}
        if status_val not in allowed:
            flash('حالة غير صالحة', 'error')
            return redirect(url_for('nurse.tasks'))

        t.status = status_val
        if status_val == 'completed':
            t.completed_at = datetime.now(timezone.utc)
        else:
            t.completed_at = None
        t.updated_at = datetime.now(timezone.utc)
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        flash('تم تحديث الحالة', 'success')
        return redirect(url_for('nurse.tasks'))
    except Exception as e:
        safe_rollback(db.session, error_message="database rollback")
        logging.error(f"Error updating task status: {str(e)}")
        flash('حدث خطأ أثناء التحديث', 'error')
        return redirect(url_for('nurse.tasks'))
