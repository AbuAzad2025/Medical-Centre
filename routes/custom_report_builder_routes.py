"""
Custom Report Builder
Drag-drop field selection for ad-hoc reports
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from app_factory import db

report_builder_bp = Blueprint('report_builder', __name__, guard_module=__name__)

from services.feature_gate_service import guard_module

@report_builder_bp.before_request
def _guard_reporting_module():
    guard_module('reporting')

REPORT_ENTITIES = {
    'patients': {
        'label': 'المرضى',
        'fields': ['id', 'full_name', 'national_id', 'phone', 'gender', 'birth_date', 'created_at']
    },
    'visits': {
        'label': 'الزيارات',
        'fields': ['id', 'patient_id', 'visit_type', 'status', 'visit_date', 'total_amount', 'created_at']
    },
    'appointments': {
        'label': 'المواعيد',
        'fields': ['id', 'patient_id', 'doctor_id', 'starts_at', 'status', 'notes']
    },
    'invoices': {
        'label': 'الفواتير',
        'fields': ['id', 'patient_id', 'total_amount', 'paid_amount', 'status', 'created_at']
    },
    'lab_requests': {
        'label': 'طلبات المختبر',
        'fields': ['id', 'patient_id', 'test_name', 'status', 'is_urgent', 'created_at']
    },
    'prescriptions': {
        'label': 'الوصفات',
        'fields': ['id', 'patient_id', 'doctor_id', 'status', 'created_at']
    }
}

@report_builder_bp.route('/')
@login_required
@role_required('admin', 'manager', 'accountant', 'doctor')
def builder():
    return render_template('report_builder/builder.html', entities=REPORT_ENTITIES)

@report_builder_bp.route('/preview', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'accountant', 'doctor')
def preview():
    data = request.get_json()
    entity = data.get('entity') if data else request.form.get('entity')
    fields = data.get('fields', []) if data else request.form.getlist('fields')
    limit = int(data.get('limit', 100) if data else request.form.get('limit', 100))

    if not entity or entity not in REPORT_ENTITIES:
        return jsonify({'success': False, 'message': 'Invalid entity'})

    # Build dynamic query
    model_map = {
        'patients': 'Patient',
        'visits': 'Visit',
        'appointments': 'Appointment',
        'invoices': 'Invoice',
        'lab_requests': 'LabRequest',
        'prescriptions': 'Prescription'
    }

    model_name = model_map.get(entity)
    if not model_name:
        return jsonify({'success': False, 'message': 'Model not found'})

    try:
        model = getattr(__import__('models', fromlist=[model_name]), model_name)
        query = model.query
        if hasattr(model, 'created_at'):
            query = query.order_by(model.created_at.desc())
        results = query.limit(limit).all()
        output = []
        for r in results:
            row = {}
            for f in fields:
                val = getattr(r, f, None)
                row[f] = str(val) if val is not None else ''
            output.append(row)
        return jsonify({'success': True, 'headers': fields, 'rows': output})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
