"""
Data Warehouse / Analytics Summary Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from utils.decorators import handle_route_errors
from app_factory import db
from models import DataWarehouseSync, DailyVisitSummary, MonthlyFinanceSummary, Visit
from sqlalchemy import func
from datetime import datetime, timezone

data_warehouse_bp = Blueprint('data_warehouse', __name__)



@data_warehouse_bp.route('/')
@login_required
@handle_route_errors
def dashboard():
    syncs = DataWarehouseSync.query.order_by(DataWarehouseSync.created_at.desc()).limit(20).all()
    daily = DailyVisitSummary.query.order_by(DailyVisitSummary.date.desc()).limit(30).all()
    monthly = MonthlyFinanceSummary.query.order_by(
        MonthlyFinanceSummary.year.desc(), MonthlyFinanceSummary.month.desc()
    ).limit(12).all()
    return render_template('data_warehouse/dashboard.html', syncs=syncs, daily=daily, monthly=monthly)


@data_warehouse_bp.route('/sync', methods=['POST'])
@login_required
@handle_route_errors
def sync():
    sync_name = request.form.get('sync_name', 'daily_visits_summary')
    sync_log = DataWarehouseSync(
        sync_name=sync_name,
        status='running',
        started_at=datetime.now(timezone.utc)
    )
    db.session.add(sync_log)
    db.session.commit()

    if sync_name == 'daily_visits_summary':
        today = datetime.now(timezone.utc).date()
        visits_today = Visit.query.filter(func.date(Visit.created_at) == today).all()
        summary = DailyVisitSummary.query.filter_by(date=today).first()
        if not summary:
            summary = DailyVisitSummary(date=today)
            db.session.add(summary)
        summary.total_visits = len(visits_today)

    sync_log.status = 'success'
    sync_log.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash('تمت المزامنة بنجاح', 'success')
    return redirect(url_for('data_warehouse.dashboard'))
