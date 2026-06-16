import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.department import Department
from models.visit import Visit
from models.appointment import Appointment
from models.invoice import Invoice, InvoiceService as InvoiceLine
from models.online_booking import OnlineBooking


class ReceptionRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.reception_username = f'reception_user_test_{suf}'
        u = User(username=self.reception_username, email=f'reception_test_{suf}@example.com', full_name='Reception User', role='reception')
        u.set_password('p')
        db.session.add(u)
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

    def test_reception_dashboard_and_patients(self):
        r = self._login(self.reception_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/reception/dashboard', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.get('/reception/patients', follow_redirects=True)
        self.assertEqual(r2.status_code, 200)

    def test_view_patient_has_valid_html_and_business_data(self):
        r = self._login(self.reception_username, 'p')
        self.assertEqual(r.status_code, 302)
        dept = Department(name='General', name_ar='عام')
        db.session.add(dept)
        doctor = User(username=f'dr_{uuid.uuid4().hex[:6]}', email='dr@example.com', full_name='د. أحمد', role='doctor', department_id=None)
        doctor.set_password('p')
        db.session.add(doctor)
        pat = Patient(first_name='علي', last_name='خالد', phone='0590000000', national_id='123456789')
        db.session.add(pat)
        db.session.commit()
        v = Visit(patient_id=pat.id, department_id=dept.id, doctor_id=doctor.id, status='OPEN', notes='زيارة اختبار', payment_method='CASH')
        db.session.add(v)
        ap = Appointment(patient_id=pat.id, doctor_id=doctor.id, department_id=dept.id, starts_at=db.func.now(), status='SCHEDULED')
        db.session.add(ap)
        db.session.commit()
        resp = self.client.get(f'/reception/view_patient/{pat.id}', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        ct = resp.headers.get('Content-Type', '')
        self.assertIn('text/html', ct)
        html = resp.data.decode('utf-8', errors='ignore')
        self.assertIn('تفاصيل المريض', html)
        self.assertIn('علي', html)
        self.assertIn('0590000000', html)
        self.assertIn('عام', html)
        self.assertIn('د. أحمد', html)
        self.assertNotIn('لا توجد زيارات', html)
        self.assertNotIn('لا توجد مواعيد', html)

    def test_send_visit_to_accounting_creates_invoice(self):
        r = self._login(self.reception_username, 'p')
        self.assertEqual(r.status_code, 302)

        dept = Department(name='General2', name_ar='عام2')
        db.session.add(dept)
        doctor = User(username=f'dr2_{uuid.uuid4().hex[:6]}', email='dr2@example.com', full_name='د. سارة', role='doctor', department_id=None)
        doctor.set_password('p')
        db.session.add(doctor)
        pat = Patient(first_name='محمود', last_name='صالح', phone='0590000009', national_id='987654321')
        db.session.add(pat)
        db.session.commit()

        v = Visit(patient_id=pat.id, department_id=dept.id, doctor_id=doctor.id, status='OPEN', payment_status='PENDING', total_amount=100, paid_amount=0, payment_method='cash')
        db.session.add(v)
        db.session.commit()

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post(f'/reception/process_payment/{v.id}', data={'csrf_token': token}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        inv = Invoice.query.filter_by(visit_id=v.id).first()
        self.assertIsNotNone(inv)
        lines = InvoiceLine.query.filter_by(invoice_id=inv.id).all()
        self.assertTrue(len(lines) >= 1)
        v2 = db.session.get(Visit, v.id)
        self.assertEqual(v2.payment_status, 'PENDING')

    def test_checkin_online_booking_creates_visit_and_patient(self):
        r = self._login(self.reception_username, 'p')
        self.assertEqual(r.status_code, 302)

        dept = Department(name='General3', name_ar='عام3')
        db.session.add(dept)
        doctor = User(username=f'dr3_{uuid.uuid4().hex[:6]}', email='dr3@example.com', full_name='د. رائد', role='doctor', department_id=None)
        doctor.set_password('p')
        db.session.add(doctor)
        db.session.commit()

        from datetime import date as _date, time as _time
        booking = OnlineBooking(
            booking_reference='TESTBKG1',
            confirmation_code='123456',
            first_name='سلمى',
            last_name='محمد',
            phone='0590000011',
            department_id=dept.id,
            doctor_id=doctor.id,
            appointment_date=_date.today(),
            appointment_time=_time(10, 0),
            status='pending'
        )
        db.session.add(booking)
        db.session.commit()

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post(
            '/reception/online-bookings/checkin',
            data={'booking_id': booking.id, 'csrf_token': token},
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

        booking2 = db.session.get(OnlineBooking, booking.id)
        self.assertEqual(booking2.status, 'completed')
        self.assertIsNotNone(booking2.patient_id)

        marker = f"[ONLINE_BOOKING:{booking2.booking_reference}]"
        visit = Visit.query.filter(Visit.notes.contains(marker)).first()
        self.assertIsNotNone(visit)
        self.assertEqual(visit.patient_id, booking2.patient_id)
        self.assertEqual(visit.department_id, dept.id)
        self.assertEqual(visit.doctor_id, doctor.id)

    def test_checkin_appointment_creates_visit(self):
        r = self._login(self.reception_username, 'p')
        self.assertEqual(r.status_code, 302)

        dept = Department(name='General4', name_ar='عام4')
        db.session.add(dept)
        doctor = User(username=f'dr4_{uuid.uuid4().hex[:6]}', email='dr4@example.com', full_name='د. هبة', role='doctor', department_id=None)
        doctor.set_password('p')
        db.session.add(doctor)
        pat = Patient(first_name='نور', last_name='ياسين', phone='0590000022', national_id='223344556')
        db.session.add(pat)
        db.session.commit()

        ap = Appointment(patient_id=pat.id, doctor_id=doctor.id, department_id=dept.id, starts_at=db.func.now(), status='SCHEDULED', notes='موعد اختبار')
        db.session.add(ap)
        db.session.commit()

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post(
            f'/reception/appointments/{ap.id}/checkin',
            data={'csrf_token': token},
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

        ap2 = db.session.get(Appointment, ap.id)
        self.assertEqual(ap2.status, 'CONFIRMED')

        marker = f"[APPOINTMENT:{ap.id}]"
        visit = Visit.query.filter(Visit.notes.contains(marker)).first()
        self.assertIsNotNone(visit)
        self.assertEqual(visit.patient_id, pat.id)
        self.assertEqual(visit.department_id, dept.id)
        self.assertEqual(visit.doctor_id, doctor.id)

    def test_confirm_cancel_no_show_appointment(self):
        r = self._login(self.reception_username, 'p')
        self.assertEqual(r.status_code, 302)

        dept = Department(name='General5', name_ar='عام5')
        db.session.add(dept)
        doctor = User(username=f'dr5_{uuid.uuid4().hex[:6]}', email='dr5@example.com', full_name='د. يزن', role='doctor', department_id=None)
        doctor.set_password('p')
        db.session.add(doctor)
        pat = Patient(first_name='ليلى', last_name='حسن', phone='0590000033', national_id='334455667')
        db.session.add(pat)
        db.session.commit()

        ap = Appointment(patient_id=pat.id, doctor_id=doctor.id, department_id=dept.id, starts_at=db.func.now(), status='SCHEDULED')
        db.session.add(ap)
        db.session.commit()

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post(f'/reception/appointments/{ap.id}/confirm', data={'csrf_token': token}, follow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        ap2 = db.session.get(Appointment, ap.id)
        self.assertEqual(ap2.status, 'CONFIRMED')

        resp2 = self.client.post(f'/reception/appointments/{ap.id}/no-show', data={'csrf_token': token}, follow_redirects=False)
        self.assertEqual(resp2.status_code, 200)
        ap3 = db.session.get(Appointment, ap.id)
        self.assertEqual(ap3.status, 'NO_SHOW')

        resp3 = self.client.post(f'/reception/appointments/{ap.id}/cancel', data={'csrf_token': token}, follow_redirects=False)
        self.assertIn(resp3.status_code, (200, 400))

    def test_add_patient_invalid_phone(self):
        r = self._login(self.reception_username, 'p')
        self.assertEqual(r.status_code, 302)

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        resp = self.client.post('/reception/add_patient', data={
            'csrf_token': token,
            'first_name': 'سعيد',
            'last_name': 'عمر',
            'phone': 'abc'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('رقم الهاتف غير صالح', resp.data.decode('utf-8', errors='ignore'))


if __name__ == '__main__':
    unittest.main()
