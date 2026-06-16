import unittest
from datetime import datetime, timedelta
from app_factory import create_app, db
from models.payment import Payment, PaymentMethod, PaymentStatus


class PaymentModelTestCase(unittest.TestCase):
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

    def test_display_maps(self):
        p = Payment(method=PaymentMethod.CARD, amount=10, status=PaymentStatus.CONFIRMED)
        self.assertIn('بطاقة', p.method_display)
        self.assertIn('مؤكد', p.status_display)

    def test_cancel_payment_within_window(self):
        p = Payment(method=PaymentMethod.CASH, amount=20, status=PaymentStatus.CONFIRMED)
        db.session.add(p)
        db.session.commit()
        ok, msg = p.cancel(user_id=None, reason='test')
        self.assertTrue(ok)
        self.assertTrue(p.is_cancelled)


if __name__ == '__main__':
    unittest.main()
