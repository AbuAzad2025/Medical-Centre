"""patients routes - extracted from monolithic emergency.py"""

import logging

# Imports
from flask import flash, g, redirect, render_template, url_for
from flask_login import login_required
from sqlalchemy import desc, select

from app.extensions import db
from app.shared.enums import EmergencyStatus
from models.emergency import EmergencyCase
from models.lab_request import LabRequest
from models.medical_record import MedicalRecord
from models.medication import Prescription
from models.patient import Patient
from models.radiology_request import RadiologyRequest
from routes.emergency import emergency_bp
from services.emergency_service import emergency_service
from utils.decorators import role_required

# =============================================
# PATIENTS ROUTES
# =============================================


@emergency_bp.route('/patient-details/<int:emergency_id>')
@login_required
@role_required('emergency', 'manager')
def patient_details(emergency_id):
    """تفاصيل حالة الطوارئ"""

    try:
        from flask import g

        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        tenant_id = getattr(g, 'tenant_id', None)

        # جلب السجل الطبي للمريض - tenant filtered
        medical_records = (
            db.session.execute(
                select(MedicalRecord)
                .filter(MedicalRecord.patient_id == emergency.patient_id)
                .filter(
                    MedicalRecord.tenant_id == tenant_id
                    if hasattr(MedicalRecord, 'tenant_id') and tenant_id
                    else True
                )
                .order_by(desc(MedicalRecord.created_at))
                .limit(10)
            )
            .scalars()
            .all()
        )

        # جلب الوصفات السابقة - tenant filtered
        previous_prescriptions = (
            db.session.execute(
                select(Prescription)
                .filter(Prescription.patient_id == emergency.patient_id)
                .filter(
                    Prescription.tenant_id == tenant_id
                    if hasattr(Prescription, 'tenant_id') and tenant_id
                    else True
                )
                .order_by(desc(Prescription.created_at))
                .limit(5)
            )
            .scalars()
            .all()
        )

        # جلب طلبات المختبر والأشعة - tenant filtered
        lab_requests = (
            db.session.execute(
                select(LabRequest)
                .filter(LabRequest.visit_id == emergency.visit_id)
                .filter(
                    LabRequest.tenant_id == tenant_id
                    if hasattr(LabRequest, 'tenant_id') and tenant_id
                    else True
                )
            )
            .scalars()
            .all()
        )

        radiology_requests = (
            db.session.execute(
                select(RadiologyRequest)
                .filter(RadiologyRequest.visit_id == emergency.visit_id)
                .filter(
                    RadiologyRequest.tenant_id == tenant_id
                    if hasattr(RadiologyRequest, 'tenant_id') and tenant_id
                    else True
                )
            )
            .scalars()
            .all()
        )

        return render_template(
            'emergency/patient_details.html',
            emergency=emergency,
            medical_records=medical_records,
            previous_prescriptions=previous_prescriptions,
            lab_requests=lab_requests,
            radiology_requests=radiology_requests,
        )
    except Exception:
        logging.exception('Error loading patient details: %s')
        flash('حدث خطأ في تحميل تفاصيل المريض', 'error')
        return redirect(url_for('emergency.patient_queue'))


# مسارات إضافية للطوارئ الاحترافية


