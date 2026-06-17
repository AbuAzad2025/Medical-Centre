"""fhir routes - extracted from monolithic radiology.py"""

from routes.radiology import radiology_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.radiology_request import RadiologyRequest
from models.radiology_test import RadiologyResult
from models.file_management import FileUpload
from models.system_config import SystemConfig
from app_factory import db
import logging, json, os, base64, secrets
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# FHIR ROUTES
# =============================================

@radiology_bp.route('/api/worklist')
@login_required
@role_required('radiology', 'technician', 'admin', 'manager', 'doctor', 'super_admin')
def api_worklist():
    try:
        visit_id = request.args.get('visit_id', type=int)
        status = request.args.get('status', type=str)
        q = RadiologyRequest.query
        if visit_id:
            q = q.filter(RadiologyRequest.visit_id == visit_id)
        if status:
            q = q.filter(RadiologyRequest.status == status)
        reqs = q.order_by(RadiologyRequest.created_at.desc()).limit(50).all()
        data = []
        for r in reqs:
            data.append({
                'id': r.id,
                'visit_id': r.visit_id,
                'patient_id': r.patient_id,
                'status': r.status,
                'request_number': getattr(r, 'request_number', None)
            })
        return jsonify({'success': True, 'requests': data})
    except Exception as e:
        logging.error(f"Error loading radiology api worklist: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500

@radiology_bp.route('/api/fhir/observation/radiology/<int:result_id>')
@login_required
@role_required('radiology', 'lab', 'doctor', 'admin', 'manager')
def api_fhir_radiology_observation(result_id):
    try:
        res = db.session.get(RadiologyResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'RadiologyResult not found'}]}), 404
        req = db.session.get(RadiologyRequest, res.request_id)
        visit_id = req.visit_id if req else None

        status_map = {
            'PENDING': 'preliminary',
            'READY': 'final',
            'VALIDATED': 'final'
        }
        status = status_map.get((res.status or '').upper(), 'unknown')

        code_text = 'Radiology Observation'
        if req and (req.modality or req.body_part):
            mp = []
            if req.modality:
                mp.append(req.modality)
            if req.body_part:
                mp.append(req.body_part)
            code_text = ' / '.join(mp)

        resource = {
            'resourceType': 'Observation',
            'id': str(res.id),
            'status': status,
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'imaging'}]}],
            'code': {
                'coding': [{'system': 'urn:medical-system:modality', 'code': (req.modality if req and req.modality else 'RAD')}],
                'text': code_text
            },
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'effectiveDateTime': (res.created_at.isoformat() if res.created_at else None),
            'valueString': (res.impression or res.findings or ''),
            **({'performer': [{'reference': f'Practitioner/{res.performed_by}'}]} if res.performed_by else {}),
            'note': ([{'text': res.notes}] if res.notes else []) + ([{'text': f'StudyUID: {res.study_uid}'}] if res.study_uid else [])
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Radiology Observation: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الأشعة حالياً'}]}), 500

@radiology_bp.route('/api/fhir/diagnosticreport/radiology/<int:result_id>')
@login_required
@role_required('radiology', 'lab', 'doctor', 'admin', 'manager')
def api_fhir_radiology_diagnostic_report(result_id):
    """تصدير تقرير أشعة بصيغة FHIR DiagnosticReport وربطه بـ Encounter"""
    try:
        res = db.session.get(RadiologyResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'RadiologyResult not found'}]}), 404
        req = db.session.get(RadiologyRequest, res.request_id)
        visit_id = req.visit_id if req else None

        status_map = {
            'PENDING': 'preliminary',
            'READY': 'final',
            'VALIDATED': 'final'
        }
        status = status_map.get((res.status or '').upper(), 'unknown')

        code_text = 'Radiology Report'
        if req and (req.modality or req.body_part):
            mp = []
            if req.modality:
                mp.append(req.modality)
            if req.body_part:
                mp.append(req.body_part)
            code_text = ' / '.join(mp)

        resource = {
            'resourceType': 'DiagnosticReport',
            'id': str(res.id),
            'status': status,
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/v2-0074', 'code': 'RAD'}]}],
            'code': {
                'coding': [{'system': 'urn:medical-system:modality', 'code': (req.modality if req and req.modality else 'RAD')}],
                'text': code_text
            },
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'effectiveDateTime': (res.created_at.isoformat() if res.created_at else None),
            'issued': (res.updated_at.isoformat() if hasattr(res, 'updated_at') and res.updated_at else None),
            'result': [{'reference': f'Observation/{res.id}'}],
            'conclusion': (res.impression or ''),
            'presentedForm': ([{'contentType': 'text/plain', 'data': base64.b64encode((res.findings or '').encode()).decode()}] if res.findings else []),
            **({'performer': [{'reference': f'Practitioner/{res.performed_by}'}]} if res.performed_by else {})
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Radiology DiagnosticReport: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير تقرير الأشعة حالياً'}]}), 500

@radiology_bp.route('/api/fhir/imagingstudy/<int:result_id>')
@login_required
@role_required('radiology', 'lab', 'doctor', 'admin', 'manager')
def api_fhir_imaging_study(result_id):
    """تصدير دراسة تصويرية بصيغة FHIR ImagingStudy وربطها بـ Encounter"""
    try:
        res = db.session.get(RadiologyResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على نتيجة الأشعة المطلوبة'}]}), 404
        req = db.session.get(RadiologyRequest, res.request_id)
        visit_id = req.visit_id if req else None

        resource = {
            'resourceType': 'ImagingStudy',
            'id': str(res.id),
            **({'identifier': [{'system': 'urn:medical-system:study-uid', 'value': res.study_uid}]} if res.study_uid else {}),
            'status': 'available',
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'started': (res.created_at.isoformat() if res.created_at else None),
            **({'modality': [{'system': 'http://dicom.nema.org/resources/ontology/DCM', 'code': req.modality}]} if req and req.modality else {}),
            'numberOfSeries': 1,
            'numberOfInstances': 1,
            'series': [{
                'uid': res.study_uid or f'{res.id}.1',
                'number': 1,
                'modality': {'system': 'http://dicom.nema.org/resources/ontology/DCM', 'code': (req.modality or 'RAD') if req else 'RAD'},
                'bodySite': ({'text': req.body_part} if req and req.body_part else None),
                'instance': [{
                    'uid': f'{res.id}.1.1',
                    'sopClass': {'system': 'urn:ietf:rfc:3986', 'code': 'image/jpeg'},
                    'number': 1
                }]
            }]
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR ImagingStudy: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير الدراسة التصويرية حالياً'}]}), 500
