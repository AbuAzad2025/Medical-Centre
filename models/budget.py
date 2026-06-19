from datetime import datetime, timezone, date
from app_factory import db

class Budget(db.Model):
    """نموذج الميزانية الشهرية - Budget vs Actual"""
    __tablename__ = 'budgets'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)

    # Budget targets
    revenue_target = db.Column(db.Numeric(14, 2), default=0)
    visits_target = db.Column(db.Integer, default=0)
    new_patients_target = db.Column(db.Integer, default=0)
    expenses_target = db.Column(db.Numeric(14, 2), default=0)

    # Notes
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)

    __table_args__ = (db.UniqueConstraint('year', 'month', 'department_id', name='uq_budget_month_dept'),)

    def to_dict(self):
        return {
            'id': self.id,
            'year': self.year,
            'month': self.month,
            'department_id': self.department_id,
            'revenue_target': float(self.revenue_target or 0),
            'visits_target': self.visits_target or 0,
            'new_patients_target': self.new_patients_target or 0,
            'expenses_target': float(self.expenses_target or 0),
            'notes': self.notes
        }

    @classmethod
    def get_or_create(cls, year, month, department_id=None, user_id=None):
        b = cls.query.filter_by(year=year, month=month, department_id=department_id).first()
        if not b:
            b = cls(year=year, month=month, department_id=department_id, created_by=user_id)
            db.session.add(b)
            db.session.commit()
        return b
