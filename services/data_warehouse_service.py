from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.extensions import db
from models.appointment import Appointment
from models.patient import Patient
from models.payment import Payment
from models.visit import Visit


class DataWarehouseService:
    @staticmethod
    def export_snapshot(days=30):
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        visits = db.session.execute(
            select(func.count()).select_from(Visit).filter(Visit.created_at >= start)
        ).scalar()
        appointments = db.session.execute(
            select(func.count()).select_from(Appointment).filter(Appointment.starts_at >= start)
        ).scalar()
        payments_total = (
            db.session.execute(
                select(db.func.sum(Payment.amount)).filter(Payment.created_at >= start)
            ).scalar()
            or 0
        )
        new_patients = db.session.execute(
            select(func.count()).select_from(Patient).filter(Patient.created_at >= start)
        ).scalar()
        return {
            'window_days': days,
            'visits': int(visits or 0),
            'appointments': int(appointments or 0),
            'payments_total': float(payments_total or 0),
            'new_patients': int(new_patients or 0),
        }
