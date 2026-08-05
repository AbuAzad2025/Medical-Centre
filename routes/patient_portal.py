"""
Patient Portal — MyChart-style patient-facing portal (UX1-006)
"""

import logging
import os
from datetime import UTC, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import InvoiceStatus, OrderState
from models.appointment import Appointment
from models.file_management import FileUpload
from models.invoice import Invoice
from models.lab_request import LabRequest, LabResult
from models.medical_record import MedicalRecord
from models.medication import Prescription
from models.patient_satisfaction import PatientSatisfactionSurvey
from models.payment import Payment
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.vaccination import Immunization
from models.visit import Visit
from services.patient_identity_service import (
    get_portal_preferences,
    resolve_patient_for_user,
    save_portal_preferences,
    verify_and_link_patient,
)
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

portal_bp = Blueprint('portal', __name__)


def _require_patient_role():
    if not current_user.is_authenticated or current_user.role != 'patient':
        flash('بوابة المريض متاحة لحسابات المرضى الموثّقة فقط', 'error')
        return redirect(url_for('main.dashboard'))
    return None


def _get_patient_from_user():
    return resolve_patient_for_user(current_user)


def _patient_visible_invoice_query(patient):
    """P0B-001B: Patient-visible invoices are DRAFT, ISSUED, or POSTED."""
    return (
        select(Invoice)
        .join(Visit)
        .filter(
            Visit.patient_id == patient.id,
            Invoice.status.in_(
                [
                    InvoiceStatus.DRAFT.value,
                    InvoiceStatus.ISSUED.value,
                    InvoiceStatus.POSTED.value,
                ]
            ),
        )
    )


