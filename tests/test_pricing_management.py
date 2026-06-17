import unittest
from app_factory import create_app, db
from models.pricing_management import PricingManagement
from models.service import ServiceMaster


class PricingManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

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

    def test_final_price_with_discount_and_tax(self):
        svc = ServiceMaster(name='Test Service', code='TEST001', base_price=100, category='general')
        db.session.add(svc)
        db.session.flush()
        pm = PricingManagement(service_id=svc.id, base_price=100, discount_percentage=10, tax_percentage=5)
        db.session.add(pm)
        db.session.commit()
        self.assertEqual(pm.get_final_price('base'), 94.5)

    def test_final_price_variants(self):
        svc = ServiceMaster(name='Test Service', code='TEST002', base_price=80, category='general')
        db.session.add(svc)
        db.session.flush()
        pm = PricingManagement(service_id=svc.id, base_price=80, emergency_price=120, insurance_price=50, private_price=150)
        db.session.add(pm)
        db.session.commit()
        self.assertEqual(pm.get_final_price('base'), 80)
        self.assertEqual(pm.get_final_price('emergency'), 120)
        self.assertEqual(pm.get_final_price('insurance'), 50)
        self.assertEqual(pm.get_final_price('private'), 150)


if __name__ == '__main__':
    unittest.main()
