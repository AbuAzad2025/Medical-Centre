import re
import unittest
from datetime import datetime, date, timedelta
from app_factory import create_app, db
from models.department import Department
from models.user import User
from models.user import StaffWorkSchedule
from models.patient_account import PatientAccount
from models.online_booking import OnlineBooking
from models.online_booking import PaymentTransaction


class BookingRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # صفحة الحجز قد تتأثر بقوالب عامة، نركز على واجهات API المضمونة

    def test_api_available_doctors(self):
        r = self.client.get('/booking/api/available-doctors')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn('success', data)

    def test_api_available_times_missing_params(self):
        r = self.client.get('/booking/api/available-times')
        self.assertEqual(r.status_code, 400)
        data = r.get_json()
        self.assertFalse(data['success'])

    def test_patient_register_and_dashboard(self):
        page = self.client.get('/booking/register')
        html = page.data.decode('utf-8', errors='ignore')
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        r = self.client.post('/booking/register', data={
            'full_name': 'Patient One',
            'phone': '0590000000',
            'password': 'p',
            'csrf_token': token
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        body = r.data.decode('utf-8', errors='ignore')
        self.assertIn('حجوزاتي', body)

        user = User.query.filter_by(role='patient', phone='0590000000').first()
        self.assertIsNotNone(user)
        link = PatientAccount.query.filter_by(user_id=user.id).first()
        self.assertIsNotNone(link)

    def test_patient_booking_links_patient_id(self):
        dept = Department(name='General', name_ar='العيادة', is_active=True)
        db.session.add(dept)
        doc = User(username='doc1', email='doc1@example.com', full_name='Doc', role='doctor', is_active=True)
        doc.set_password('p')
        db.session.add(doc)
        db.session.flush()
        StaffWorkSchedule.query.filter_by(user_id=doc.id).delete()
        ap_date = date.today() + timedelta(days=7)
        db.session.add(StaffWorkSchedule(
            user_id=doc.id,
            day_of_week=ap_date.weekday(),
            start_time=datetime.strptime('09:00', '%H:%M').time(),
            end_time=datetime.strptime('17:00', '%H:%M').time(),
            is_active=True
        ))
        db.session.commit()

        page = self.client.get('/booking/register')
        html = page.data.decode('utf-8', errors='ignore')
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        self.client.post('/booking/register', data={
            'full_name': 'Patient Two',
            'phone': '0590000001',
            'password': 'p',
            'csrf_token': token
        }, follow_redirects=True)

        page2 = self.client.get('/booking/create')
        html2 = page2.data.decode('utf-8', errors='ignore')
        m2 = re.search(r'name="csrf_token" value="([^"]+)"', html2)
        token2 = m2.group(1) if m2 else ''
        r = self.client.post('/booking/create', data={
            'csrf_token': token2,
            'first_name': 'Patient',
            'last_name': 'Two',
            'phone': '0590000001',
            'email': 'p2@example.com',
            'department_id': str(dept.id),
            'doctor_id': str(doc.id),
            'appointment_date': ap_date.strftime('%Y-%m-%d'),
            'appointment_time': '10:00'
        }, follow_redirects=False)
        booking = OnlineBooking.query.order_by(OnlineBooking.id.desc()).first()
        self.assertIsNotNone(booking)
        self.assertIsNotNone(booking.patient_id)

        confirm = self.client.get(f'/booking/confirmation/{booking.id}')
        self.assertEqual(confirm.status_code, 200)

        pay = self.client.post(f'/booking/payment/{booking.id}', data={
            'amount': '50',
            'payment_method': 'CASH'
        }, follow_redirects=False)
        self.assertIn(pay.status_code, [302, 303])
        txn = PaymentTransaction.query.filter_by(booking_id=booking.id).first()
        self.assertIsNotNone(txn)


if __name__ == '__main__':
    unittest.main()