def _patient_visible_lab_requests(patient):
    """P0B-001B: Lab results are visible only when APPROVED and not critical."""
    reqs = (
        db.session.execute(
            select(LabRequest)
            .filter(
                LabRequest.patient_id == patient.id,
                LabRequest.status == OrderState.APPROVED.value,
            )
            .order_by(LabRequest.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [req for req in reqs if not any(r.is_critical for r in req.results)]


def _patient_visible_radiology_requests(patient):
    """P0B-001B: Radiology results are visible only when DONE and not critical."""
    reqs = (
        db.session.execute(
            select(RadiologyRequest)
            .filter(RadiologyRequest.patient_id == patient.id, RadiologyRequest.status == 'DONE')
            .order_by(RadiologyRequest.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [req for req in reqs if not any(r.is_critical for r in req.results)]


def _patient_has_critical_results(patient):
    """P0B-001B: Returns True if the patient has any critical lab/radiology result."""
    critical_labs = db.session.execute(
        select(func.count())
        .select_from(LabResult)
        .join(LabRequest)
        .filter(LabRequest.patient_id == patient.id, LabResult.is_critical.is_(True))
    ).scalar()
    if critical_labs:
        return True
    critical_rads = db.session.execute(
        select(func.count())
        .select_from(RadiologyResult)
        .join(RadiologyRequest)
        .filter(RadiologyRequest.patient_id == patient.id, RadiologyResult.is_critical.is_(True))
    ).scalar()
    return critical_rads > 0


def _patient_documents(patient):
    """Files attached to patient or their visits — portal-visible only."""
    visit_ids = [
        v.id
        for v in db.session.execute(select(Visit).filter_by(patient_id=patient.id)).scalars().all()
    ]
    clauses = [
        db.and_(
            FileUpload.related_entity_type == 'patient', FileUpload.related_entity_id == patient.id
        ),
    ]
    if visit_ids:
        clauses.append(
            db.and_(
                FileUpload.related_entity_type == 'visit',
                FileUpload.related_entity_id.in_(visit_ids),
            )
        )
    return (
        db.session.execute(
            select(FileUpload)
            .filter(db.or_(*clauses))
            .order_by(FileUpload.uploaded_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )


def _patient_owns_file(patient, file_upload):
    if file_upload.related_entity_type == 'patient' and file_upload.related_entity_id == patient.id:
        return True
    if file_upload.related_entity_type == 'visit':
        visit = db.session.get(Visit, file_upload.related_entity_id)
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
        _linked, err = verify_and_link_patient(
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

    upcoming_appointments = (
        db.session.execute(
            select(Appointment)
            .filter(
                Appointment.patient_id == patient.id, Appointment.starts_at >= datetime.now(UTC)
            )
            .order_by(Appointment.starts_at)
            .limit(5)
        )
        .scalars()
        .all()
    )

    recent_visits = (
        db.session.execute(
            select(Visit)
            .filter_by(patient_id=patient.id)
            .order_by(Visit.created_at.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )

    open_invoices = db.session.execute(_patient_visible_invoice_query(patient)).scalars().all()
    total_due = sum(
        (float(getattr(inv, 'total_amount', 0) or 0) - float(getattr(inv, 'paid_amount', 0) or 0))
        for inv in open_invoices
    )

    visible_labs = _patient_visible_lab_requests(patient)
    visible_rads = _patient_visible_radiology_requests(patient)
    unread_results = len(visible_labs) + len(visible_rads)
    critical_results = _patient_has_critical_results(patient)

    immunizations = (
        db.session.execute(
            select(Immunization)
            .filter_by(patient_id=patient.id)
            .order_by(Immunization.administration_date.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )

    return render_template(
        'portal/dashboard.html',
        patient=patient,
        upcoming_appointments=upcoming_appointments,
        recent_visits=recent_visits,
        total_due=total_due,
        unread_results=unread_results,
        critical_results=critical_results,
        immunizations=immunizations,
    )


@portal_bp.route('/appointments')
@login_required
@role_required('patient')
def appointments():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    items = (
        db.session.execute(
            select(Appointment)
            .filter_by(patient_id=patient.id)
            .order_by(Appointment.starts_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
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
    records = (
        db.session.execute(
            select(MedicalRecord)
            .filter_by(patient_id=patient.id)
            .order_by(MedicalRecord.created_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    return render_template('portal/medical_records.html', patient=patient, records=records)


@portal_bp.route('/prescriptions')
@login_required
@role_required('patient')
def prescriptions():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    items = (
        db.session.execute(
            select(Prescription)
            .filter_by(patient_id=patient.id)
            .order_by(Prescription.created_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
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
    return render_template(
        'portal/lab_results.html',
        patient=patient,
        lab_requests=requests,
        critical_results_pending=critical_results_pending,
    )


@portal_bp.route('/radiology-results')
@login_required
@role_required('patient')
def radiology_results():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    requests = _patient_visible_radiology_requests(patient)[:50]
    return render_template(
        'portal/radiology_results.html', patient=patient, radiology_requests=requests
    )


@portal_bp.route('/bills')
@login_required
@role_required('patient')
def bills():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    invoices = (
        db.session.execute(
            _patient_visible_invoice_query(patient).order_by(Invoice.created_at.desc()).limit(50)
        )
        .scalars()
        .all()
    )
    payments = (
        db.session.execute(
            select(Payment)
            .filter_by(patient_id=patient.id)
            .order_by(Payment.payment_date.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    return render_template(
        'portal/bills.html', patient=patient, invoices=invoices, payments=payments
    )


@portal_bp.route('/vaccinations')
@login_required
@role_required('patient')
def vaccinations():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.link_account'))
    items = (
        db.session.execute(
            select(Immunization)
            .filter_by(patient_id=patient.id)
            .order_by(Immunization.administration_date.desc())
        )
        .scalars()
        .all()
    )
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
    upload = db.get_or_404(FileUpload, file_id)
    if not _patient_owns_file(patient, upload):
        abort(403)
    if not upload.file_path or not os.path.isfile(upload.file_path):
        abort(404)
    try:
        upload.last_accessed = datetime.now(UTC)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Error updating file access time: %s')
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
            try:
                survey = PatientSatisfactionSurvey(
                    patient_id=patient.id,
                    visit_id=visit_id,
                    overall_rating=rating,
                    comments=comments,
                )
                db.session.add(survey)
                safe_commit(db.session, error_message='database commit failed', reraise=True)
                flash('شكراً لتقييمك', 'success')
                return redirect(url_for('portal.dashboard'))
            except Exception:
                safe_rollback(db.session, error_message='database rollback')
                logging.exception('Error saving feedback: %s')
                flash('حدث خطأ أثناء حفظ التقييم', 'error')
    return render_template('portal/feedback.html', patient=patient)
