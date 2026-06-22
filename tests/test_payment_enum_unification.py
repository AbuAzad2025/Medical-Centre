"""Tests for P3-005: Payment enum compatibility/unification."""

from app.shared.enums import PaymentMethod as SharedPaymentMethod
from app.shared.enums import PaymentStatus as SharedPaymentStatus
from models.payment import PaymentMethod as ModelPaymentMethod
from models.payment import PaymentStatus as ModelPaymentStatus


class TestPaymentEnumUnification:
    def test_payment_status_same_values(self):
        shared_values = {m.value for m in SharedPaymentStatus}
        model_values = {getattr(ModelPaymentStatus, attr) for attr in dir(ModelPaymentStatus)
                        if not attr.startswith('_') and not callable(getattr(ModelPaymentStatus, attr))}
        assert shared_values == model_values

    def test_payment_method_same_values(self):
        shared_values = {m.value for m in SharedPaymentMethod}
        model_values = {getattr(ModelPaymentMethod, attr) for attr in dir(ModelPaymentMethod)
                        if not attr.startswith('_') and not callable(getattr(ModelPaymentMethod, attr))}
        assert shared_values == model_values

    def test_status_values_include_confirmed_and_paid(self):
        assert ModelPaymentStatus.CONFIRMED == 'CONFIRMED'
        assert ModelPaymentStatus.PAID == 'PAID'
        assert SharedPaymentStatus.CONFIRMED == 'CONFIRMED'
        assert SharedPaymentStatus.PAID == 'PAID'

    def test_method_values_include_card_and_insurance(self):
        assert ModelPaymentMethod.CARD == 'CARD'
        assert ModelPaymentMethod.INSURANCE == 'INSURANCE'
        assert SharedPaymentMethod.CARD == 'CARD'
        assert SharedPaymentMethod.INSURANCE == 'INSURANCE'
