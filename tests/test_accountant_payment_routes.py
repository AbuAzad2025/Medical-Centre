import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.department import Department
from models.patient import Patient
from models.visit import Visit

class AccountantPaymentRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.dept = Department(name='Internal Medicine', name_ar='الباطنية', is_active=True)
        db.session.add(self.dept)
        self.accountant = User(username=f'accountant_{suf}', email=f'a_{suf}@example.com', full_name='Accountant', role='accountant', is_active=True)
        self.accountant.set_password('p')
        db.session.add(self.accountant)
        self.patient = Patient(national_id=f'NI{suf}', first_name='ليلى', last_name='سليم', phone='0590000002', gender='female')
        db.session.add(self.patient)
        db.session.commit()
        self.visit = Visit(patient_id=self.patient.id, department_id=self.dept.id, status='COMPLETED', payment_status='PAID', total_amount=100, paid_amount=100, visit_type='REGULAR', payment_method='cash')
        db.session.add(self.visit)
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

    def _login(self, u, p):
        return self.client.post('/auth/login', data={'username': u, 'password': p}, follow_redirects=False)

    def test_accountant_payment_process_page(self):
        self._login(self.accountant.username, 'p')
        r = self.client.get(f'/payment/process/{self.visit.id}')
        self.assertEqual(r.status_code, 200)

if __name__ == '__main__':
    unittest.main()
