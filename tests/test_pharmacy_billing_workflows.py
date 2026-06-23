"""Transactional-guard tests for pharmacy stock & billing services.

LEAN: no engine. db.session is the centralized FakeSession; Medication /
PrescriptionItem are SimpleNamespace stand-ins. Focus = the financial/stock
integrity guards (insufficient stock, over-dispense, illegal invoice posting).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.shared.enums import StockMovementType, InvoiceStatus
from app.modules.workflows.pharmacy import PharmacyStockService
from app.modules.workflows.billing import _BillingServiceDeprecated as BillingService


def _med(stock=100, minimum=20, mid=1):
    return SimpleNamespace(
        id=mid, stock_quantity=stock, minimum_stock=minimum,
        trade_name="Amox", scientific_name="Amoxicillin", updated_at=None,
    )


# ---------------------------------------------------------------------------
# adjust_stock
# ---------------------------------------------------------------------------
def test_adjust_stock_increments_and_records_movement(patch_db_session):
    med = _med(stock=50)
    session = patch_db_session()
    session.store[1] = med

    PharmacyStockService.adjust_stock(1, 25, StockMovementType.ADJUSTMENT)

    assert med.stock_quantity == 75
    # med + movement both queued
    assert len(session.added) == 2


def test_adjust_stock_sale_decrements(patch_db_session):
    med = _med(stock=50)
    session = patch_db_session()
    session.store[1] = med
    PharmacyStockService.adjust_stock(1, -10, StockMovementType.SALE)
    assert med.stock_quantity == 40


def test_adjust_stock_insufficient_raises(patch_db_session):
    med = _med(stock=5)
    session = patch_db_session()
    session.store[1] = med
    with pytest.raises(ValueError, match="Insufficient stock"):
        PharmacyStockService.adjust_stock(1, -10, StockMovementType.SALE)
    assert med.stock_quantity == 5  # unchanged


def test_adjust_stock_negative_adjustment_clamps_to_zero(patch_db_session):
    med = _med(stock=5)
    session = patch_db_session()
    session.store[1] = med
    PharmacyStockService.adjust_stock(1, -10, StockMovementType.ADJUSTMENT)
    assert med.stock_quantity == 0


def test_adjust_stock_missing_medication_raises(patch_db_session):
    patch_db_session()  # empty store
    with pytest.raises(ValueError, match="Medication not found"):
        PharmacyStockService.adjust_stock(999, 5, StockMovementType.ADJUSTMENT)


def test_adjust_stock_emits_low_stock_signal(patch_db_session, monkeypatch):
    med = _med(stock=30, minimum=20)
    session = patch_db_session()
    session.store[1] = med
    sent = []
    import app.shared.signal_subscribers as subs
    monkeypatch.setattr(subs, "_safe_send", lambda signal, **kw: sent.append(kw))
    # drop below minimum
    PharmacyStockService.adjust_stock(1, -15, StockMovementType.SALE)
    assert med.stock_quantity == 15
    assert sent and sent[0]["current_stock"] == 15


# ---------------------------------------------------------------------------
# dispense_prescription_item
# ---------------------------------------------------------------------------
def test_dispense_updates_quantity_and_stock(patch_db_session):
    med = _med(stock=100, mid=1)
    pi = SimpleNamespace(id=100, medication_id=1, quantity=10,
                         dispensed_quantity=0, dispensed_at=None)
    session = patch_db_session()
    session.store.update({100: pi, 1: med})

    PharmacyStockService.dispense_prescription_item(100, 4, performed_by=7)
    assert pi.dispensed_quantity == 4
    assert pi.dispensed_at is not None
    assert med.stock_quantity == 96


def test_dispense_over_prescribed_raises(patch_db_session):
    pi = SimpleNamespace(id=100, medication_id=1, quantity=10, dispensed_quantity=8, dispensed_at=None)
    session = patch_db_session()
    session.store[100] = pi
    with pytest.raises(ValueError, match="more than prescribed"):
        PharmacyStockService.dispense_prescription_item(100, 5)
    assert pi.dispensed_quantity == 8  # rolled back logically (never mutated)


def test_dispense_missing_item_raises(patch_db_session):
    patch_db_session()
    with pytest.raises(ValueError, match="PrescriptionItem not found"):
        PharmacyStockService.dispense_prescription_item(404, 1)


# ---------------------------------------------------------------------------
# Billing post_invoice
# ---------------------------------------------------------------------------
def test_post_draft_invoice_succeeds():
    inv = SimpleNamespace(status=InvoiceStatus.DRAFT, posted_at=None)
    BillingService.post_invoice(inv, user_id=1)
    assert inv.status == InvoiceStatus.POSTED
    assert inv.posted_at is not None


@pytest.mark.parametrize("status", [InvoiceStatus.POSTED, "PAID", "CANCELLED"])
def test_post_non_draft_invoice_raises(status):
    inv = SimpleNamespace(status=status, posted_at=None)
    with pytest.raises(ValueError, match="DRAFT"):
        BillingService.post_invoice(inv, user_id=1)
    assert inv.posted_at is None
