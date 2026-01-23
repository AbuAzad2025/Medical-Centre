import unittest
import uuid
from app_factory import create_app, db
from models.user import User


class DashboardsByRoleTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:6]
        self.users = {
            'manager': self._create_user(f'manager_{suf}', 'manager'),
            'reception': self._create_user(f'reception_{suf}', 'reception'),
            'doctor': self._create_user(f'doctor_{suf}', 'doctor'),
            'lab': self._create_user(f'lab_{suf}', 'lab'),
            'radiology': self._create_user(f'radiology_{suf}', 'radiology'),
            'nurse': self._create_user(f'nurse_{suf}', 'nurse'),
            'accountant': self._create_user(f'accountant_{suf}', 'accountant'),
        }

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _create_user(self, username, role, password='p'):
        u = User(username=username, email=f'{username}@example.com', full_name=username, role=role, is_admin=False, is_active=True)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return username

    def _login(self, username, password='p'):
        return self.client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)

    def test_manager_dashboard(self):
        r = self._login(self.users['manager'])
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/manager/dashboard', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_reception_dashboard(self):
        r = self._login(self.users['reception'])
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/reception/dashboard', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_doctor_dashboard(self):
        r = self._login(self.users['doctor'])
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/doctor/dashboard', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_lab_dashboard(self):
        r = self._login(self.users['lab'])
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/lab/dashboard', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_radiology_dashboard(self):
        r = self._login(self.users['radiology'])
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/radiology/dashboard', follow_redirects=False)
        self.assertIn(resp.status_code, (200, 302))

    def test_nurse_dashboard(self):
        r = self._login(self.users['nurse'])
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/nurse/dashboard', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_accountant_dashboard(self):
        r = self._login(self.users['accountant'])
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/accountant/dashboard', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
