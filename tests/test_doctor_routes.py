import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.nurse import Nurse, VitalSigns
from models.follow_up import FollowUpRequest


class DoctorRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.manager_username = f'manager_user_test_{suf}'
        u = User(username=self.manager_username, email=f'manager_test_{suf}@example.com', full_name='Manager User', role='manager')
        u.set_password('p')
        db.session.add(u)
        self.doctor_username = f'doctor_user_test_{suf}'
        d = User(username=self.doctor_username, email=f'doctor_test_{suf}@example.com', full_name='Doctor User', role='doctor')
        d.set_password('p')
        db.session.add(d)
        self.reception_username = f'reception_user_test_{suf}'
        r = User(username=self.reception_username, email=f'reception_test_{suf}@example.com', full_name='Reception User', role='reception')
        r.set_password('p')
        db.session.add(r)
        nurse_user = User(username=f'nurse_user_test_{suf}', email=f'nurse_test_{suf}@example.com', full_name='Nurse User', role='nurse')
        nurse_user.set_password('p')
        db.session.add(nurse_user)
        db.session.commit()
        nurse_profile = Nurse(user_id=nurse_user.id, license_number=f'LIC-{suf}')
        db.session.add(nurse_profile)
        patient = Patient(first_name='Test', last_name=f'Patient{suf}')
        db.session.add(patient)
        db.session.flush()
        visit = Visit(patient_id=patient.id, doctor_id=d.id, status='IN_PROGRESS')
        db.session.add(visit)
        db.session.flush()
        vs = VitalSigns(
            patient_id=patient.id,
            nurse_id=nurse_profile.id,
            blood_pressure_systolic=120,
            blood_pressure_diastolic=80,
            heart_rate=75,
            temperature=36.8,
            oxygen_saturation=98,
            respiratory_rate=18,
        )
        db.session.add(vs)
        db.session.commit()
        self.visit_id = visit.id
        self.patient_id = patient.id

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
        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        return self.client.post('/auth/login', data={'username': username, 'password': password, 'csrf_token': token}, follow_redirects=False)

    def test_doctor_dashboard_and_queue(self):
        r = self._login(self.manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/doctor/dashboard', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.get('/doctor/patient-queue', follow_redirects=True)
        self.assertEqual(r2.status_code, 200)

    def test_patient_details_shows_latest_nurse_vitals(self):
        r = self._login(self.doctor_username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get(f'/doctor/patient-details/{self.visit_id}', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode('utf-8')
        self.assertIn('آخر قياس تمريض', body)
        self.assertIn('120/80', body)
        self.assertIn('SpO2', body)

    def test_patient_timeline_and_follow_up_request_created(self):
        r = self._login(self.doctor_username, 'p')
        self.assertEqual(r.status_code, 302)

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post(
            f'/doctor/save-visit-summary/{self.visit_id}',
            data={'csrf_token': token, 'diagnosis': 'Dx', 'treatment_plan': 'Plan', 'follow_up_date': '2099-01-01', 'follow_up_notes': 'notes'},
            follow_redirects=False
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload.get('success'))

        fu = FollowUpRequest.query.filter_by(source_visit_id=self.visit_id).first()
        self.assertIsNotNone(fu)
        self.assertEqual(fu.status, 'PENDING')

        resp2 = self.client.get(f'/doctor/patient-timeline/{self.patient_id}', follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        body = resp2.data.decode('utf-8', errors='ignore')
        self.assertIn('الخط الزمني للمريض', body)
        self.assertIn('متابعة مقترحة', body)

        r2 = self._login(self.reception_username, 'p')
        self.assertEqual(r2.status_code, 302)
        resp3 = self.client.get('/reception/follow-ups', follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)
        self.assertIn('المتابعات', resp3.data.decode('utf-8', errors='ignore'))

    def test_doctor_note_templates_api_and_notes_page(self):
        r = self._login(self.doctor_username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/doctor/api/note-templates', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))
        self.assertTrue(isinstance(data.get('templates'), list))

        resp2a = self.client.get(f'/doctor/notes/{self.visit_id}', follow_redirects=False)
        self.assertEqual(resp2a.status_code, 200, f"expected notes 200, got {resp2a.status_code}, location={resp2a.headers.get('Location')}")
        resp2 = self.client.get(f'/doctor/notes/{self.visit_id}', follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        body = resp2.data.decode('utf-8', errors='ignore')
        import re
        m = re.search(r'<title>(.*?)</title>', body, re.IGNORECASE | re.DOTALL)
        title = (m.group(1).strip() if m else '')[:120]
        visit = db.session.get(Visit, self.visit_id)
        doctor_user = User.query.filter_by(username=self.doctor_username).first()
        visit_doctor_id = getattr(visit, 'doctor_id', None) if visit else None
        doctor_user_id = getattr(doctor_user, 'id', None) if doctor_user else None
        self.assertTrue(
            'note_template_select' in body,
            f"notes page missing template select; title={title!r}; visit_doctor_id={visit_doctor_id}; doctor_user_id={doctor_user_id}; login_marker={('تسجيل الدخول' in body)}"
        )


if __name__ == '__main__':
    unittest.main()
