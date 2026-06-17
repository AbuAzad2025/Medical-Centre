"""fhir routes - extracted from monolithic lab.py"""

from routes.lab import lab_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, make_response
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.lab_request import LabRequest
from models.lab_request import LabResult
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent
from models.audit_trail import AuditTrail
from app_factory import db
import logging, json, base64
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# FHIR ROUTES
# =============================================

@lab_bp.route('/api/worklist')
@login_required
@role_required('lab', 'technician', 'admin', 'manager', 'doctor', 'super_admin')
def api_worklist():
    try:
        visit_id = request.args.get('visit_id', type=int)
        status = request.args.get('status', type=str)
        q = LabRequest.query
        if visit_id:
            q = q.filter(LabRequest.visit_id == visit_id)
        if status:
            q = q.filter(LabRequest.status == status)
        reqs = q.order_by(LabRequest.created_at.desc()).limit(50).all()
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
        logging.error(f"Error loading lab api worklist: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500

@lab_bp.route('/api/fhir/servicerequest', methods=['POST'])
@login_required
@role_required('lab', 'doctor', 'admin', 'manager')
def api_fhir_lab_service_request():
    try:
        data = request.get_json() or {}
        patient_id = data.get('patient_id')
        visit_id = data.get('visit_id')
        requester_id = data.get('requester_id') or getattr(current_user, 'id', None)
        tests = data.get('tests') or []
        if not patient_id or not visit_id:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'patient_id and visit_id مطلوبان'}]}), 400
        req = LabRequest(
            visit_id=visit_id,
            patient_id=patient_id,
            requested_by=requester_id,
            status='REQUESTED',
            notes=data.get('notes')
        )
        req.request_number = f"LAB-{int(datetime.now(timezone.utc).timestamp())}"
        db.session.add(req)
        db.session.flush()
        for t in tests:
            if not isinstance(t, dict):
                continue
            code = (t.get('test_code') or '').strip()
            name = (t.get('test_name') or '').strip() or code or 'Test'
            if not code and not name:
                continue
            db.session.add(LabResult(
                request_id=req.id,
                patient_id=patient_id,
                test_code=code or name,
                test_name=name,
                status='PENDING'
            ))
        _log_lab_workflow(req.id, 'REQUESTED', 'fhir_service_request')
        db.session.commit()
        return jsonify({'resourceType': 'ServiceRequest', 'id': str(req.id), 'status': 'active', 'subject': {'reference': f'Patient/{patient_id}'}, 'encounter': {'reference': f'Encounter/{visit_id}'}}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error importing FHIR ServiceRequest: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر استيراد طلب المختبر'}]}), 500

@lab_bp.route('/api/fhir/observation', methods=['POST'])
@login_required
@role_required('lab', 'doctor', 'admin', 'manager')
def api_fhir_lab_observation_import():
    try:
        data = request.get_json() or {}
        request_id = data.get('request_id')
        patient_id = data.get('patient_id')
        test_code = (data.get('test_code') or '').strip()
        test_name = (data.get('test_name') or '').strip() or test_code or 'Test'
        value = data.get('value')
        unit = data.get('unit')
        reference_range = data.get('reference_range')
        if not request_id or not patient_id:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'request_id and patient_id مطلوبان'}]}), 400
        req = db.session.get(LabRequest, int(request_id))
        if not req:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'طلب المختبر غير موجود'}]}), 404
        res = None
        if test_code:
            res = LabResult.query.filter_by(request_id=req.id, test_code=test_code).first()
        if not res:
            res = LabResult(
                request_id=req.id,
                patient_id=patient_id,
                test_code=test_code or test_name,
                test_name=test_name,
                status='READY'
            )
            db.session.add(res)
        res.value = value
        res.unit = unit
        res.reference_range = reference_range
        res.status = 'VALIDATED'
        res.performed_by = getattr(current_user, 'id', None)
        req.updated_at = datetime.now(timezone.utc)
        _log_lab_workflow(req.id, req.status, 'fhir_observation')
        db.session.commit()
        return jsonify({'resourceType': 'Observation', 'id': str(res.id), 'status': 'final'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error importing FHIR Observation: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر استيراد نتيجة المختبر'}]}), 500

@lab_bp.route('/api/hl7/import', methods=['POST'])
@login_required
@role_required('lab', 'doctor', 'admin', 'manager')
def api_hl7_import():
    try:
        data = request.get_json() or {}
        patient_id = data.get('patient_id')
        visit_id = data.get('visit_id')
        tests = data.get('tests') or []
        if not patient_id or not visit_id:
            return jsonify({'success': False, 'message': 'patient_id و visit_id مطلوبان'}), 400
        req = LabRequest(
            visit_id=visit_id,
            patient_id=patient_id,
            requested_by=getattr(current_user, 'id', None),
            status='REQUESTED',
            notes=data.get('notes')
        )
        req.request_number = f"HL7-{int(datetime.now(timezone.utc).timestamp())}"
        db.session.add(req)
        db.session.flush()
        for t in tests:
            if not isinstance(t, dict):
                continue
            code = (t.get('test_code') or '').strip()
            name = (t.get('test_name') or '').strip() or code or 'Test'
            db.session.add(LabResult(
                request_id=req.id,
                patient_id=patient_id,
                test_code=code or name,
                test_name=name,
                value=t.get('value'),
                unit=t.get('unit'),
                reference_range=t.get('reference_range'),
                status='PENDING'
            ))
        _log_lab_workflow(req.id, 'REQUESTED', 'hl7_import')
        db.session.commit()
        return jsonify({'success': True, 'request_id': req.id}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error importing HL7 lab payload: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر استيراد HL7'}), 500

@lab_bp.route('/api/fhir/observation/lab/<int:result_id>')
@login_required
@role_required('lab', 'radiology', 'doctor', 'admin', 'manager')
def api_fhir_lab_observation(result_id):
    """تصدير نتيجة مختبر بصيغة FHIR Observation وربطها بـ Encounter"""
    try:
        res = db.session.get(LabResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'LabResult not found'}]}), 404
        req = db.session.get(LabRequest, res.request_id)
        visit_id = req.visit_id if req else None

        # تحويل الحالة إلى FHIR
        status_map = {
            'PENDING': 'preliminary',
            'READY': 'final',
            'VALIDATED': 'final'
        }
        status = status_map.get((res.status or '').upper(), 'unknown')

        # محاولة تحويل القيمة إلى رقم
        value_str = (res.value or '').strip()
        value_num = None
        try:
            value_num = float(value_str)
        except Exception:
            value_num = None

        resource = {
            'resourceType': 'Observation',
            'id': str(res.id),
            'status': status,
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'laboratory'}]}],
            'code': {
                'coding': [{'system': 'urn:medical-system:test-code', 'code': res.test_code}],
                'text': res.test_name
            },
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'effectiveDateTime': (res.created_at.isoformat() if res.created_at else None),
            **({'valueQuantity': {'value': value_num, 'unit': res.unit}} if value_num is not None else {'valueString': value_str}),
            'referenceRange': ([{'text': res.reference_range}] if res.reference_range else []),
            **({'performer': [{'reference': f'Practitioner/{res.performed_by}'}]} if res.performed_by else {}),
            'note': ([{'text': res.notes}] if res.notes else [])
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Lab Observation: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير نتائج المختبر حالياً'}]}), 500

