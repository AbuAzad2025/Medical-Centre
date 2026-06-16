import unittest
import uuid
from app_factory import create_app, db
from models.user import User


class UserModelTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

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

    def test_password_hashing(self):
        suf = uuid.uuid4().hex[:8]
        u = User(username=f'user_one_{suf}', email=f'u1_{suf}@example.com', full_name='Tester', role='super_admin')
        u.set_password('secret')
        db.session.add(u)
        db.session.commit()
        self.assertTrue(u.check_password('secret'))
        self.assertFalse(u.check_password('wrong'))

    def test_to_dict(self):
        suf = uuid.uuid4().hex[:8]
        u = User(username=f'user_2_{suf}', email=f'u2_{suf}@example.com', full_name='User Two', role='manager')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()
        d = u.to_dict()
        self.assertTrue(d['username'].startswith('user_2_'))
        self.assertEqual(d['role'], 'manager')


if __name__ == '__main__':
    unittest.main()
