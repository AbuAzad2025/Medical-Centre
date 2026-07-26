"""
What-If Scenario Routes
"""
from sqlalchemy import select
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, manager_or_admin_only
from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
from models import WhatIfScenario, Department
from datetime import datetime, timezone

what_if_bp = Blueprint('what_if', __name__)



@what_if_bp.route('/')
@login_required
@handle_route_errors
def index():
    scenarios = db.session.execute(select(WhatIfScenario).order_by(WhatIfScenario.created_at.desc())).scalars().all()
    return render_template('what_if/index.html', scenarios=scenarios)


@what_if_bp.route('/new', methods=['GET', 'POST'])
@login_required
@manager_or_admin_only
@handle_route_errors
def new_scenario():
    if request.method == 'POST':
        scenario = WhatIfScenario(
            name=request.form.get('name', '').strip(),
            scenario_type=request.form.get('scenario_type', 'add_doctor'),
            description=request.form.get('description', ''),
            baseline_visits_per_day=request.form.get('baseline_visits_per_day', type=int),
            baseline_avg_wait_minutes=request.form.get('baseline_avg_wait_minutes', type=float),
            baseline_revenue_per_day=request.form.get('baseline_revenue_per_day', type=float),
            param_change_value=request.form.get('param_change_value', type=float),
            param_change_percent=request.form.get('param_change_percent', type=float),
            param_new_staff_count=request.form.get('param_new_staff_count', type=int),
            param_new_bed_count=request.form.get('param_new_bed_count', type=int),
            param_department_id=request.form.get('param_department_id', type=int),
            created_by=current_user.id
        )
        scenario.calculate_projections()
        db.session.add(scenario)
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        flash('تم إنشاء السيناريو وحساب التوقعات', 'success')
        return redirect(url_for('what_if.index'))
    departments = db.session.execute(select(Department)).scalars().all()
    return render_template('what_if/new.html', departments=departments)


@what_if_bp.route('/<int:scenario_id>')
@login_required
@handle_route_errors
def view_scenario(scenario_id):
    scenario = db.get_or_404(WhatIfScenario, scenario_id)
    return render_template('what_if/view.html', scenario=scenario)
