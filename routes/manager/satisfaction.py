"""satisfaction routes - extracted from monolithic manager.py"""

# Imports
from flask import render_template
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from routes.manager import manager_bp
from utils.decorators import (
    role_required,
)

# =============================================
# SATISFACTION ROUTES
# =============================================


@manager_bp.route('/patient-satisfaction')
@login_required
@role_required('manager', 'admin', 'super_admin')
def patient_satisfaction_dashboard():
    """لوحة رضا المرضى"""
    try:
        from models.patient_satisfaction import PatientSatisfactionSurvey

        surveys = (
            db.session.execute(
                select(PatientSatisfactionSurvey)
                .filter(PatientSatisfactionSurvey.tenant_id == current_user.tenant_id)
                .order_by(PatientSatisfactionSurvey.created_at.desc())
                .limit(100)
            )
            .scalars()
            .all()
        )
        total = len(surveys) if surveys else 0
        if total > 0:
            avg_score = sum(float(s.overall_satisfaction or 0) for s in surveys) / total
            avg_recommend = sum(float(s.recommend_likelihood or 0) for s in surveys) / total
            promoters = sum(1 for s in surveys if float(s.recommend_likelihood or 0) >= 9)
            detractors = sum(1 for s in surveys if float(s.recommend_likelihood or 0) <= 6)
            nps = round(((promoters - detractors) / total) * 100, 1)
        else:
            avg_score = avg_recommend = nps = 0
        return render_template(
            'manager/patient_satisfaction.html',
            surveys=surveys,
            total=total,
            avg_score=round(avg_score, 1),
            avg_recommend=round(avg_recommend, 1),
            nps=nps,
        )
    except Exception:
        return render_template(
            'manager/patient_satisfaction.html',
            surveys=[],
            total=0,
            avg_score=0,
            avg_recommend=0,
            nps=0,
        )
