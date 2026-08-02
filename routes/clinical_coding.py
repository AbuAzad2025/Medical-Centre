"""
Clinical Coding Routes — ICD-10, CPT, DRG management
"""

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.icd_coding import CodedDiagnosis, CodedProcedure, CPTCode, DRGCode, ICD10Code
from models.patient import Patient
from utils.decorators import handle_route_errors, role_required

clinical_coding_bp = Blueprint('clinical_coding', __name__)


@clinical_coding_bp.route('/icd10')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def icd10_list():
    q = request.args.get('q', '').strip()
    query = select(ICD10Code)
    if q:
        query = query.filter(
            db.or_(
                ICD10Code.code.ilike(f'%{q}%'),
                ICD10Code.description.ilike(f'%{q}%'),
                ICD10Code.description_ar.ilike(f'%{q}%'),
            )
        )
    codes = query.order_by(ICD10Code.code).limit(200).all()
    return render_template('clinical_coding/icd10_list.html', codes=codes, q=q)


@clinical_coding_bp.route('/icd10/<int:id>')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def icd10_detail(id):
    code = db.get_or_404(ICD10Code, id)
    return render_template('clinical_coding/icd10_detail.html', code=code)


@clinical_coding_bp.route('/cpt')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def cpt_list():
    q = request.args.get('q', '').strip()
    query = select(CPTCode)
    if q:
        query = query.filter(
            db.or_(CPTCode.code.ilike(f'%{q}%'), CPTCode.description.ilike(f'%{q}%'))
        )
    codes = query.order_by(CPTCode.code).limit(200).all()
    return render_template('clinical_coding/cpt_list.html', codes=codes, q=q)


@clinical_coding_bp.route('/drg')
@login_required
@role_required('admin', 'manager', 'accountant')
@handle_route_errors
def drg_list():
    q = request.args.get('q', '').strip()
    query = select(DRGCode)
    if q:
        query = query.filter(
            db.or_(DRGCode.code.ilike(f'%{q}%'), DRGCode.description.ilike(f'%{q}%'))
        )
    codes = query.order_by(DRGCode.code).limit(200).all()
    return render_template('clinical_coding/drg_list.html', codes=codes, q=q)


@clinical_coding_bp.route('/patient/<int:patient_id>/diagnoses')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def patient_diagnoses(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    diagnoses = (
        db.session.execute(
            select(CodedDiagnosis)
            .filter_by(patient_id=patient_id)
            .order_by(CodedDiagnosis.created_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template(
        'clinical_coding/patient_diagnoses.html', patient=patient, diagnoses=diagnoses
    )


@clinical_coding_bp.route('/patient/<int:patient_id>/procedures')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def patient_procedures(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    procedures = (
        db.session.execute(
            select(CodedProcedure)
            .filter_by(patient_id=patient_id)
            .order_by(CodedProcedure.created_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template(
        'clinical_coding/patient_procedures.html', patient=patient, procedures=procedures
    )


@clinical_coding_bp.route('/api/icd10/search')
@login_required
@handle_route_errors
def api_icd10_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    codes = (
        db.session.execute(
            select(ICD10Code)
            .filter(
                db.or_(ICD10Code.code.ilike(f'%{q}%'), ICD10Code.description.ilike(f'%{q}%')),
                ICD10Code.is_active == True,
            )
            .limit(20)
        )
        .scalars()
        .all()
    )
    return jsonify(
        [{'id': c.id, 'code': c.code, 'text': f'{c.code} - {c.description}'} for c in codes]
    )


@clinical_coding_bp.route('/api/cpt/search')
@login_required
@handle_route_errors
def api_cpt_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    codes = (
        db.session.execute(
            select(CPTCode)
            .filter(
                db.or_(CPTCode.code.ilike(f'%{q}%'), CPTCode.description.ilike(f'%{q}%')),
                CPTCode.is_active == True,
            )
            .limit(20)
        )
        .scalars()
        .all()
    )
    return jsonify(
        [{'id': c.id, 'code': c.code, 'text': f'{c.code} - {c.description}'} for c in codes]
    )
