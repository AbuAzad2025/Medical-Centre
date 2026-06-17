import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.department import Department
from models.patient import Patient
from models.visit import Visit
from models.queue_management import QueueManagement
from sqlalchemy import desc

class DoctorFlowArchiveTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.dept = Department(name='Internal Medicine', name_ar='الباطنية', is_active=True)
        db.session.add(self.dept)
        self.doctor = User(username=f'doctor_{suf}', email=f'd_{suf}@example.com', full_name='Doctor Test', role='doctor', is_active=True, department_id=None)
        self.doctor.set_password('p')
        db.session.add(self.doctor)
        self.reception = User(username=f'reception_{suf}', email=f'r_{suf}@example.com', full_name='Reception Test', role='reception', is_active=True)
        self.reception.set_password('p')
        db.session.add(self.reception)
        self.patient = Patient(national_id=f'NI{suf}', first_name='أحمد', last_name='محمد', phone='0590000000', gender='male')
        db.session.add(self.patient)
        db.session.commit()
        self.visit = Visit(patient_id=self.patient.id, department_id=self.dept.id, doctor_id=self.doctor.id, status='OPEN', payment_status='PAID', total_amount=50, paid_amount=50, visit_type='REGULAR', payment_method='cash')
        db.session.add(self.visit)
        db.session.flush()
        ticket = QueueManagement(queue_number=f'Q{suf}', patient_id=self.patient.id, visit_id=self.visit.id, department_id=self.dept.id, status='waiting', payment_status='paid')
        db.session.add(ticket)
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

    def _login(self, username, password):
        return self.client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)

    def test_doctor_start_and_end_treatment_then_archive(self):
        r1 = self._login(self.doctor.username, 'p')
        self.assertIn(r1.status_code, (302, 200))
        r2 = self.client.post(f'/doctor/start-treatment/{self.visit.id}', follow_redirects=False)
        self.assertIn(r2.status_code, (302, 200))
        t = QueueManagement.query.filter_by(visit_id=self.visit.id, department_id=self.dept.id).order_by(desc(QueueManagement.id)).first()
        self.assertIsNotNone(t)
        diag = {
            'chief_complaint':'Headache',
            'symptoms':'Pain',
            'diagnosis':'Migraine',
            'differential_diagnosis':'Tension',
            'treatment_plan':'Rest',
            'follow_up_notes':'Check',
            'blood_pressure':'120/80',
            'heart_rate':'70',
            'temperature':'36.8',
            'respiratory_rate':'16'
        }
        r3 = self.client.post(f'/doctor/diagnosis/{self.visit.id}', data=diag, follow_redirects=False)
        self.assertIn(r3.status_code, (302, 200))
        t2 = QueueManagement.query.filter_by(visit_id=self.visit.id, department_id=self.dept.id).order_by(desc(QueueManagement.id)).first()
        if t2:
            t2.status = 'in_progress'
            db.session.commit()
        r4 = self.client.post(f'/doctor/end-treatment/{self.visit.id}', follow_redirects=False)
        self.assertIn(r4.status_code, (302, 200))
        v = db.session.get(Visit, self.visit.id)
        self.assertEqual(v.status, 'COMPLETED')
        self.client.get('/auth/logout')
        r4 = self._login(self.reception.username, 'p')
        self.assertIn(r4.status_code, (302, 200))
        r5 = self.client.post(f'/reception/visits/{self.visit.id}/archive', follow_redirects=False)
        self.assertIn(r5.status_code, (302, 200))
        v2 = db.session.get(Visit, self.visit.id)
        self.assertEqual(v2.status, 'ARCHIVED')

if __name__ == '__main__':
    unittest.main()
