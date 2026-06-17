import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.radiology_request import RadiologyRequest
from models.radiology_test import RadiologyResult


class RadiologyRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()

        suf = uuid.uuid4().hex[:8]
        self.radiology_username = f'radiology_user_test_{suf}'
        rad = User(username=self.radiology_username, email=f'radiology_test_{suf}@example.com', full_name='Radiology User', role='radiology')
        rad.set_password('p')
        db.session.add(rad)

        self.doctor_username = f'doctor_radiology_test_{suf}'
        doc = User(username=self.doctor_username, email=f'doctor_radiology_test_{suf}@example.com', full_name='Doctor User', role='doctor')
        doc.set_password('p')
        db.session.add(doc)

        pat = Patient(first_name='Pat', last_name=f'Rad{suf}', phone='0590000202', national_id=f'NI{suf}')
        db.session.add(pat)
        db.session.flush()

        visit = Visit(patient_id=pat.id, doctor_id=doc.id, status='IN_PROGRESS')
        db.session.add(visit)
        db.session.flush()

        req = RadiologyRequest(visit_id=visit.id, patient_id=pat.id, requested_by=doc.id, status='REQUESTED', modality='CT')
        db.session.add(req)
        db.session.commit()

        self.visit_id = visit.id
        self.request_id = req.id

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

    def test_radiology_complete_marks_critical_and_quality_page(self):
        r = self._login(self.radiology_username, 'p')
        self.assertEqual(r.status_code, 302)

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post(
            f'/radiology/worklist/complete/{self.request_id}',
            data={
                'csrf_token': token,
                'action': 'finalize',
                'test_name': 'CT Scan',
                'body_part': 'Head',
                'description': 'desc',
                'results': 'Impression text',
                'findings': 'Findings text',
                'recommendations': 'notes',
                'is_critical': '1'
            },
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

        res = RadiologyResult.query.filter_by(request_id=self.request_id).first()
        self.assertIsNotNone(res)
        self.assertTrue(res.is_critical)

        q = self.client.get('/radiology/quality', follow_redirects=True)
        self.assertEqual(q.status_code, 200)

        r2 = self._login(self.doctor_username, 'p')
        self.assertEqual(r2.status_code, 302)
        pd = self.client.get(f'/doctor/patient-details/{self.visit_id}', follow_redirects=True)
        self.assertEqual(pd.status_code, 200)
        self.assertIn('نتائج أشعة حرجة', pd.data.decode('utf-8', errors='ignore'))


if __name__ == '__main__':
    unittest.main()

