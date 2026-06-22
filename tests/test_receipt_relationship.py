"""Tests for P3-004: Receipt relationship repair and lifecycle."""

import pytest

from app_factory import db as _db
from models.patient import Patient
from models.payment import Payment
from models.receipt import Receipt
from models.user import User
from models.visit import Visit
from services.billing_state_service import ReceiptService


@pytest.fixture(scope='function')
def receipt_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Receipt',
        last_name='Patient',
        phone='0500000070',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def receipt_visit(app, test_tenant, receipt_patient):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=receipt_patient.id,
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


@pytest.fixture(scope='function')
def receipt_accountant(app, test_tenant):
    u = User.query.filter_by(username='receipt_accountant').first()
    if not u:
        u = User(
            username='receipt_accountant',
            email='receipt_acc@example.com',
            full_name='Accountant Receipt',
            role='accountant',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def receipt_payment(app, test_tenant, receipt_visit, receipt_patient, receipt_accountant):
    p = Payment(
        tenant_id=test_tenant.id,
        visit_id=receipt_visit.id,
        patient_id=receipt_patient.id,
        amount=75,
        method='CASH',
        status='CONFIRMED',
        received_by=receipt_accountant.id,
    )
    _db.session.add(p)
    _db.session.commit()
    return p


class TestReceiptService:
    def test_issue_receipt_links_payment(self, receipt_visit, receipt_payment, test_tenant):
        result = ReceiptService.issue_receipt(receipt_visit, receipt_payment)
        assert result['status'] == 'issued'

        receipt = _db.session.get(Receipt, result['receipt_id'])
        assert receipt is not None
        assert receipt.payment_id == receipt_payment.id
        assert receipt.visit_id == receipt_visit.id
        assert receipt.patient_id == receipt_visit.patient_id
        assert receipt.status == 'issued'
        assert float(receipt.total_amount) == 75
        assert float(receipt.paid_amount) == 75
        assert float(receipt.remaining_amount) == 0
        assert receipt.payment_method == 'cash'
        assert receipt.receipt_number.startswith('RCP-')

    def test_issue_receipt_maps_card_method(self, receipt_visit, receipt_payment, test_tenant):
        receipt_payment.method = 'CARD'
        result = ReceiptService.issue_receipt(receipt_visit, receipt_payment)
        receipt = _db.session.get(Receipt, result['receipt_id'])
        assert receipt.payment_method == 'card'

    def test_mark_printed(self, receipt_visit, receipt_payment):
        result = ReceiptService.issue_receipt(receipt_visit, receipt_payment)
        receipt = _db.session.get(Receipt, result['receipt_id'])
        ReceiptService.mark_printed(receipt.id)
        _db.session.refresh(receipt)
        assert receipt.status == 'printed'
        assert receipt.is_printed is True
        assert receipt.printed_at is not None

    def test_void_receipt(self, receipt_visit, receipt_payment):
        result = ReceiptService.issue_receipt(receipt_visit, receipt_payment)
        receipt = _db.session.get(Receipt, result['receipt_id'])
        ReceiptService.void_receipt(receipt.id, reason='Cancelled')
        _db.session.refresh(receipt)
        assert receipt.status == 'voided'
        assert receipt.void_reason == 'Cancelled'

    def test_to_dict_includes_new_fields(self, receipt_visit, receipt_payment):
        result = ReceiptService.issue_receipt(receipt_visit, receipt_payment)
        receipt = _db.session.get(Receipt, result['receipt_id'])
        data = receipt.to_dict()
        assert data['payment_id'] == receipt_payment.id
        assert data['status'] == 'issued'
        assert 'void_reason' in data
