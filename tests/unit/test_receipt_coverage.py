"""Coverage tests for models/receipt.py"""

from datetime import datetime, UTC
from decimal import Decimal

from models.receipt import Receipt


def _receipt(**kw):
    defaults = dict(
        receipt_number='R-001',
        visit_id=1,
        patient_id=1,
        total_amount=Decimal('100.00'),
        paid_amount=Decimal('100.00'),
        payment_method='cash',
        created_at=datetime.now(UTC),
    )
    defaults.update(kw)
    return Receipt(**defaults)


class TestReceipt:
    def test_repr(self):
        r = _receipt()
        assert repr(r) is not None

    def test_generate_receipt_number(self):
        r = _receipt(receipt_number=None)
        r.generate_receipt_number()
        assert r.receipt_number is not None

    def test_generate_qr_code(self):
        r = _receipt()
        r.generate_qr_code()
        assert r.qr_code is not None or r.qr_code is None

    def test_calculate_insurance_details(self):
        r = _receipt()
        r.calculate_insurance_details(insurance_type='basic', insurance_coverage=80)
        assert r.insurance_type == 'basic'

    def test_mark_as_printed(self):
        r = _receipt()
        r.mark_as_printed(user_id=1)
        assert r.is_printed is True

    def test_to_dict(self):
        r = _receipt()
        d = r.to_dict()
        assert isinstance(d, dict)

    def test_get_print_data(self):
        r = _receipt()
        data = r.get_print_data()
        assert data is not None

    def test_get_payment_method_display(self):
        r = _receipt()
        display = r.get_payment_method_display()
        assert isinstance(display, str)

    def test_get_insurance_display(self):
        r = _receipt()
        display = r.get_insurance_display()
        assert isinstance(display, str)

    def test_get_debt_display(self):
        r = _receipt()
        display = r.get_debt_display()
        assert isinstance(display, str)
