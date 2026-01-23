import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.lab_request import LabRequest, LabResult
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent


class LabRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.manager_username = f'manager_lab_test_{suf}'
        u = User(username=self.manager_username, email=f'manager_lab_test_{suf}@example.com', full_name='Manager Lab', role='manager')
        u.set_password('p')
        db.session.add(u)
        self.lab_username = f'lab_user_test_{suf}'
        labu = User(username=self.lab_username, email=f'lab_test_{suf}@example.com', full_name='Lab User', role='lab')
        labu.set_password('p')
        db.session.add(labu)
        self.doctor_username = f'doctor_lab_test_{suf}'
        doc = User(username=self.doctor_username, email=f'doctor_lab_test_{suf}@example.com', full_name='Doctor User', role='doctor')
        doc.set_password('p')
        db.session.add(doc)
        self.reception_username = f'reception_lab_test_{suf}'
        rec = User(username=self.reception_username, email=f'reception_lab_test_{suf}@example.com', full_name='Reception User', role='reception')
        rec.set_password('p')
        db.session.add(rec)
        db.session.commit()

        pat = Patient(first_name='Pat', last_name=f'Lab{suf}', phone='0590000101', national_id=f'{uuid.uuid4().int % 10**9}')
        db.session.add(pat)
        db.session.flush()
        visit = Visit(patient_id=pat.id, doctor_id=doc.id, status='IN_PROGRESS')
        db.session.add(visit)
        db.session.flush()
        req = LabRequest(visit_id=visit.id, patient_id=pat.id, requested_by=doc.id, status='REQUESTED')
        db.session.add(req)
        db.session.commit()
        self.visit_id = visit.id
        self.lab_request_id = req.id

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, username, password):
        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        return self.client.post('/auth/login', data={'username': username, 'password': password, 'csrf_token': token}, follow_redirects=False)

    def test_lab_dashboard_and_tests(self):
        r = self._login(self.manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/lab/dashboard', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.get('/lab/tests', follow_redirects=False)
        self.assertEqual(r2.status_code, 302)

    def test_lab_critical_result_sets_flag_and_shows_alert_for_doctor(self):
        r = self._login(self.lab_username, 'p')
        self.assertEqual(r.status_code, 302)

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post(
            f'/lab/worklist/request/{self.lab_request_id}',
            data={
                'csrf_token': token,
                'action': 'finalize',
                'result_id[]': [''],
                'test_code[]': ['HB'],
                'test_name[]': ['Hemoglobin'],
                'value[]': ['4.0'],
                'unit[]': ['g/dL'],
                'reference_range[]': ['12-16'],
                'is_critical[]': ['1'],
                'status[]': ['VALIDATED'],
                'notes[]': ['critical low']
            },
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

        res = LabResult.query.filter_by(request_id=self.lab_request_id).first()
        self.assertIsNotNone(res)
        self.assertTrue(res.is_critical)

        r2 = self._login(self.doctor_username, 'p')
        self.assertEqual(r2.status_code, 302)
        resp2 = self.client.get(f'/doctor/patient-details/{self.visit_id}', follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn('نتائج مختبر حرجة', resp2.data.decode('utf-8', errors='ignore'))

    def test_lab_quality_reagents_and_qc_pages(self):
        r = self._login(self.lab_username, 'p')
        self.assertEqual(r.status_code, 302)

        r1 = self.client.get('/lab/quality', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        r2 = self.client.post('/lab/quality-control', data={
            'csrf_token': token,
            'test_code': 'HB',
            'test_name': 'Hemoglobin QC',
            'control_level': 'NORMAL',
            'measured_value': '12.0',
            'unit': 'g/dL',
            'expected_range': '11-15',
            'status': 'PASS',
            'notes': 'ok'
        }, follow_redirects=True)
        self.assertEqual(r2.status_code, 200)
        self.assertGreater(LabQualityControlEntry.query.count(), 0)

        r3 = self.client.post('/lab/reagents/add', data={
            'csrf_token': token,
            'name': 'Reagent A',
            'supplier': 'Vendor',
            'lot_number': 'LOT-1',
            'unit': 'mL',
            'stock_quantity': '5',
            'minimum_stock': '10',
            'expiry_date': '2099-01-01',
            'is_active': 'on'
        }, follow_redirects=True)
        self.assertEqual(r3.status_code, 200)
        self.assertGreater(LabReagent.query.count(), 0)

        r4 = self.client.get('/lab/reagents?stock=low', follow_redirects=True)
        self.assertEqual(r4.status_code, 200)


if __name__ == '__main__':
    unittest.main()
