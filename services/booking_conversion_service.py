"""
OnlineBookingConversionService + AppointmentCheckinService
"""
from datetime import datetime, timezone
from flask import g
from app.extensions import db
from app.shared.enums import VisitState, AppointmentState, BookingState, OrderState


class AppointmentCheckinService:
    @staticmethod
    def checkin(appointment) -> dict:
        from models.visit import Visit
        visit = Visit(
            tenant_id=getattr(g, 'tenant_id', None),
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            department_id=appointment.department_id,
            status=VisitState.CHECKED_IN,
            visit_type='REGULAR',
            visit_date=datetime.now(timezone.utc).date(),
        )
        db.session.add(visit)
        db.session.flush()
        appointment.status = AppointmentState.CHECKED_IN
        db.session.commit()
        return {"visit_id": visit.id, "status": VisitState.CHECKED_IN}

    @staticmethod
    def create_walkin(patient_id: int, doctor_id: int | None = None, department_id: int | None = None) -> dict:
        from models.visit import Visit
        visit = Visit(
            tenant_id=getattr(g, 'tenant_id', None),
            patient_id=patient_id,
            doctor_id=doctor_id,
            department_id=department_id,
            status=VisitState.OPEN,
            visit_type='REGULAR',
            visit_date=datetime.now(timezone.utc).date(),
        )
        db.session.add(visit)
        db.session.commit()
        return {"visit_id": visit.id, "status": VisitState.OPEN}


