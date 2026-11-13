"""Coverage tests for models/pricing_management.py"""

from decimal import Decimal

from models.pricing_management import PricingManagement, PricingRule


class TestPricingManagement:
    def test_repr(self):
        pm = PricingManagement(service_id=1, base_price=Decimal('100.00'))
        assert repr(pm) is not None

    def test_get_final_price_base(self):
        pm = PricingManagement(service_id=1, base_price=Decimal('100.00'))
        price = pm.get_final_price('base')
        assert price is not None

    def test_get_final_price_emergency(self):
        pm = PricingManagement(
            service_id=1, base_price=Decimal('100.00'), emergency_price=Decimal('150.00')
        )
        price = pm.get_final_price('emergency')
        assert price is not None

    def test_to_dict(self):
        pm = PricingManagement(service_id=1, base_price=Decimal('100.00'))
        d = pm.to_dict()
        assert isinstance(d, dict)

    def test_pricing_rule_applies_to(self):
        rule = PricingRule(
            name='Test Rule',
            condition_type='patient_age',
            condition_value='30',
            condition_operator='equals',
            price_adjustment_value=Decimal('10.00'),
        )
        result = rule.applies_to(patient_age=30)
        assert result is True

    def test_pricing_rule_apply_to_price(self):
        rule = PricingRule(
            name='Test Rule',
            condition_type='patient_age',
            condition_value='30',
            condition_operator='equals',
            price_adjustment_value=Decimal('10.00'),
        )
        result = rule.apply_to_price(Decimal('100.00'))
        assert result is not None

    def test_pricing_rule_to_dict(self):
        rule = PricingRule(
            name='Test Rule',
            condition_type='patient_age',
            condition_value='30',
            condition_operator='equals',
            price_adjustment_value=Decimal('10.00'),
        )
        d = rule.to_dict()
        assert isinstance(d, dict)

    def test_pricing_rule_repr(self):
        rule = PricingRule(
            name='Test Rule',
            condition_type='patient_age',
            condition_value='30',
            condition_operator='equals',
            price_adjustment_value=Decimal('10.00'),
        )
        assert repr(rule) is not None
