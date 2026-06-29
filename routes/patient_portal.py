"""
Patient Portal — MyChart-style patient-facing portal (UX1-006)
"""
import logging
import os

from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, send_file
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.medical_record import MedicalRecord
from models.medication import Prescription
from models.invoice import Invoice
from models.payment import Payment
from models.lab_request import LabRequest, LabResult
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.vaccination import Immunization
from models.patient_satisfaction import PatientSatisfactionSurvey
from models.file_management import FileUpload
from app_factory import db
from app.shared.enums import InvoiceStatus, OrderState
from datetime import datetime, timezone
from services.patient_identity_service import (
    resolve_patient_for_user,
    verify_and_link_patient,
    get_portal_preferences,
    save_portal_preferences,
)
from services.file_service import FileService

portal_bp = Blueprint('portal', __name__)


def _require_patient_role():
    if not current_user.is_authenticated or current_user.role != 'patient':
        flash('بوابة المريض متاحة لحسابات المرضى الموثّقة فقط', 'error')
        return redirect(url_for('main.dashboard'))


def _get_patient_from_user():
    return resolve_patient_for_user(current_user)


def _patient_visible_invoice_query(patient):
    """P0B-001B: Patient-visible invoices are DRAFT, ISSUED, or POSTED."""
    return Invoice.query.join(Visit).filter(
        Visit.patient_id == patient.id,
        Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.ISSUED, InvoiceStatus.POSTED])
    )


def _patient_visible_lab_requests(patient):
    """P0B-001B: Lab results are visible only when APPROVED and not critical."""
    reqs = LabRequest.query.filter(
        LabRequest.patient_id == patient.id,
        LabRequest.status == OrderState.APPROVED.value,
    ).order_by(LabRequest.created_at.desc()).all()
    return [req for req in reqs if not any(r.is_critical for r in req.results)]


def _patient_visible_radiology_requests(patient):
    """P0B-001B: Radiology results are visible only when DONE and not critical."""
    reqs = RadiologyRequest.query.filter(
        RadiologyRequest.patient_id == patient.id,
        RadiologyRequest.status == 'DONE'
    ).order_by(RadiologyRequest.created_at.desc()).all()
    return [req for req in reqs if not any(r.is_critical for r in req.results)]


def _patient_has_critical_results(patient):
    """P0B-001B: Returns True if the patient has any critical lab/radiology result."""
    critical_labs = LabResult.query.join(LabRequest).filter(
        LabRequest.patient_id == patient.id,
        LabResult.is_critical.is_(True)
    ).count()
    if critical_labs:
        return True
    critical_rads = RadiologyResult.query.join(RadiologyRequest).filter(
        RadiologyRequest.patient_id == patient.id,
        RadiologyResult.is_critical.is_(True)
    ).count()
    return critical_rads > 0


def _patient_documents(patient):
    """Files attached to patient or their visits — portal-visible only."""
    visit_ids = [v.id for v in Visit.query.filter_by(patient_id=patient.id).all()]
    clauses = [
        db.and_(FileUpload.related_entity_type == 'patient', FileUpload.related_entity_id == patient.id),
    ]
    if visit_ids:
        clauses.append(
            db.and_(FileUpload.related_entity_type == 'visit', FileUpload.related_entity_id.in_(visit_ids))
        )
    return FileUpload.query.filter(db.or_(*clauses)).order_by(FileUpload.uploaded_at.desc()).limit(100).all()


def _patient_owns_file(patient, file_upload):
    if file_upload.related_entity_type == 'patient' and file_upload.related_entity_id == patient.id:
        return True
    if file_upload.related_entity_type == 'visit':
        visit = Visit.query.get(file_upload.related_entity_id)
        return visit and visit.patient_id == patient.id
    return False


@portal_bp.route('/')
@login_required
@role_required('patient')
def index():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    return redirect(url_for('portal.dashboard'))


@portal_bp.route('/link-account', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def link_account():
    patient = _get_patient_from_user()
    if patient:
        return redirect(url_for('portal.dashboard'))
    if request.method == 'POST':
        national_id = request.form.get('national_id')
        phone = request.form.get('phone') or current_user.phone
        linked, err = verify_and_link_patient(
            current_user,
            national_id=national_id,
            phone=phone,
        )
        if err:
            flash(err, 'error')
        else:
            flash('تم ربط حسابك بملف المريض بنجاح', 'success')
            return redirect(url_for('portal.dashboard'))
    return render_template('portal/link_account.html')


@portal_bp.route('/dashboard')
@login_required
@role_required('patient')
def dashboard():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))

    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.starts_at >= datetime.now(timezone.utc)
    ).order_by(Appointment.starts_at).limit(5).all()

    recent_visits = Visit.query.filter_by(patient_id=patient.id).order_by(
        Visit.created_at.desc()
    ).limit(5).all()

    open_invoices = _patient_visible_invoice_query(patient).all()
    total_due = sum(
        (float(getattr(inv, 'total_amount', 0) or 0) - float(getattr(inv, 'paid_amount', 0) or 0))
        for inv in open_invoices
    )

    visible_labs = _patient_visible_lab_requests(patient)
    visible_rads = _patient_visible_radiology_requests(patient)
    unread_results = len(visible_labs) + len(visible_rads)
    critical_results = _patient_has_critical_results(patient)

    immunizations = Immunization.query.filter_by(patient_id=patient.id).order_by(
        Immunization.administration_date.desc()
    ).limit(5).all()

    return render_template('portal/dashboard.html',
                           patient=patient,
                           upcoming_appointments=upcoming_appointments,
                           recent_visits=recent_visits,
                           total_due=total_due,
                           unread_results=unread_results,
                           critical_results=critical_results,
                           immunizations=immunizations)