@emergency_bp.route('/medical-history/<int:patient_id>')
@login_required
@role_required('emergency', 'manager')
def medical_history(patient_id):
    """السجل الطبي للمريض في الطوارئ"""

    try:
        from flask import g

        tenant_id = getattr(g, 'tenant_id', None)

        patient = (
            db.session.execute(
                select(Patient)
                .filter_by(id=patient_id)
                .filter(
                    Patient.tenant_id == tenant_id
                    if hasattr(Patient, 'tenant_id') and tenant_id
                    else True
                )
            )
            .scalars()
            .first()
        )
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))

        # جلب السجل الطبي الكامل - tenant filtered
        medical_records = (
            db.session.execute(
                select(MedicalRecord)
                .filter(MedicalRecord.patient_id == patient_id)
                .filter(
                    MedicalRecord.tenant_id == tenant_id
                    if hasattr(MedicalRecord, 'tenant_id') and tenant_id
                    else True
                )
                .order_by(desc(MedicalRecord.created_at))
            )
            .scalars()
            .all()
        )

        # جلب حالات الطوارئ السابقة - tenant filtered
        previous_emergencies = (
            db.session.execute(
                select(EmergencyCase)
                .filter(
                    EmergencyCase.patient_id == patient_id,
                    EmergencyCase.status == EmergencyStatus.COMPLETED,
                    EmergencyCase.tenant_id == tenant_id
                    if hasattr(EmergencyCase, 'tenant_id') and tenant_id
                    else True,
                )
                .order_by(desc(EmergencyCase.created_at))
                .limit(10)
            )
            .scalars()
            .all()
        )

        return render_template(
            'emergency/medical_history.html',
            patient=patient,
            medical_records=medical_records,
            previous_emergencies=previous_emergencies,
        )
    except Exception:
        logging.exception('Error loading medical history: %s')
        flash('حدث خطأ في تحميل السجل الطبي', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/prescriptions-history/<int:patient_id>')
@login_required
@role_required('emergency', 'manager')
def prescriptions_history(patient_id):
    """تاريخ الوصفات الطبية للمريض في الطوارئ"""

    try:
        from flask import g

        patient = (
            db.session.execute(
                select(Patient)
                .filter_by(id=patient_id)
                .filter(
                    Patient.tenant_id == g.tenant_id
                    if hasattr(Patient, 'tenant_id') and g.tenant_id
                    else True
                )
            )
            .scalars()
            .first()
        )
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))

        prescriptions = (
            db.session.execute(
                select(Prescription)
                .filter(Prescription.patient_id == patient_id)
                .filter(
                    Prescription.tenant_id == g.tenant_id
                    if hasattr(Prescription, 'tenant_id') and g.tenant_id
                    else True
                )
                .order_by(desc(Prescription.created_at))
            )
            .scalars()
            .all()
        )

        return render_template(
            'emergency/prescriptions_history.html', patient=patient, prescriptions=prescriptions
        )
    except Exception:
        logging.exception('Error loading prescriptions history: %s')
        flash('حدث خطأ في تحميل تاريخ الوصفات', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/lab-results/<int:patient_id>')
@login_required
@role_required('emergency', 'manager')
def lab_results(patient_id):
    """نتائج المختبر للمريض في الطوارئ"""

    try:
        patient = (
            db.session.execute(
                select(Patient)
                .filter_by(id=patient_id)
                .filter(
                    Patient.tenant_id == g.tenant_id
                    if hasattr(Patient, 'tenant_id') and g.tenant_id
                    else True
                )
            )
            .scalars()
            .first()
        )
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))

        lab_requests = (
            db.session.execute(
                select(LabRequest)
                .filter(LabRequest.patient_id == patient_id)
                .filter(
                    LabRequest.tenant_id == g.tenant_id
                    if hasattr(LabRequest, 'tenant_id') and g.tenant_id
                    else True
                )
                .order_by(desc(LabRequest.created_at))
            )
            .scalars()
            .all()
        )

        return render_template(
            'emergency/lab_results.html', patient=patient, lab_requests=lab_requests
        )
    except Exception:
        logging.exception('Error loading lab results: %s')
        flash('حدث خطأ في تحميل نتائج المختبر', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/radiology-results/<int:patient_id>')
@login_required
@role_required('emergency', 'manager')
def radiology_results(patient_id):
    """نتائج الأشعة للمريض في الطوارئ"""

    try:
        patient = (
            db.session.execute(
                select(Patient)
                .filter_by(id=patient_id)
                .filter(
                    Patient.tenant_id == g.tenant_id
                    if hasattr(Patient, 'tenant_id') and g.tenant_id
                    else True
                )
            )
            .scalars()
            .first()
        )
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))

        radiology_requests = (
            db.session.execute(
                select(RadiologyRequest)
                .filter(RadiologyRequest.patient_id == patient_id)
                .filter(
                    RadiologyRequest.tenant_id == g.tenant_id
                    if hasattr(RadiologyRequest, 'tenant_id') and g.tenant_id
                    else True
                )
                .order_by(desc(RadiologyRequest.created_at))
            )
            .scalars()
            .all()
        )

        return render_template(
            'emergency/radiology_results.html',
            patient=patient,
            radiology_requests=radiology_requests,
        )
    except Exception:
        logging.exception('Error loading radiology results: %s')
        flash('حدث خطأ في تحميل نتائج الأشعة', 'error')
        return redirect(url_for('emergency.patient_queue'))
