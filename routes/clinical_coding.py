"""
Clinical Coding Routes — ICD-10, CPT, DRG management
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.icd_coding import ICD10Code, CPTCode, DRGCode, CodedDiagnosis, CodedProcedure
from models.patient import Patient
from models.visit import Visit
from models.medical_record import MedicalRecord
from models.user import User
from app_factory import db
import logging

clinical_coding_bp = Blueprint('clinical_coding', __name__)

@clinical_coding_bp.route('/icd10')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def icd10_list():
    q = request.args.get('q', '').strip()
    query = ICD10Code.query.filter_by(is_active=True)
    if q:
        query = query.filter(
            db.or_(
                ICD10Code.code.ilike(f'%{q}%'),
                ICD10Code.description.ilike(f'%{q}%'),
                ICD10Code.description_ar.ilike(f'%{q}%')
            )
        )
    codes = query.order_by(ICD10Code.code).limit(200).all()
    return render_template('clinical_coding/icd10_list.html', codes=codes, q=q)

@clinical_coding_bp.route('/icd10/<int:id>')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def icd10_detail(id):
    code = ICD10Code.query.get_or_404(id)
    return render_template('clinical_coding/icd10_detail.html', code=code)

@clinical_coding_bp.route('/cpt')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def cpt_list():
    q = request.args.get('q', '').strip()
    query = CPTCode.query.filter_by(is_active=True)
    if q:
        query = query.filter(
            db.or_(
                CPTCode.code.ilike(f'%{q}%'),
                CPTCode.description.ilike(f'%{q}%')
            )
        )
    codes = query.order_by(CPTCode.code).limit(200).all()
    return render_template('clinical_coding/cpt_list.html', codes=codes, q=q)

@clinical_coding_bp.route('/drg')
@login_required
@role_required('admin', 'manager', 'accountant')
@handle_route_errors
def drg_list():
    q = request.args.get('q', '').strip()
    query = DRGCode.query.filter_by(is_active=True)
    if q:
        query = query.filter(
            db.or_(
                DRGCode.code.ilike(f'%{q}%'),
                DRGCode.description.ilike(f'%{q}%')
            )
        )
    codes = query.order_by(DRGCode.code).limit(200).all()
    return render_template('clinical_coding/drg_list.html', codes=codes, q=q)

@clinical_coding_bp.route('/patient/<int:patient_id>/diagnoses')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def patient_diagnoses(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    diagnoses = CodedDiagnosis.query.filter_by(patient_id=patient_id).order_by(
        CodedDiagnosis.created_at.desc()
    ).all()
    return render_template('clinical_coding/patient_diagnoses.html',
                           patient=patient, diagnoses=diagnoses)

@clinical_coding_bp.route('/patient/<int:patient_id>/procedures')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def patient_procedures(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    procedures = CodedProcedure.query.filter_by(patient_id=patient_id).order_by(
        CodedProcedure.created_at.desc()
    ).all()
    return render_template('clinical_coding/patient_procedures.html',
                           patient=patient, procedures=procedures)

@clinical_coding_bp.route('/api/icd10/search')
@login_required
@handle_route_errors
def api_icd10_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    codes = ICD10Code.query.filter(
        db.or_(
            ICD10Code.code.ilike(f'%{q}%'),
            ICD10Code.description.ilike(f'%{q}%')
        ),
        ICD10Code.is_active == True
    ).limit(20).all()
    return jsonify([{'id': c.id, 'code': c.code, 'text': f"{c.code} - {c.description}"} for c in codes])

@clinical_coding_bp.route('/api/cpt/search')
@login_required
@handle_route_errors
def api_cpt_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    codes = CPTCode.query.filter(
        db.or_(
            CPTCode.code.ilike(f'%{q}%'),
            CPTCode.description.ilike(f'%{q}%')
        ),
        CPTCode.is_active == True
    ).limit(20).all()
    return jsonify([{'id': c.id, 'code': c.code, 'text': f"{c.code} - {c.description}"} for c in codes])
