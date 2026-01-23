import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.department import Department
from models.patient import Patient
from models.visit import Visit
from models.medication import Prescription
import tempfile
import shutil
from io import BytesIO

class FhirLabRadPharmacyTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.dept = Department(name='Internal Medicine', name_ar='الباطنية', is_active=True)
        db.session.add(self.dept)
        self.lab_dept = Department(name='Lab', name_ar='مختبر', is_active=True)
        db.session.add(self.lab_dept)
        self.rad_dept = Department(name='Radiology', name_ar='أشعة', is_active=True)
        db.session.add(self.rad_dept)
        self.doctor = User(username=f'doctor_{suf}', email=f'd_{suf}@example.com', full_name='Doctor', role='doctor', is_active=True)
        self.doctor.set_password('p')
        db.session.add(self.doctor)
        self.reception = User(username=f'reception_{suf}', email=f'r_{suf}@example.com', full_name='Reception', role='reception', is_active=True)
        self.reception.set_password('p')
        db.session.add(self.reception)
        self.lab = User(username=f'lab_{suf}', email=f'l_{suf}@example.com', full_name='Lab', role='lab', is_active=True)
        self.lab.set_password('p')
        db.session.add(self.lab)
        self.rad = User(username=f'rad_{suf}', email=f'ra_{suf}@example.com', full_name='Rad', role='radiology', is_active=True)
        self.rad.set_password('p')
        db.session.add(self.rad)
        self.ph = User(username=f'ph_{suf}', email=f'ph_{suf}@example.com', full_name='Pharmacist', role='pharmacist', is_active=True)
        self.ph.set_password('p')
        db.session.add(self.ph)
        self.patient = Patient(national_id=f'NI{suf}', first_name='سارة', last_name='أحمد', phone='0590000001', gender='female')
        db.session.add(self.patient)
        db.session.commit()
        self.visit = Visit(patient_id=self.patient.id, department_id=self.dept.id, doctor_id=self.doctor.id, status='OPEN', payment_status='PAID', total_amount=80, paid_amount=80, visit_type='REGULAR', payment_method='cash')
        db.session.add(self.visit)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, u, p):
        return self.client.post('/auth/login', data={'username': u, 'password': p}, follow_redirects=False)

    def test_fhir_endpoints(self):
        self._login(self.reception.username, 'p')
        rp = self.client.get(f'/reception/api/fhir/patient/{self.patient.id}')
        self.assertEqual(rp.status_code, 200)
        rv = self.client.get(f'/reception/api/fhir/encounter/{self.visit.id}')
        self.assertEqual(rv.status_code, 200)

    def test_lab_radiology_worklist(self):
        self._login(self.doctor.username, 'p')
        lr = self.client.post(f'/doctor/lab-request/{self.visit.id}', data={'test_name':'CBC','test_description':'CBC','urgency':'normal','notes':'N'}, follow_redirects=False)
        rr = self.client.post(f'/doctor/radiology-request/{self.visit.id}', data={'test_name':'Chest X-Ray','test_description':'XR','urgency':'normal','notes':'N'}, follow_redirects=False)
        self.client.get('/auth/logout')
        self._login(self.lab.username, 'p')
        api_lr = self.client.get('/lab/api/worklist?visit_id={}&status=REQUESTED'.format(self.visit.id))
        self.assertEqual(api_lr.status_code, 200)
        self.client.get('/auth/logout')
        self._login(self.rad.username, 'p')
        api_rr = self.client.get('/radiology/api/worklist?visit_id={}&status=REQUESTED'.format(self.visit.id))
        self.assertEqual(api_rr.status_code, 200)

    def test_radiology_claim_and_complete_form(self):
        from models.radiology_request import RadiologyRequest
        from models.radiology_test import RadiologyResult
        from models.file_management import FileUpload

        req = RadiologyRequest(visit_id=self.visit.id, patient_id=self.patient.id, requested_by=self.doctor.id, status='REQUESTED', modality='XRay', body_part='Chest', notes='N')
        db.session.add(req)
        db.session.commit()

        self._login(self.rad.username, 'p')
        tmp_dir = tempfile.mkdtemp(prefix='rad_upload_')
        self.app.config['UPLOAD_FOLDER'] = tmp_dir
        try:
            c = self.client.post(f'/radiology/worklist/claim/{req.id}', data={}, follow_redirects=False)
            self.assertIn(c.status_code, (302, 200))

            d = self.client.post(
                f'/radiology/worklist/complete/{req.id}',
                data={
                    'action': 'finalize',
                    'results': 'Normal study',
                    'findings': 'No acute findings',
                    'recommendations': 'Follow up as needed',
                    'image_upload': (BytesIO(b'abc'), 'test.png')
                },
                content_type='multipart/form-data',
                follow_redirects=False
            )
            self.assertIn(d.status_code, (302, 200))

            req2 = db.session.get(RadiologyRequest, req.id)
            self.assertEqual((req2.status or '').upper(), 'DONE')
            res = RadiologyResult.query.filter_by(request_id=req.id).first()
            self.assertIsNotNone(res)
            fu = FileUpload.query.filter_by(related_entity_type='radiology_result', related_entity_id=res.id).first()
            self.assertIsNotNone(fu)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_radiology_report_templates_api(self):
        self._login(self.rad.username, 'p')
        r = self.client.get('/radiology/api/report-templates')
        self.assertEqual(r.status_code, 200)
        data = r.get_json() or {}
        templates = data.get('templates') or []
        self.assertTrue(isinstance(templates, list))
        self.assertTrue(len(templates) >= 3)

        c = self.client.post('/radiology/api/report-templates', json={
            'name': 'قالب اختبار',
            'modality': 'XRAY',
            'findings': 'F {{BODY_PART}}',
            'impression': 'I',
            'recommendations': 'R',
            'is_active': True
        })
        self.assertIn(c.status_code, (200, 201))
        cid = (c.get_json() or {}).get('id')
        self.assertTrue(cid)

        r2 = self.client.get('/radiology/api/report-templates')
        self.assertEqual(r2.status_code, 200)
        t2 = (r2.get_json() or {}).get('templates') or []
        self.assertTrue(any((t.get('id') == cid) for t in t2 if isinstance(t, dict)))

        d = self.client.post(f'/radiology/api/report-templates/{cid}/delete')
        self.assertEqual(d.status_code, 200)

        r3 = self.client.get('/radiology/api/report-templates')
        self.assertEqual(r3.status_code, 200)
        t3 = (r3.get_json() or {}).get('templates') or []
        self.assertFalse(any((t.get('id') == cid) for t in t3 if isinstance(t, dict)))

    def test_pharmacy_prescriptions(self):
        self._login(self.doctor.username, 'p')
        pr = self.client.post(f'/doctor/prescription/{self.visit.id}', data={'medication_name':'Paracetamol','dosage':'500mg','frequency':'TID','duration':'5 days','instructions':'After meals'}, follow_redirects=False)
        self.client.get('/auth/logout')
        self._login(self.ph.username, 'p')
        api = self.client.get('/medication/api/prescriptions?visit_id={}&status=active'.format(self.visit.id))
        self.assertEqual(api.status_code, 200)
        data = api.get_json()
        arr = data.get('prescriptions') or []
        if arr:
            pid = arr[0]['id']
            d = self.client.post(f'/medication/prescriptions/dispense/{pid}', follow_redirects=False)
            self.assertIn(d.status_code, (302, 200))

if __name__ == '__main__':
    unittest.main()
