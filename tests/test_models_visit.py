import unittest
import uuid
from datetime import datetime
from app_factory import create_app, db
from models.visit import Visit
from models.user import User
from models.patient import Patient


class VisitModelTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        suf = uuid.uuid4().hex[:8]
        self.patient = Patient(first_name='Ali', last_name='Ahmad', first_name_ar='علي', last_name_ar='أحمد', national_id=f'X1_{suf}')
        db.session.add(self.patient)
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

    def test_amounts_and_payment(self):
        v = Visit(patient_id=self.patient.id, total_amount=100, paid_amount=30)
        db.session.add(v)
        db.session.commit()
        self.assertEqual(v.remaining_amount, 70.0)
        self.assertFalse(v.is_fully_paid)

        v.paid_amount = 100
        db.session.commit()
        self.assertTrue(v.is_fully_paid)

    def test_insurance_calculation(self):
        v = Visit(patient_id=self.patient.id, total_amount=200, payment_method='insurance', insurance_coverage_percentage=50)
        v.calculate_insurance_amounts()
        self.assertEqual(float(v.insurance_amount), 100.0)
        self.assertEqual(float(v.patient_share), 100.0)


if __name__ == '__main__':
    unittest.main()
