import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.system_config import SystemConfig


class AuthRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.admin_username = f'admin_test_{suf}'
        self.admin_password = 'admin123'
        u = User(username=self.admin_username, email=f'admin_test_{suf}@example.com', full_name='Admin Test', role='super_admin', is_admin=True)
        u.set_password(self.admin_password)
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

    def test_login_success_redirect(self):
        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        r = self.client.post('/auth/login', data={'username': self.admin_username, 'password': self.admin_password, 'csrf_token': token}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get('/super-admin/dashboard', follow_redirects=True)
        self.assertEqual(r2.status_code, 200)

    def test_logout_requires_login(self):
        # Without login, redirect to login
        r = self.client.get('/auth/logout', follow_redirects=False)
        # flask-login protects route, will redirect to login
        self.assertEqual(r.status_code, 302)

    def test_login_lockout_after_failed_attempts(self):
        db.session.add(SystemConfig(config_key='max_login_attempts', config_value='3', config_type='integer', category='security'))
        db.session.add(SystemConfig(config_key='login_attempt_window_minutes', config_value='60', config_type='integer', category='security'))
        db.session.add(SystemConfig(config_key='login_lockout_minutes', config_value='60', config_type='integer', category='security'))
        db.session.commit()

        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''

        for _ in range(3):
            r = self.client.post('/auth/login', data={'username': self.admin_username, 'password': 'wrong', 'csrf_token': token}, follow_redirects=False)
            self.assertIn(r.status_code, (200, 401))

        r2 = self.client.post('/auth/login', data={'username': self.admin_username, 'password': 'wrong', 'csrf_token': token}, follow_redirects=False)
        self.assertEqual(r2.status_code, 429)
        self.assertIn('تجميد', r2.data.decode('utf-8', errors='ignore'))


if __name__ == '__main__':
    unittest.main()
