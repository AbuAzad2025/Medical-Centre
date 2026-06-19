"""
What-If Scenario Engine for Manager Dashboard
"""
from datetime import datetime, timezone
from app_factory import db

class WhatIfScenario(db.Model):
    __tablename__ = 'what_if_scenarios'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    scenario_type = db.Column(db.String(50), nullable=False, index=True)
    # types: 'add_doctor', 'add_beds', 'extend_hours', 'seasonal_surge', 'price_change'

    # Baseline parameters
    baseline_visits_per_day = db.Column(db.Integer, nullable=True)
    baseline_avg_wait_minutes = db.Column(db.Numeric(6, 2), nullable=True)
    baseline_revenue_per_day = db.Column(db.Numeric(12, 2), nullable=True)
    baseline_staff_count = db.Column(db.Integer, nullable=True)

    # Scenario parameters (changes)
    param_change_value = db.Column(db.Numeric(12, 2), nullable=True)  # numeric change
    param_change_percent = db.Column(db.Numeric(6, 2), nullable=True)  # percentage change
    param_department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    param_new_staff_count = db.Column(db.Integer, nullable=True)
    param_new_bed_count = db.Column(db.Integer, nullable=True)

    # Projected results
    projected_visits_per_day = db.Column(db.Numeric(6, 2), nullable=True)
    projected_avg_wait_minutes = db.Column(db.Numeric(6, 2), nullable=True)
    projected_revenue_per_day = db.Column(db.Numeric(12, 2), nullable=True)
    projected_capacity_increase = db.Column(db.Numeric(6, 2), nullable=True)

    # Results summary
    result_summary = db.Column(db.Text, nullable=True)
    result_json = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    department = db.relationship('Department', lazy='selectin')
    creator = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<WhatIfScenario {self.name}>"

    def calculate_projections(self):
        """Simple what-if calculation engine"""
        if self.scenario_type == 'add_doctor' and self.baseline_visits_per_day and self.param_new_staff_count:
            # Assume each new doctor adds ~8 visits/day capacity
            additional = self.param_new_staff_count * 8
            self.projected_visits_per_day = self.baseline_visits_per_day + additional
            if self.baseline_avg_wait_minutes:
                # Wait time decreases proportionally
                ratio = self.baseline_visits_per_day / float(self.projected_visits_per_day)
                self.projected_avg_wait_minutes = float(self.baseline_avg_wait_minutes) * ratio
            if self.baseline_revenue_per_day:
                avg_revenue = float(self.baseline_revenue_per_day) / self.baseline_visits_per_day
                self.projected_revenue_per_day = float(self.projected_visits_per_day) * avg_revenue

        elif self.scenario_type == 'add_beds' and self.baseline_visits_per_day and self.param_new_bed_count:
            # Each bed allows ~0.5 additional visit/day (admission capacity)
            additional = self.param_new_bed_count * 0.5
            self.projected_visits_per_day = self.baseline_visits_per_day + additional
            if self.baseline_revenue_per_day:
                avg_revenue = float(self.baseline_revenue_per_day) / self.baseline_visits_per_day
                self.projected_revenue_per_day = float(self.projected_visits_per_day) * avg_revenue

        elif self.scenario_type == 'extend_hours' and self.param_change_percent:
            # Extending hours by X% increases capacity by X%
            factor = 1 + (float(self.param_change_percent) / 100)
            if self.baseline_visits_per_day:
                self.projected_visits_per_day = self.baseline_visits_per_day * factor
            if self.baseline_revenue_per_day:
                self.projected_revenue_per_day = float(self.baseline_revenue_per_day) * factor

        elif self.scenario_type == 'price_change' and self.param_change_percent:
            factor = 1 + (float(self.param_change_percent) / 100)
            # Assume 10% price elasticity: 10% price increase = 5% demand decrease
            elasticity = -0.5
            demand_factor = 1 + (float(self.param_change_percent) / 100) * elasticity
            if self.baseline_revenue_per_day:
                self.projected_revenue_per_day = float(self.baseline_revenue_per_day) * factor * demand_factor
            if self.baseline_visits_per_day:
                self.projected_visits_per_day = self.baseline_visits_per_day * demand_factor

        if self.baseline_visits_per_day and self.projected_visits_per_day:
            increase = (float(self.projected_visits_per_day) - self.baseline_visits_per_day) / self.baseline_visits_per_day
            self.projected_capacity_increase = increase * 100
