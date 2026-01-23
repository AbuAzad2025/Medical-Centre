import unittest
from app_factory import create_app, db
from models.pricing_management import PricingManagement


class PricingManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_final_price_with_discount_and_tax(self):
        pm = PricingManagement(service_id=1, base_price=100, discount_percentage=10, tax_percentage=5)
        db.session.add(pm)
        db.session.commit()
        self.assertEqual(pm.get_final_price('base'), 94.5)

    def test_final_price_variants(self):
        pm = PricingManagement(service_id=1, base_price=80, emergency_price=120, insurance_price=50, private_price=150)
        db.session.add(pm)
        db.session.commit()
        self.assertEqual(pm.get_final_price('base'), 80)
        self.assertEqual(pm.get_final_price('emergency'), 120)
        self.assertEqual(pm.get_final_price('insurance'), 50)
        self.assertEqual(pm.get_final_price('private'), 150)


if __name__ == '__main__':
    unittest.main()
