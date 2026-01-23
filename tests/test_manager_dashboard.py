import unittest
import uuid
from app_factory import create_app, db
from models.user import User


class ManagerDashboardTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.manager_username = f'manager_dash_test_{suf}'
        u = User(username=self.manager_username, email=f'manager_dash_test_{suf}@example.com', full_name='Manager', role='manager')
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

    def test_manager_dashboard_loads(self):
        r = self._login(self.manager_username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/manager/dashboard', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('لوحة المدير', resp.data.decode('utf-8', errors='ignore'))


if __name__ == '__main__':
    unittest.main()

