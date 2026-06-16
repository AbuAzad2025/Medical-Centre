import unittest
from app_factory import create_app, db
from models.user import User


class FinanceJsonEndpointsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        self.username = 'accountant_json'
        u = User(username=self.username, email='accountant_json@example.com', full_name='Accountant JSON', role='accountant', is_active=True)
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

    def _login(self):
        r = self.client.post('/auth/login', data={'username': self.username, 'password': 'p'}, follow_redirects=False)
        self.assertEqual(r.status_code, 302)

    def test_post_gl_requires_visit_id(self):
        self._login()
        r = self.client.post('/finance/post', json={}, follow_redirects=False)
        self.assertEqual(r.status_code, 400)
        data = r.get_json()
        self.assertTrue('error' in data)

    def test_archive_visit_endpoint_reachable(self):
        self._login()
        r = self.client.post('/finance/visits/1/archive', json={}, follow_redirects=False)
        self.assertIn(r.status_code, (200, 422, 500))


if __name__ == '__main__':
    unittest.main()
