"""
Population Health Dashboard Routes
"""
from sqlalchemy import select
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.population_health import DiseaseRegistry, PopulationHealthIndicator, QualityMeasure
from models.icd_coding import ICD10Code
from models.patient import Patient
from app.extensions import db

pop_health_bp = Blueprint('pop_health', __name__)


@pop_health_bp.route('/dashboard')
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def dashboard():
    indicators = db.session.execute(select(PopulationHealthIndicator).order_by(
        PopulationHealthIndicator.created_at.desc()
    ).limit(20)).scalars().all()
    quality_measures = db.session.execute(select(QualityMeasure).filter_by(is_active=True)).scalars().all()
    return render_template('population_health/dashboard.html',
                           indicators=indicators, quality_measures=quality_measures)

@pop_health_bp.route('/disease-registry')
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def disease_registry():
    items = db.session.execute(select(DiseaseRegistry).order_by(DiseaseRegistry.created_at.desc()).limit(200)).scalars().all()
    return render_template('population_health/disease_registry.html', diseases=items)

@pop_health_bp.route('/quality-measures')
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def quality_measures():
    items = db.session.execute(select(QualityMeasure).filter_by(is_active=True).order_by(QualityMeasure.measure_code)).scalars().all()
    return render_template('population_health/quality_measures.html', measures=items)
