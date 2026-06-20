"""
Patient Portal — MyChart-style patient-facing portal
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.medical_record import MedicalRecord
from models.medication import Prescription
from models.invoice import Invoice
from models.payment import Payment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.vaccination import Immunization
from models.patient_satisfaction import PatientSatisfactionSurvey
from models.online_booking import OnlineBooking
from models.branding import BrandingSettings
from app_factory import db
from datetime import datetime, date, timezone

portal_bp = Blueprint('portal', __name__)

def _get_patient_from_user():
    """Get patient record linked to current user"""
    if not hasattr(current_user, 'linked_patient_id') or not current_user.linked_patient_id:
        return None
    return Patient.query.get(current_user.linked_patient_id)

@portal_bp.route('/')
@login_required
def index():
    patient = _get_patient_from_user()
    if not patient:
        return render_template('portal/link_account.html')
    return redirect(url_for('portal.dashboard'))

@portal_bp.route('/dashboard')
@login_required
def dashboard():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))

    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.starts_at >= datetime.now(timezone.utc)
    ).order_by(Appointment.starts_at).limit(5).all()

    recent_visits = Visit.query.filter_by(patient_id=patient.id).order_by(
        Visit.created_at.desc()
    ).limit(5).all()

    open_invoices = Invoice.query.filter_by(patient_id=patient.id).filter(
        Invoice.status.in_(['DRAFT', 'ISSUED', 'PARTIAL'])
    ).all()
    total_due = sum(inv.balance_due or 0 for inv in open_invoices)

    unread_results = LabRequest.query.filter_by(patient_id=patient.id).filter(
        LabRequest.status.in_(['RESULTED', 'CRITICAL'])
    ).count()

    immunizations = Immunization.query.filter_by(patient_id=patient.id).order_by(
        Immunization.administration_date.desc()
    ).limit(5).all()

    return render_template('portal/dashboard.html',
                           patient=patient,
                           upcoming_appointments=upcoming_appointments,
                           recent_visits=recent_visits,
                           total_due=total_due,
                           unread_results=unread_results,
                           immunizations=immunizations)

@portal_bp.route('/appointments')
@login_required
def appointments():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
    items = Appointment.query.filter_by(patient_id=patient.id).order_by(
        Appointment.starts_at.desc()
    ).limit(50).all()
    return render_template('portal/appointments.html', patient=patient, appointments=items)

@portal_bp.route('/book-appointment', methods=['GET', 'POST'])
@login_required
def book_appointment():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
    if request.method == 'POST':
        from models.user import User
        doctor_id = request.form.get('doctor_id', type=int)
        appt_date = request.form.get('appointment_date')
        appt_time = request.form.get('appointment_time')
        reason = request.form.get('reason')
        if doctor_id and appt_date and appt_time:
            from datetime import datetime
            try:
                starts_at = datetime.strptime(f"{appt_date} {appt_time}", "%Y-%m-%d %H:%M")
                appt = Appointment(
                    patient_id=patient.id,
                    doctor_id=doctor_id,
                    starts_at=starts_at,
                    status='PENDING',
                    notes=reason
                )
                db.session.add(appt)
                db.session.commit()
                flash('تم طلب الموعد بنجاح، سيتم التأكيد قريباً', 'success')
                return redirect(url_for('portal.appointments'))
            except Exception:

                logging.warning(f"Error in {__name__}: {e}")
        flash('يرجى ملء جميع الحقول المطلوبة', 'error')

    from models.user import User
    doctors = User.query.filter(User.role.in_(['doctor', 'admin'])).all()
    return render_template('portal/book_appointment.html', patient=patient, doctors=doctors)

@portal_bp.route('/medical-records')
@login_required
def medical_records():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
    records = MedicalRecord.query.filter_by(patient_id=patient.id).order_by(
        MedicalRecord.created_at.desc()
    ).limit(50).all()
    return render_template('portal/medical_records.html', patient=patient, records=records)

@portal_bp.route('/prescriptions')
@login_required
def prescriptions():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
    items = Prescription.query.filter_by(patient_id=patient.id).order_by(
        Prescription.created_at.desc()
    ).limit(50).all()
    return render_template('portal/prescriptions.html', patient=patient, prescriptions=items)

@portal_bp.route('/lab-results')
@login_required
def lab_results():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
    requests = LabRequest.query.filter_by(patient_id=patient.id).order_by(
        LabRequest.created_at.desc()
    ).limit(50).all()
    return render_template('portal/lab_results.html', patient=patient, lab_requests=requests)

@portal_bp.route('/radiology-results')
@login_required
def radiology_results():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
    requests = RadiologyRequest.query.filter_by(patient_id=patient.id).order_by(
        RadiologyRequest.created_at.desc()
    ).limit(50).all()
    return render_template('portal/radiology_results.html', patient=patient, radiology_requests=requests)

@portal_bp.route('/bills')
@login_required
def bills():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
    invoices = Invoice.query.filter_by(patient_id=patient.id).order_by(
        Invoice.created_at.desc()
    ).limit(50).all()
    payments = Payment.query.filter_by(patient_id=patient.id).order_by(
        Payment.payment_date.desc()
    ).limit(50).all()
    return render_template('portal/bills.html', patient=patient, invoices=invoices, payments=payments)

@portal_bp.route('/vaccinations')
@login_required
def vaccinations():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
    items = Immunization.query.filter_by(patient_id=patient.id).order_by(
        Immunization.administration_date.desc()
    ).all()
    return render_template('portal/vaccinations.html', patient=patient, immunizations=items)

@portal_bp.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    patient = _get_patient_from_user()
    if not patient:
        return redirect(url_for('portal.index'))
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
