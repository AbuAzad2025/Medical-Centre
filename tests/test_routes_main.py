import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.department import Department


class MainRedirectsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///test_main.sqlite', TESTING=True)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        self.suf = uuid.uuid4().hex[:6]

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

    def _create_user(self, username, role, password='p'):
        uname = f"{username}_{self.suf}"
        u = User(username=uname, email=f'{uname}@example.com', full_name=uname.replace('_',' ').title(), role=role, is_admin=(role in ['super_admin','admin']))
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    def test_redirects_by_role(self):
        roles_paths = [
            ('super_admin', '/super-admin/dashboard'),
            ('manager', '/manager/dashboard'),
            ('doctor', '/doctor/dashboard'),
            ('reception', '/reception/dashboard'),
            ('lab', '/lab/dashboard'),
            ('radiology', '/radiology/dashboard'),
            ('nurse', '/nurse/dashboard'),
            ('accountant', '/accountant/dashboard'),
        ]

        for role, expected_path in roles_paths:
            username = f'user_{role}'
            self._create_user(username, role, password='p')
            r = self._login(f"{username}_{self.suf}", 'p')
            self.assertEqual(r.status_code, 302)
            resp = self.client.get('/dashboard', follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(resp.headers['Location'].endswith(expected_path))

    def test_emergency_reports_daily(self):
        from models.emergency import EmergencyCase
        from datetime import datetime, timezone

        emergency_user = self._create_user('user_emergency2', 'emergency', password='p')
        dept = Department(name='Emergency', name_ar='طوارئ', is_active=True)
        db.session.add(dept)
        patient = Patient(national_id=f'NI{self.suf}', first_name='سامي', last_name='خليل', phone='0590000011')
        db.session.add(patient)
        db.session.commit()

        visit = Visit(patient_id=patient.id, department_id=dept.id, status='OPEN', visit_type='EMERGENCY', payment_status='PENDING', total_amount=0, paid_amount=0, payment_method='cash')
        db.session.add(visit)
        db.session.flush()

        ec = EmergencyCase(
            patient_id=patient.id,
            visit_id=visit.id,
            case_number=f'EC-{visit.id}-{int(datetime.now(timezone.utc).timestamp())}',
            chief_complaint='ألم صدر',
            severity='HIGH',
            status='IN_PROGRESS'
        )
        db.session.add(ec)
        db.session.commit()

        self._login(emergency_user.username, 'p')
        r = self.client.get('/emergency/reports')
        self.assertEqual(r.status_code, 200)
        html = r.data.decode('utf-8', errors='ignore')
        self.assertIn('الأسباب الشائعة', html)

    def test_accountant_patient_statement(self):
        from models.invoice import Invoice
        from models.payment import Payment, PaymentStatus, PaymentMethod
        from datetime import datetime, timezone

        acc = self._create_user('user_accountant2', 'accountant', password='p')
        dept = Department(name='General', name_ar='عام', is_active=True)
        db.session.add(dept)
        patient = Patient(national_id=f'NI2{self.suf}', first_name='ليلى', last_name='حسن', phone='0590000022')
        db.session.add(patient)
        db.session.commit()

        visit = Visit(patient_id=patient.id, department_id=dept.id, status='OPEN', payment_status='DEBT', total_amount=100, paid_amount=30, payment_method='cash')
        db.session.add(visit)
        db.session.flush()

        inv = Invoice(invoice_number=f'INV-{visit.id}-{int(datetime.now(timezone.utc).timestamp())}', visit_id=visit.id, created_by=acc.id, status='ISSUED', total_amount=100, paid_amount=30, currency='ILS')
        db.session.add(inv)
        db.session.flush()

        pmt = Payment(patient_id=patient.id, visit_id=visit.id, invoice_id=inv.id, method=PaymentMethod.CASH, amount=30, status=PaymentStatus.CONFIRMED, received_by=acc.id)
        db.session.add(pmt)
        db.session.commit()

        self._login(acc.username, 'p')
        resp = self.client.get(f'/accountant/financial?patient_id={patient.id}')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8', errors='ignore')
        self.assertIn('كشف حساب', html)
        self.assertIn(patient.first_name, html)


if __name__ == '__main__':
    unittest.main()
