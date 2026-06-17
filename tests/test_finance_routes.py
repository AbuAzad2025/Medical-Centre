import unittest
import uuid
from app_factory import create_app, db
from models.user import User


class FinanceRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.manager_username = f'manager_fin_test_{suf}'
        u = User(username=self.manager_username, email=f'mf_test_{suf}@example.com', full_name='Manager Finance', role='manager')
        u.set_password('p')
        db.session.add(u)
        db.session.commit()

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

    def test_finance_dashboard(self):
        r = self._login(self.manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/finance/dashboard', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

    def test_finance_payments(self):
        r = self._login(self.manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/finance/payments', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

    def test_finance_invoices(self):
        r = self._login(self.manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/finance/invoices', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

    def test_finance_audit(self):
        r = self._login(self.manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/finance/audit', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

    def test_payment_dashboard(self):
        r = self._login(self.manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        r1 = self.client.get('/payment/dashboard', follow_redirects=True)
        self.assertEqual(r1.status_code, 200)


if __name__ == '__main__':
    unittest.main()