class OnlineBookingConversionService:
    @staticmethod
    def convert_to_visit(booking) -> dict:
        from models.patient import Patient
        from models.visit import Visit
        tenant_id = getattr(g, 'tenant_id', None) or getattr(booking, 'tenant_id', None)

        patient = Patient.query.filter_by(tenant_id=tenant_id, phone=booking.phone).first()
        is_new_patient = patient is None
        if not patient:
            patient = Patient(
                tenant_id=tenant_id,
                first_name=booking.first_name,
                last_name=booking.last_name,
                phone=booking.phone,
                national_id=booking.national_id or None,
            )
            db.session.add(patient)
            db.session.flush()

        visit = Visit(
            tenant_id=tenant_id,
            patient_id=patient.id,
            doctor_id=booking.doctor_id or None,
            department_id=getattr(booking, 'department_id', None),
            status=VisitState.OPEN,
            visit_type='REGULAR',
            visit_date=getattr(booking, 'appointment_date', None) or datetime.now(timezone.utc).date(),
            notes=f"Converted from online booking #{booking.booking_reference}",
        )
        db.session.add(visit)
        db.session.flush()
        booking.status = BookingState.CONVERTED
        db.session.commit()
        return {"visit_id": visit.id, "patient_id": patient.id, "is_new_patient": is_new_patient}

    @staticmethod
    def convert_to_appointment(booking) -> dict:
        from models.appointment import Appointment
        tenant_id = getattr(g, 'tenant_id', None) or getattr(booking, 'tenant_id', None)
        from models.patient import Patient

        patient = Patient.query.filter_by(tenant_id=tenant_id, phone=booking.phone).first()
        if not patient:
            patient = Patient(
                tenant_id=tenant_id,
                first_name=booking.first_name,
                last_name=booking.last_name,
                phone=booking.phone,
            )
            db.session.add(patient)
            db.session.flush()

        appt_date = getattr(booking, 'appointment_date', None) or datetime.now(timezone.utc).date()
        appt_time = getattr(booking, 'appointment_time', None)
        if appt_time:
            starts_at = datetime.combine(appt_date, appt_time, tzinfo=timezone.utc)
        else:
            starts_at = datetime.combine(appt_date, datetime.min.time(), tzinfo=timezone.utc)

        appointment = Appointment(
            tenant_id=tenant_id,
            patient_id=patient.id,
            doctor_id=booking.doctor_id or None,
            department_id=getattr(booking, 'department_id', None),
            starts_at=starts_at,
            status=AppointmentState.SCHEDULED,
            notes=f"Online booking #{booking.booking_reference}",
        )
        db.session.add(appointment)
        db.session.flush()
        booking.status = BookingState.CONVERTED
        db.session.commit()
        return {"appointment_id": appointment.id, "patient_id": patient.id}

    @staticmethod
    def convert_based_on_profile(booking, profile_code: str | None = None) -> dict:
        if not profile_code:
            profile_code = getattr(g, 'product_profile', None)
        if profile_code in ('standalone_lab',):
            return OnlineBookingConversionService._convert_to_lab_order(booking)
        elif profile_code in ('standalone_radiology',):
            return OnlineBookingConversionService._convert_to_radiology_order(booking)
        elif profile_code in ('private_doctor_clinic',):
            return OnlineBookingConversionService.convert_to_appointment(booking)
        else:
            return OnlineBookingConversionService.convert_to_visit(booking)

    @staticmethod
    def _convert_to_lab_order(booking):
        from models.patient import Patient
        from models.visit import Visit
        from models.lab_request import LabRequest
        tenant_id = getattr(g, 'tenant_id', None) or getattr(booking, 'tenant_id', None)

        patient = Patient.query.filter_by(tenant_id=tenant_id, phone=booking.phone).first()
        if not patient:
            patient = Patient(tenant_id=tenant_id, first_name=booking.first_name, last_name=booking.last_name, phone=booking.phone)
            db.session.add(patient)
            db.session.flush()

        visit = Visit(
            tenant_id=tenant_id,
            patient_id=patient.id,
            doctor_id=booking.doctor_id or None,
            department_id=getattr(booking, 'department_id', None),
            status=VisitState.OPEN,
            visit_type='REGULAR',
            visit_date=getattr(booking, 'appointment_date', None) or datetime.now(timezone.utc).date(),
            notes=f"Lab booking #{booking.booking_reference}",
        )
        db.session.add(visit)
        db.session.flush()

        lab_request = LabRequest(
            tenant_id=tenant_id,
            visit_id=visit.id,
            patient_id=patient.id,
            requested_by=None,
            status=OrderState.REQUESTED,
            notes=f"From online booking #{booking.booking_reference}",
        )
        db.session.add(lab_request)
        db.session.flush()
        from services.barcode_service import setup_barcode_for_lab_request
        setup_barcode_for_lab_request(lab_request, tenant_id=tenant_id)
        booking.status = BookingState.CONVERTED
        db.session.commit()
        return {"lab_request_id": lab_request.id, "patient_id": patient.id}

    @staticmethod
    def _convert_to_radiology_order(booking):
        from models.patient import Patient
        from models.visit import Visit
        from models.radiology_request import RadiologyRequest
        tenant_id = getattr(g, 'tenant_id', None) or getattr(booking, 'tenant_id', None)

        patient = Patient.query.filter_by(tenant_id=tenant_id, phone=booking.phone).first()
        if not patient:
            patient = Patient(tenant_id=tenant_id, first_name=booking.first_name, last_name=booking.last_name, phone=booking.phone)
            db.session.add(patient)
            db.session.flush()

        visit = Visit(
            tenant_id=tenant_id,
            patient_id=patient.id,
            doctor_id=booking.doctor_id or None,
            department_id=getattr(booking, 'department_id', None),
            status=VisitState.OPEN,
            visit_type='REGULAR',
            visit_date=getattr(booking, 'appointment_date', None) or datetime.now(timezone.utc).date(),
            notes=f"Radiology booking #{booking.booking_reference}",
        )
        db.session.add(visit)
        db.session.flush()

        rad_request = RadiologyRequest(
            tenant_id=tenant_id,
            visit_id=visit.id,
            patient_id=patient.id,
            requested_by=None,
            status=OrderState.REQUESTED,
        )
        db.session.add(rad_request)
        db.session.flush()
        booking.status = BookingState.CONVERTED
        db.session.commit()
        return {"radiology_request_id": rad_request.id, "patient_id": patient.id}