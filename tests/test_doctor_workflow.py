import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.audit_trail import AuditTrail


class DoctorWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        self.suf = uuid.uuid4().hex[:8]
        # Create doctor user
        self.doctor_username = f'doctor_user_{self.suf}'
        d = User(username=self.doctor_username, email=f'doc_{self.suf}@example.com', full_name='Doctor User', role='doctor')
        d.set_password('p')
        db.session.add(d)
        db.session.commit()
        self.doctor_id = d.id
        # Create patient
        self.patient = Patient(first_name='Ali', last_name='Ahmad', first_name_ar='علي', last_name_ar='أحمد', national_id=f'NID_{self.suf}')
        db.session.add(self.patient)
        db.session.commit()

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

    def _create_visit(self, status='OPEN'):
        v = Visit(patient_id=self.patient.id, doctor_id=self.doctor_id, status=status)
        db.session.add(v)
        db.session.commit()
        return v

    def test_diagnosis_sets_in_progress_and_audit(self):
        self._login(self.doctor_username, 'p')
        v = self._create_visit(status='OPEN')
        r = self.client.post(f'/doctor/diagnosis/{v.id}', data={
            'chief_complaint': 'Headache',
            'symptoms': 'Pain',
            'diagnosis': 'Migraine',
            'differential_diagnosis': 'Tension',
            'treatment_plan': 'Rest',
            'follow_up_notes': 'Check in 1 week',
            'blood_pressure': '120/80',
            'heart_rate': '70',
            'temperature': '36.8',
            'respiratory_rate': '16',
        }, follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        v2 = db.session.get(Visit, v.id)
        self.assertEqual(v2.status, 'IN_PROGRESS')
        audit = AuditTrail.query.filter_by(entity_type='visit', entity_id=v.id, action='update').order_by(AuditTrail.created_at.desc()).first()
        self.assertIsNotNone(audit)
        self.assertIn('حفظ التشخيص', audit.description or '')

    def test_prescription_only_in_progress(self):
        self._login(self.doctor_username, 'p')
        v = self._create_visit(status='OPEN')
        # Attempt prescription while OPEN should not create prescription
        r1 = self.client.post(f'/doctor/prescription/{v.id}', data={
            'medication_name': 'Paracetamol',
            'dosage': '500mg',
            'frequency': 'TID',
            'duration': '5 days',
            'instructions': 'After meals'
        }, follow_redirects=False)
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(Prescription.query.filter_by(visit_id=v.id).count(), 0)

        # Move to IN_PROGRESS and retry
        v.status = 'IN_PROGRESS'
        db.session.commit()
        r2 = self.client.post(f'/doctor/prescription/{v.id}', data={
            'medication_name': 'Paracetamol',
            'dosage': '500mg',
            'frequency': 'TID',
            'duration': '5 days',
            'instructions': 'After meals'
        }, follow_redirects=False)
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(Prescription.query.filter_by(visit_id=v.id).count(), 1)
        v3 = db.session.get(Visit, v.id)
        self.assertTrue(v3.prescription_issued)
        audit = AuditTrail.query.filter_by(entity_type='visit', entity_id=v.id, action='update').order_by(AuditTrail.created_at.desc()).first()
        self.assertIsNotNone(audit)
        self.assertIn('إضافة وصفة طبية', audit.description or '')

    def test_lab_and_radiology_requests_only_in_progress(self):
        self._login(self.doctor_username, 'p')
        v = self._create_visit(status='OPEN')
        # Lab request while OPEN should not create
        r1 = self.client.post(f'/doctor/lab-request/{v.id}', data={
            'test_name': 'CBC',
            'test_description': 'Complete Blood Count',
            'urgency': 'normal',
            'notes': 'Routine'
        }, follow_redirects=False)
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(LabRequest.query.filter_by(visit_id=v.id).count(), 0)

        # Radiology request while OPEN should not create
        r2 = self.client.post(f'/doctor/radiology-request/{v.id}', data={
            'test_name': 'Chest X-Ray',
            'test_description': 'PA view',
            'urgency': 'normal',
            'notes': 'Cough'
        }, follow_redirects=False)
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(RadiologyRequest.query.filter_by(visit_id=v.id).count(), 0)

        # Move to IN_PROGRESS and retry
        v.status = 'IN_PROGRESS'
        db.session.commit()
        r3 = self.client.post(f'/doctor/lab-request/{v.id}', data={
            'test_name': 'CBC',
            'test_description': 'Complete Blood Count',
            'urgency': 'normal',
            'notes': 'Routine'
        }, follow_redirects=False)
        self.assertEqual(r3.status_code, 302)
        self.assertEqual(LabRequest.query.filter_by(visit_id=v.id).count(), 0)
        v2 = db.session.get(Visit, v.id)
        self.assertTrue(v2.lab_tests_ordered)
        self.assertIn('مذكرة تحاليل', v2.notes or '')
        lab_audit = AuditTrail.query.filter_by(entity_type='lab_test', action='create').order_by(AuditTrail.created_at.desc()).first()
        self.assertIsNotNone(lab_audit)

        r4 = self.client.post(f'/doctor/radiology-request/{v.id}', data={
            'test_name': 'Chest X-Ray',
            'test_description': 'PA view',
            'urgency': 'normal',
            'notes': 'Cough'
        }, follow_redirects=False)
        self.assertEqual(r4.status_code, 302)
        self.assertEqual(RadiologyRequest.query.filter_by(visit_id=v.id).count(), 0)
        v3 = db.session.get(Visit, v.id)
        self.assertTrue(v3.radiology_ordered)
        self.assertIn('مذكرة تصوير', v3.notes or '')
        rad_audit = AuditTrail.query.filter_by(entity_type='radiology_test', action='create').order_by(AuditTrail.created_at.desc()).first()
        self.assertIsNotNone(rad_audit)

    def test_notes_blocked_on_archived(self):
        self._login(self.doctor_username, 'p')
        v = self._create_visit(status='ARCHIVED')
        prev_notes = v.notes or ''
        r = self.client.post(f'/doctor/notes/{v.id}', data={'medical_notes': 'Note'}, follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        v2 = db.session.get(Visit, v.id)
        self.assertEqual(v2.notes or '', prev_notes)
        # Ensure no audit created for notes on archived
        audit_count = AuditTrail.query.filter_by(entity_type='visit', entity_id=v.id, description='إضافة ملاحظات طبية').count()
        self.assertEqual(audit_count, 0)

    def test_save_visit_summary_allowed_states(self):
        self._login(self.doctor_username, 'p')
        v = self._create_visit(status='OPEN')
        # Should fail when OPEN
        r1 = self.client.post(f'/doctor/save-visit-summary/{v.id}', json={'diagnosis': 'Flu'})
        self.assertEqual(r1.status_code, 400)
        # Move to IN_PROGRESS
        v.status = 'IN_PROGRESS'
        db.session.commit()
        r2 = self.client.post(f'/doctor/save-visit-summary/{v.id}', json={'diagnosis': 'Flu', 'treatment_plan': 'Rest'})
        self.assertEqual(r2.status_code, 200)
        data = r2.get_json()
        self.assertTrue(data.get('success'))
        audit = AuditTrail.query.filter_by(entity_type='visit', entity_id=v.id, action='update', description='حفظ ملخص الزيارة').order_by(AuditTrail.created_at.desc()).first()
        self.assertIsNotNone(audit)


if __name__ == '__main__':
    unittest.main()
