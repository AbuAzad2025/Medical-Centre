import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.medication import Medication, Prescription, PrescriptionItem, PrescriptionDispenseLog


class MedicationRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.pharma_username = f'pharma_user_test_{suf}'
        u = User(username=self.pharma_username, email=f'pharma_test_{suf}@example.com', full_name='Pharma User', role='pharmacist')
        u.set_password('p')
        db.session.add(u)
        db.session.commit()

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

    def test_medication_dashboard(self):
        r = self._login(self.pharma_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/medication/dashboard', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

    def test_dispense_prescription_creates_log_and_reduces_stock(self):
        r = self._login(self.pharma_username, 'p')
        self.assertEqual(r.status_code, 302)

        suf = uuid.uuid4().hex[:8]
        patient = Patient(first_name='سامي', last_name='حسن', phone='0590000011', national_id=f'NI{suf}')
        db.session.add(patient)
        doctor = User(username=f'dr_{suf}', email=f'dr_{suf}@example.com', full_name='Doctor', role='doctor')
        doctor.set_password('p')
        db.session.add(doctor)
        med = Medication(scientific_name='Amoxicillin', trade_name='Amox', dosage_form='tablet', strength='500mg', price=5, stock_quantity=10, minimum_stock=1)
        db.session.add(med)
        db.session.commit()

        pres = Prescription(patient_id=patient.id, doctor_id=doctor.id, prescription_number=f'RX-{suf}', status='active')
        db.session.add(pres)
        db.session.flush()
        item = PrescriptionItem(prescription_id=pres.id, medication_id=med.id, dosage='1', quantity=2, duration_days=5, instructions='after food', unit_price=5, total_price=10)
        db.session.add(item)
        db.session.commit()

        resp = self.client.post(f'/medication/prescriptions/dispense/{pres.id}')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload.get('success'))

        pres2 = db.session.get(Prescription, pres.id)
        self.assertEqual(pres2.status, 'dispensed')
        med2 = db.session.get(Medication, med.id)
        self.assertEqual(int(med2.stock_quantity), 8)

        logs = PrescriptionDispenseLog.query.filter_by(prescription_id=pres.id).all()
        self.assertEqual(len(logs), 1)

if __name__ == '__main__':
    unittest.main()
    unittest.main()
