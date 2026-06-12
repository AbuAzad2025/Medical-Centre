"""
Data Warehouse / Analytics Summary Tables
"""
from datetime import datetime, timezone
from app_factory import db

class DataWarehouseSync(db.Model):
    __tablename__ = 'data_warehouse_syncs'

    id = db.Column(db.Integer, primary_key=True)
    sync_name = db.Column(db.String(100), nullable=False, index=True)
    # names: 'daily_visits_summary', 'monthly_finance_summary', etc.

    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    # pending | running | success | failed

    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    source_rows = db.Column(db.Integer, nullable=True)
    target_rows = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<DataWarehouseSync {self.sync_name} {self.status}>"


class DailyVisitSummary(db.Model):
    __tablename__ = 'dw_daily_visit_summary'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True, index=True)

    total_visits = db.Column(db.Integer, default=0, nullable=False)
    new_patients = db.Column(db.Integer, default=0, nullable=False)
    follow_up_visits = db.Column(db.Integer, default=0, nullable=False)
    emergency_visits = db.Column(db.Integer, default=0, nullable=False)

    avg_wait_minutes = db.Column(db.Numeric(6, 2), nullable=True)
    avg_visit_duration_minutes = db.Column(db.Numeric(6, 2), nullable=True)

    revenue_total = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    revenue_cash = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    revenue_insurance = db.Column(db.Numeric(12, 2), default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<DailyVisitSummary {self.date} visits={self.total_visits}>"


class MonthlyFinanceSummary(db.Model):
    __tablename__ = 'dw_monthly_finance_summary'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)

    total_invoices = db.Column(db.Integer, default=0, nullable=False)
    total_paid = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    total_outstanding = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    total_discounts = db.Column(db.Numeric(12, 2), default=0, nullable=False)

    revenue_by_department = db.Column(db.Text, nullable=True)  # JSON
    top_services = db.Column(db.Text, nullable=True)  # JSON

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='uq_dw_monthly_finance'),
    )

    def __repr__(self):
        return f"<MonthlyFinanceSummary {self.year}-{self.month}>"