@lab_bp.route('/api/fhir/diagnosticreport/lab/<int:result_id>')
@login_required
@role_required('lab', 'radiology', 'doctor', 'admin', 'manager')
def api_fhir_lab_diagnostic_report(result_id):
    """تصدير تقرير مختبر بصيغة FHIR DiagnosticReport وربطه بـ Encounter"""
    try:
        res = db.session.get(LabResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على نتيجة المختبر المطلوبة'}]}), 404
        req = db.session.get(LabRequest, res.request_id)
        visit_id = req.visit_id if req else None

        status_map = {
            'PENDING': 'preliminary',
            'READY': 'final',
            'VALIDATED': 'final'
        }
        status = status_map.get((res.status or '').upper(), 'unknown')

        resource = {
            'resourceType': 'DiagnosticReport',
            'id': str(res.id),
            'status': status,
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/v2-0074', 'code': 'LAB'}]}],
            'code': {
                'coding': [{'system': 'urn:medical-system:test-code', 'code': res.test_code}],
                'text': res.test_name
            },
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'effectiveDateTime': (res.created_at.isoformat() if res.created_at else None),
            'issued': (res.updated_at.isoformat() if hasattr(res, 'updated_at') and res.updated_at else None),
            'result': [{'reference': f'Observation/{res.id}'}],
            'conclusion': (res.notes or ''),
            **({'performer': [{'reference': f'Practitioner/{res.performed_by}'}]} if res.performed_by else {})
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Lab DiagnosticReport: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير تقرير المختبر حالياً'}]}), 500
