"""
DICOM / PACS Routes
"""

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.dicom_pacs import DICOMSeries, DICOMStudy
from models.patient import Patient
from utils.decorators import handle_route_errors, role_required
from utils.tenant_query import get_tenant_record

dicom_bp = Blueprint('dicom', __name__)


@dicom_bp.route('/studies')
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager')
@handle_route_errors
def studies():
    patient_id = request.args.get('patient_id', type=int)
    modality = request.args.get('modality')
    if patient_id:
        patient = get_tenant_record(Patient, patient_id)
        if not patient:
            abort(404)
    query = DICOMStudy.query
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if modality:
        query = query.filter_by(modality=modality)
    items = query.order_by(DICOMStudy.study_date.desc()).limit(200).all()
    return render_template('dicom/studies.html', studies=items)


@dicom_bp.route('/study/<int:study_id>')
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager')
@handle_route_errors
def study_detail(study_id):
    study = db.get_or_404(DICOMStudy, study_id)
    series = db.session.execute(select(DICOMSeries).filter_by(study_id=study_id)).scalars().all()
    return render_template('dicom/study_detail.html', study=study, series=series)


@dicom_bp.route('/viewer/<int:study_id>')
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager')
@handle_route_errors
def viewer(study_id):
    study = db.get_or_404(DICOMStudy, study_id)
    series = db.session.execute(select(DICOMSeries).filter_by(study_id=study_id)).scalars().all()
    return render_template('dicom/viewer.html', study=study, series=series)


@dicom_bp.route('/api/studies/patient/<int:patient_id>')
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager', 'super_admin')
@handle_route_errors
def api_patient_studies(patient_id):
    patient = get_tenant_record(Patient, patient_id)
    if not patient:
        abort(404)
    studies = (
        db.session.execute(
            select(DICOMStudy)
            .filter_by(patient_id=patient_id)
            .order_by(DICOMStudy.study_date.desc())
        )
        .scalars()
        .all()
    )
    return jsonify(
        [
            {
                'id': s.id,
                'study_uid': s.study_instance_uid,
                'modality': s.modality,
                'description': s.study_description,
                'study_date': s.study_date.isoformat() if s.study_date else None,
                'series_count': s.series_count,
                'status': s.status,
            }
            for s in studies
        ]
    )
