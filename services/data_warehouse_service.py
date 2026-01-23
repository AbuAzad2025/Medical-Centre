from datetime import datetime, timedelta, timezone
from app_factory import db
from models.visit import Visit
from models.appointment import Appointment
from models.payment import Payment
from models.patient import Patient

class DataWarehouseService:
    @staticmethod
    def export_snapshot(days=30):
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        visits = Visit.query.filter(Visit.created_at >= start).count()
        appointments = Appointment.query.filter(Appointment.starts_at >= start).count()
        payments_total = db.session.query(db.func.sum(Payment.amount)).filter(Payment.created_at >= start).scalar() or 0
        new_patients = Patient.query.filter(Patient.created_at >= start).count()
        return {
            'window_days': days,
            'visits': int(visits or 0),
            'appointments': int(appointments or 0),
            'payments_total': float(payments_total or 0),
            'new_patients': int(new_patients or 0)
        }
