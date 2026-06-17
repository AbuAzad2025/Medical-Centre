import unittest
from datetime import datetime, timedelta
from app_factory import create_app, db
from services.notification_service import NotificationService
from models.notification import Notification
from models.visit import Visit
from models.patient import Patient
from models.user import User
from models.department import Department
from models.appointment import Appointment


class NotificationAlertsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.patient = Patient(first_name='Test', last_name='Patient')
        db.session.add(self.patient)
        self.dept = Department(name='Reception', name_ar='الاستقبال')
        db.session.add(self.dept)
        self.doctor = User(username='alert_doc', email='alert_doc@example.com', full_name='Alert Doctor', role='doctor')
        self.doctor.set_password('p')
        db.session.add(self.doctor)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            for t in tables:
                db.session.execute(db.text(f"DELETE FROM {t}"))
        db.session.commit()
        db.engine.dispose()
        db.session.remove()
        self.ctx.pop()

    def test_send_debt_reminders(self):
        v = Visit(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            payment_status='DEBT',
            total_amount=200,
            paid_amount=50,
            is_force_payment=True,
        )
        # اجعلها قديمة أكثر من 7 أيام
        v.created_at = datetime.now() - timedelta(days=8)
        db.session.add(v)
        db.session.commit()
        res = NotificationService.send_debt_reminders()
        self.assertTrue(res['success'])
        self.assertGreaterEqual(res['reminders_sent'], 1)
        cnt = Notification.query.count()
        self.assertGreaterEqual(cnt, 1)

    def test_send_insurance_followup_alerts(self):
        v = Visit(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            payment_method='insurance',
            payment_status='PARTIAL',
            insurance_provider='ACME',
            insurance_policy_number='POL123',
            insurance_amount=120,
        )
        v.created_at = datetime.now() - timedelta(days=20)
        db.session.add(v)
        db.session.commit()
        res = NotificationService.send_insurance_followup_alerts()
        self.assertTrue(res['success'])
        self.assertGreaterEqual(res['alerts_sent'], 1)

    def test_send_force_payment_approval_alerts(self):
        v1 = Visit(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_force_payment=True,
            total_amount=300,
            force_payment_reason='Urgent case',
        )
        v2 = Visit(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_force_payment=True,
            total_amount=200,
            force_payment_reason='No funds',
        )
        db.session.add_all([v1, v2])
        db.session.commit()
        res = NotificationService.send_force_payment_approval_alerts()
        self.assertTrue(res['success'])
        self.assertEqual(res['pending_count'], 2)

    def test_send_appointment_reminders_fallback(self):
        ap = Appointment(
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            department_id=self.dept.id,
            starts_at=datetime.now() + timedelta(hours=1),
            status='SCHEDULED'
        )
        # لا رقم هاتف للمريض ليفعل مسار الاستقبال
        db.session.add(ap)
        db.session.commit()
        res = NotificationService.send_appointment_reminders()
        self.assertTrue(res['success'])
        self.assertGreaterEqual(res['fallback_notified'], 1)


if __name__ == '__main__':
    unittest.main()
