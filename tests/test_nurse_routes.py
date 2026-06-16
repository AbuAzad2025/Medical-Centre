import unittest
import uuid
from app_factory import create_app, db
from models.nurse import Nurse, VitalSigns, MedicationAdministrationLog
from models.patient import Patient
from models.user import User
from models.visit import Visit
from models.medication import Medication, Prescription, PrescriptionItem
from models.task_management import Task


class NurseRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.nurse_manager_username = f'manager_nurse_test_{suf}'
        u = User(username=self.nurse_manager_username, email=f'mn_test_{suf}@example.com', full_name='Manager Nurse', role='manager')
        u.set_password('p')
        db.session.add(u)
        self.nurse_username = f'nurse_test_{suf}'
        nurse_user = User(username=self.nurse_username, email=f'nurse_test_{suf}@example.com', full_name='Nurse User', role='nurse')
        nurse_user.set_password('p')
        db.session.add(nurse_user)
        db.session.commit()

        nurse_profile = Nurse(user_id=nurse_user.id, license_number=f'LIC-{suf}')
        db.session.add(nurse_profile)

        patient = Patient(first_name='Test', last_name=f'Patient{suf}')
        db.session.add(patient)
        doctor = User(username=f'dr_{suf}', email=f'dr_{suf}@example.com', full_name='Doctor', role='doctor')
        doctor.set_password('p')
        db.session.add(doctor)
        db.session.commit()

        self.patient_id = patient.id
        self.doctor_id = doctor.id

        visit = Visit(patient_id=patient.id, doctor_id=doctor.id)
        db.session.add(visit)
        db.session.flush()
        self.visit_id = visit.id

        med = Medication(scientific_name='Amoxicillin', trade_name='Amox', dosage_form='tablet', strength='500mg', price=5, stock_quantity=10, minimum_stock=1)
        db.session.add(med)
        db.session.flush()
        self.medication_id = med.id

        pres = Prescription(patient_id=patient.id, doctor_id=doctor.id, visit_id=visit.id, prescription_number=f'RX-{suf}', status='active')
        db.session.add(pres)
        db.session.flush()
        item = PrescriptionItem(prescription_id=pres.id, medication_id=med.id, dosage='1', quantity=2, duration_days=5, instructions='after food', unit_price=5, total_price=10)
        db.session.add(item)
        db.session.commit()
        self.prescription_item_id = item.id

    def tearDown(self):
        db.session.rollback()
        # Use TRUNCATE TABLE instead of DROP SCHEMA to avoid enum type recreation issues
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            db.session.execute(db.text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE"))
        db.session.commit()
        db.engine.dispose()
        db.session.remove()
        self.ctx.pop()

    def _login(self, username, password):
        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        return self.client.post('/auth/login', data={'username': username, 'password': password, 'csrf_token': token}, follow_redirects=False)

    def test_nurse_dashboard(self):
        r = self._login(self.nurse_manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/nurse/dashboard', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

    def test_record_vital_signs_persists(self):
        r = self._login(self.nurse_username, 'p')
        self.assertEqual(r.status_code, 302)

        resp = self.client.post(
            f'/nurse/record-vital-signs/{self.patient_id}',
            data={
                'blood_pressure_systolic': '120',
                'blood_pressure_diastolic': '80',
                'heart_rate': '75',
                'temperature': '36.8',
                'oxygen_saturation': '98',
                'respiratory_rate': '18',
                'weight': '70.5',
                'height': '175.0',
                'notes': 'ok'
            }
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload.get('success'))

        rec = VitalSigns.query.filter_by(patient_id=self.patient_id).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.blood_pressure_systolic, 120)
        self.assertEqual(rec.blood_pressure_diastolic, 80)
        self.assertEqual(rec.heart_rate, 75)

    def test_vital_signs_page_loads(self):
        r = self._login(self.nurse_username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get(f'/nurse/vital-signs?patient_id={self.patient_id}', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_tasks_page_loads(self):
        r = self._login(self.nurse_username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/nurse/tasks', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_patient_care_page_loads(self):
        r = self._login(self.nurse_username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/nurse/patient-care', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_create_task_and_update_status(self):
        r = self._login(self.nurse_username, 'p')
        self.assertEqual(r.status_code, 302)

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post('/nurse/tasks/create', data={
            'csrf_token': token,
            'title': 'Follow-up vitals',
            'description': 'check patient',
            'priority': 'high',
            'visit_id': str(self.visit_id)
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        t = Task.query.filter_by(assigned_to=User.query.filter_by(username=self.nurse_username).first().id, title='Follow-up vitals').first()
        self.assertIsNotNone(t)

        resp2 = self.client.post(f'/nurse/tasks/{t.id}/status', data={
            'csrf_token': token,
            'status': 'completed'
        }, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        t2 = db.session.get(Task, t.id)
        self.assertEqual(t2.status, 'completed')

    def test_nurse_reports_page_loads(self):
        r = self._login(self.nurse_username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/nurse/reports', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_administer_medication_creates_log(self):
        r = self._login(self.nurse_username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.post(
            f'/nurse/administer-medication/{self.prescription_item_id}',
            data={'notes': 'done'},
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        log = MedicationAdministrationLog.query.filter_by(prescription_item_id=self.prescription_item_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.visit_id, self.visit_id)


if __name__ == '__main__':
    unittest.main()
