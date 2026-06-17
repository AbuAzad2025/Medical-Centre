import unittest
import uuid
from app_factory import create_app, db
from models.user import User


class SuperAdminPermsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.user_username = f'user_manager_test_{suf}'
        self.user_password = 'p'
        self.user = User(username=self.user_username, email=f'u_test_{suf}@example.com', full_name='User', role='manager', is_admin=False)
        self.user.set_password(self.user_password)
        db.session.add(self.user)
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

    def test_dashboard_requires_admin(self):
        # login via form for non-admin
        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        r = self.client.post('/auth/login', data={'username': self.user_username, 'password': self.user_password, 'csrf_token': token}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get('/super-admin/dashboard', follow_redirects=True)
        self.assertEqual(r2.status_code, 200)
        self.assertNotIn('لوحة السوبر أدمن', r2.data.decode('utf-8'))

    def test_admin_can_access_dashboard(self):
        suf = uuid.uuid4().hex[:8]
        admin = User(username=f'admin2_test_{suf}', email=f'a2_test_{suf}@example.com', full_name='Admin Two', role='admin', is_admin=True)
        admin.set_password('p2')
        db.session.add(admin)
        db.session.commit()
        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        r = self.client.post('/auth/login', data={'username': admin.username, 'password': 'p2', 'csrf_token': token}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get('/super-admin/dashboard', follow_redirects=True)
        self.assertEqual(r2.status_code, 200)
        self.assertIn('لوحة السوبر أدمن', r2.data.decode('utf-8'))

        r3 = self.client.get('/super-admin/system-monitor', follow_redirects=True)
        self.assertEqual(r3.status_code, 200)

        r4 = self.client.get('/super-admin/queue-settings', follow_redirects=True)
        self.assertEqual(r4.status_code, 200)

        r5 = self.client.get('/super-admin/system-backup', follow_redirects=True)
        self.assertEqual(r5.status_code, 200)


if __name__ == '__main__':
    unittest.main()