@portal_bp.route('/appointments')
@login_required
@role_required('patient')
def appointments():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    items = Appointment.query.filter_by(patient_id=patient.id).order_by(
        Appointment.starts_at.desc()
    ).limit(50).all()
    return render_template('portal/appointments.html', patient=patient, appointments=items)


@portal_bp.route('/book-appointment')
@login_required
@role_required('patient')
def book_appointment():
    """Redirect to public booking flow (prefilled for logged-in patient)."""
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    return redirect(url_for('booking.create_booking'))


@portal_bp.route('/medical-records')
@login_required
@role_required('patient')
def medical_records():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    records = MedicalRecord.query.filter_by(patient_id=patient.id).order_by(
        MedicalRecord.created_at.desc()
    ).limit(50).all()
    return render_template('portal/medical_records.html', patient=patient, records=records)


@portal_bp.route('/prescriptions')
@login_required
@role_required('patient')
def prescriptions():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    items = Prescription.query.filter_by(patient_id=patient.id).order_by(
        Prescription.created_at.desc()
    ).limit(50).all()
    return render_template('portal/prescriptions.html', patient=patient, prescriptions=items)


@portal_bp.route('/lab-results')
@login_required
@role_required('patient')
def lab_results():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    requests = _patient_visible_lab_requests(patient)[:50]
    critical_results_pending = _patient_has_critical_results(patient)
    return render_template('portal/lab_results.html', patient=patient, lab_requests=requests,
                           critical_results_pending=critical_results_pending)


@portal_bp.route('/radiology-results')
@login_required
@role_required('patient')
def radiology_results():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    requests = _patient_visible_radiology_requests(patient)[:50]
    return render_template('portal/radiology_results.html', patient=patient, radiology_requests=requests)


@portal_bp.route('/bills')
@login_required
@role_required('patient')
def bills():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    invoices = _patient_visible_invoice_query(patient).order_by(
        Invoice.created_at.desc()
    ).limit(50).all()
    payments = Payment.query.filter_by(patient_id=patient.id).order_by(
        Payment.payment_date.desc()
    ).limit(50).all()
    return render_template('portal/bills.html', patient=patient, invoices=invoices, payments=payments)


@portal_bp.route('/vaccinations')
@login_required
@role_required('patient')
def vaccinations():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    items = Immunization.query.filter_by(patient_id=patient.id).order_by(
        Immunization.administration_date.desc()
    ).all()
    return render_template('portal/vaccinations.html', patient=patient, immunizations=items)


@portal_bp.route('/documents')
@login_required
@role_required('patient')
def documents():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    files = _patient_documents(patient)
    return render_template('portal/documents.html', patient=patient, files=files)


@portal_bp.route('/documents/<int:file_id>')
@login_required
@role_required('patient')
def download_document(file_id):
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    upload = FileUpload.query.get_or_404(file_id)
    if not _patient_owns_file(patient, upload):
        abort(403)
    if not upload.file_path or not os.path.isfile(upload.file_path):
        abort(404)
    upload.last_accessed = datetime.now(timezone.utc)
    db.session.commit()
    return send_file(
        upload.file_path,
        as_attachment=True,
        download_name=upload.original_filename,
        mimetype=upload.file_type or 'application/octet-stream',
    )


@portal_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def settings():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    prefs = get_portal_preferences(current_user)
    if request.method == 'POST':
        updates = {
            'notify_results': request.form.get('notify_results') == '1',
            'notify_appointments': request.form.get('notify_appointments') == '1',
            'marketing_contact': request.form.get('marketing_contact') == '1',
            'telemedicine_consent': request.form.get('telemedicine_consent') == '1',
        }
        if save_portal_preferences(current_user, updates):
            flash('تم حفظ تفضيلاتك', 'success')
            return redirect(url_for('portal.settings'))
        flash('تعذر حفظ التفضيلات', 'error')
        prefs = get_portal_preferences(current_user)
    return render_template('portal/settings.html', patient=patient, preferences=prefs)


@portal_bp.route('/feedback', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def feedback():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    if request.method == 'POST':
        rating = request.form.get('rating', type=int)
        comments = request.form.get('comments')
        visit_id = request.form.get('visit_id', type=int)
        if rating:
            survey = PatientSatisfactionSurvey(
                patient_id=patient.id,
                visit_id=visit_id,
                overall_rating=rating,
                comments=comments
            )
            db.session.add(survey)
            db.session.commit()
            flash('شكراً لتقييمك', 'success')
            return redirect(url_for('portal.dashboard'))
    return render_template('portal/feedback.html', patient=patient)
