import unittest
from app_factory import create_app, db


class AppFactoryTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()

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

    def test_health_endpoint(self):
        r = self.client.get('/__health')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'ok', r.data)

    def test_ping_endpoint(self):
        r = self.client.get('/__ping')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, b'pong')

    def test_routes_listing(self):
        r = self.client.get('/__routes')
        self.assertEqual(r.status_code, 200)
        self.assertIn('قائمة المسارات', r.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
