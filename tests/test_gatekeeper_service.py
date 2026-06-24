"""Exhaustive tests for services.gatekeeper_service.GatekeeperService.

Pure validators run without a DB. Visit-state transitions run under
``rollback_db`` (savepoint isolation) with real Visit/Patient/Payment rows.
"""
import types
from datetime import datetime, timezone, timedelta

import pytest

from services.gatekeeper_service import GatekeeperService as GK
import services.gatekeeper_service as gk_mod
from models.visit import Visit
from models.patient import Patient
from models.user import User


# ───────────────────────── pure validators ─────────────────────────

class TestValidatePaymentMethod:
    @pytest.mark.parametrize('method', ['cash', 'visa', 'card', 'insurance', 'force', 'wire', 'CASH', 'Visa'])
    def test_valid_methods(self, method):
        ok, _ = GK.validate_payment_method(method)
        assert ok is True

    def test_missing_method(self):
        ok, msg = GK.validate_payment_method('')
        assert ok is False and 'تحديد' in msg

    def test_invalid_method(self):
        ok, msg = GK.validate_payment_method('bitcoin')
        assert ok is False

    def test_cash_within_limit(self):
        ok, _ = GK.validate_payment_method('cash', amount=GK.MAX_CASH_AMOUNT)
        assert ok is True

    def test_cash_over_limit(self):
        ok, msg = GK.validate_payment_method('cash', amount=GK.MAX_CASH_AMOUNT + 1)
        assert ok is False and 'الحد المسموح' in msg


class TestValidateInsurance:
    def test_valid(self):
        ok, _ = GK.validate_insurance('Provider X', 'POL123', 80)
        assert ok is True

    def test_short_provider(self):
        ok, _ = GK.validate_insurance('AB', 'POL123', 80)
        assert ok is False

    def test_short_policy(self):
        ok, _ = GK.validate_insurance('Provider X', 'PO', 80)
        assert ok is False

    def test_coverage_below_min(self):
        ok, _ = GK.validate_insurance('Provider X', 'POL123', GK.MIN_INSURANCE_COVERAGE - 1)
        assert ok is False

    def test_coverage_above_max(self):
        ok, _ = GK.validate_insurance('Provider X', 'POL123', GK.MAX_INSURANCE_COVERAGE + 1)
        assert ok is False

    def test_coverage_not_numeric(self):
        ok, msg = GK.validate_insurance('Provider X', 'POL123', 'abc')
        assert ok is False and 'رقم' in msg


class TestValidateCardPayment:
    def test_valid(self):
        ok, _ = GK.validate_card_payment('1234', 'Jane Doe')
        assert ok is True

    def test_missing_digits(self):
        ok, _ = GK.validate_card_payment('', 'Jane Doe')
        assert ok is False

    def test_non_digit(self):
        ok, _ = GK.validate_card_payment('12ab', 'Jane Doe')
        assert ok is False

    def test_wrong_length(self):
        ok, _ = GK.validate_card_payment('12345', 'Jane Doe')
        assert ok is False

    def test_short_holder_name(self):
        ok, _ = GK.validate_card_payment('1234', 'Jo')
        assert ok is False


class TestCheckPaymentRules:
    def _visit(self, **kw):
        base = dict(total_amount=100, paid_amount=100, payment_method='cash',
                    insurance_provider=None, insurance_policy_number=None,
                    insurance_coverage_percentage=None, patient_share=None,
                    is_force_payment=False, force_payment_reason=None,
                    force_payment_approved_by=None, card_number_last_digits=None,
                    card_holder_name=None)
        base.update(kw)
        return types.SimpleNamespace(**base)

    def test_valid_cash(self):
        ok, issues = GK.check_payment_rules(self._visit())
        assert ok is True and issues == []

    def test_zero_total(self):
        ok, issues = GK.check_payment_rules(self._visit(total_amount=0, paid_amount=0))
        assert ok is False and any('الإجمالي' in i for i in issues)

    def test_overpaid(self):
        ok, issues = GK.check_payment_rules(self._visit(total_amount=50, paid_amount=80))
        assert ok is False

    def test_insurance_missing_fields(self):
        ok, issues = GK.check_payment_rules(self._visit(payment_method='insurance'))
        assert ok is False and len(issues) >= 3

    def test_insurance_patient_share_unpaid(self):
        v = self._visit(payment_method='insurance', insurance_provider='X',
                        insurance_policy_number='P1', insurance_coverage_percentage=80,
                        patient_share=40, paid_amount=10, total_amount=100)
        ok, issues = GK.check_payment_rules(v)
        assert ok is False and any('حصة المريض' in i for i in issues)

    def test_force_missing_fields(self):
        ok, issues = GK.check_payment_rules(self._visit(payment_method='force'))
        assert ok is False and len(issues) >= 3

    def test_card_missing_fields(self):
        ok, issues = GK.check_payment_rules(self._visit(payment_method='visa'))
        assert ok is False and len(issues) >= 2


# ───────────────────────── visit-state transitions ─────────────────────────

@pytest.fixture
def staff_id(rollback_db):
    u = User(username='zz_gk_staff', email='zz_gk_staff@x.com', full_name='s',
             role='reception', is_active=True)
    u.set_password('p')
    rollback_db.session.add(u)
    rollback_db.session.commit()
    return u.id


@pytest.fixture
def make_visit(rollback_db):
    created = {}

    def _make(**kw):
        if 'patient' not in created:
            p = Patient(first_name='ز', last_name='ت')
            rollback_db.session.add(p)
            rollback_db.session.commit()
            created['patient'] = p
        defaults = dict(patient_id=created['patient'].id, total_amount=100, paid_amount=0,
                        is_emergency=False, is_strong_pay=False, financial_locked=False,
                        receipt_printed=False)
        defaults.update(kw)
        v = Visit(**defaults)
        rollback_db.session.add(v)
        rollback_db.session.commit()
        return v

    return _make


class TestCanEnqueueVisit:
    def test_not_found(self, rollback_db):
        ok, msg = GK.can_enqueue_visit(99999999, 1)
        assert ok is False and 'غير موجودة' in msg

    def test_emergency_without_liability(self, make_visit):
        v = make_visit(is_emergency=True, liability_acknowledged_at=None)
        ok, msg = GK.can_enqueue_visit(v.id, 1)
        assert ok is False and 'إقرار المسؤولية' in msg

    def test_emergency_with_liability_locks(self, make_visit):
        v = make_visit(is_emergency=True, liability_acknowledged_at=datetime.now(timezone.utc))
        ok, msg = GK.can_enqueue_visit(v.id, 1)
        assert ok is True
        assert v.financial_locked is True

    def test_normal_without_receipt(self, make_visit):
        v = make_visit(receipt_printed=False)
        ok, msg = GK.can_enqueue_visit(v.id, 1)
        assert ok is False and 'سند قبض' in msg

    def test_normal_with_receipt(self, make_visit):
        v = make_visit(receipt_printed=True)
        ok, _ = GK.can_enqueue_visit(v.id, 1)
        assert ok is True


class TestCanPostGl:
    def test_not_found(self, rollback_db):
        ok, _ = GK.can_post_gl(99999999, 1)
        assert ok is False

    def test_locked(self, make_visit):
        v = make_visit(financial_locked=True, receipt_printed=True)
        ok, msg = GK.can_post_gl(v.id, 1)
        assert ok is False and 'مقفلة' in msg

    def test_no_receipt(self, make_visit):
        v = make_visit(receipt_printed=False)
        ok, _ = GK.can_post_gl(v.id, 1)
        assert ok is False

    def test_underpaid(self, make_visit):
        v = make_visit(receipt_printed=True, paid_amount=10, total_amount=100)
        ok, msg = GK.can_post_gl(v.id, 1)
        assert ok is False and 'أقل' in msg

    def test_ok(self, make_visit):
        v = make_visit(receipt_printed=True, paid_amount=100, total_amount=100)
        ok, _ = GK.can_post_gl(v.id, 1)
        assert ok is True


class TestCanArchiveVisit:
    def test_not_found(self, rollback_db):
        ok, _ = GK.can_archive_visit(99999999, 1)
        assert ok is False

    def test_no_gl_posted(self, make_visit):
        v = make_visit(gl_posted_at=None)
        ok, msg = GK.can_archive_visit(v.id, 1)
        assert ok is False and 'الترحيل المالي' in msg

    def test_locked(self, make_visit):
        v = make_visit(gl_posted_at=datetime.now(timezone.utc), financial_locked=True)
        ok, _ = GK.can_archive_visit(v.id, 1)
        assert ok is False

    def test_emergency_without_financial_completed(self, make_visit):
        v = make_visit(gl_posted_at=datetime.now(timezone.utc), financial_locked=False,
                       is_emergency=True, financial_completed_at=None)
        ok, msg = GK.can_archive_visit(v.id, 1)
        assert ok is False and 'اكتمال الدفع' in msg

    def test_ok(self, make_visit):
        v = make_visit(gl_posted_at=datetime.now(timezone.utc), financial_locked=False)
        ok, _ = GK.can_archive_visit(v.id, 1)
        assert ok is True


class TestCreateSystemReceipt:
    def test_not_found(self, rollback_db):
        ok, _ = GK.create_system_receipt(99999999, 1, 50)
        assert ok is False

    def test_success_partial(self, make_visit, staff_id):
        v = make_visit(total_amount=100)
        ok, msg = GK.create_system_receipt(v.id, staff_id, 50)
        assert ok is True and 'RCP-' in msg
        assert v.receipt_printed is True
        assert float(v.paid_amount) == 50.0

    def test_success_full_unlocks(self, make_visit, staff_id):
        v = make_visit(total_amount=100, financial_locked=True)
        ok, _ = GK.create_system_receipt(v.id, staff_id, 100)
        assert ok is True
        assert v.financial_locked is False
        assert v.financial_completed_at is not None

    def test_exception_rolls_back(self, make_visit, staff_id, monkeypatch):
        v = make_visit()
        monkeypatch.setattr(gk_mod, 'Payment', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')))
        ok, _ = GK.create_system_receipt(v.id, staff_id, 50)
        assert ok is False


class TestCreateProvisionalReceipt:
    def test_not_found(self, rollback_db):
        ok, _ = GK.create_provisional_receipt(99999999, 1, 50)
        assert ok is False

    def test_non_emergency_rejected(self, make_visit):
        v = make_visit(is_emergency=False, is_strong_pay=False)
        ok, msg = GK.create_provisional_receipt(v.id, 1, 50)
        assert ok is False and 'للطوارئ' in msg

    def test_emergency_success(self, make_visit, staff_id):
        v = make_visit(is_emergency=True)
        ok, msg = GK.create_provisional_receipt(v.id, staff_id, 50, reason='EMERGENCY')
        assert ok is True and 'PRV-' in msg
        assert v.financial_locked is True


class TestAcknowledgeLiability:
    def test_not_found(self, rollback_db):
        ok, _ = GK.acknowledge_liability(99999999, 1)
        assert ok is False

    def test_non_emergency_rejected(self, make_visit):
        v = make_visit(is_emergency=False, is_strong_pay=False)
        ok, _ = GK.acknowledge_liability(v.id, 1)
        assert ok is False

    def test_emergency_success(self, make_visit):
        v = make_visit(is_strong_pay=True)
        ok, _ = GK.acknowledge_liability(v.id, 1)
        assert ok is True
        assert v.liability_acknowledged_at is not None


class TestPostGl:
    def test_not_found(self, rollback_db):
        ok, _ = GK.post_gl(99999999, 1)
        assert ok is False

    def test_blocked_when_cannot_post(self, make_visit):
        v = make_visit(financial_locked=True, receipt_printed=True)
        ok, _ = GK.post_gl(v.id, 1)
        assert ok is False

    def test_success(self, make_visit):
        v = make_visit(receipt_printed=True, paid_amount=100, total_amount=100)
        ok, _ = GK.post_gl(v.id, 1)
        assert ok is True
        assert v.gl_posted_at is not None


class TestArchiveVisit:
    def test_not_found(self, rollback_db):
        ok, _ = GK.archive_visit(99999999, 1)
        assert ok is False

    def test_blocked_when_cannot_archive(self, make_visit):
        v = make_visit(gl_posted_at=None)
        ok, _ = GK.archive_visit(v.id, 1)
        assert ok is False

    def test_success(self, make_visit, staff_id):
        v = make_visit(gl_posted_at=datetime.now(timezone.utc), financial_locked=False)
        ok, _ = GK.archive_visit(v.id, staff_id)
        assert ok is True
        assert v.archive_status == 'ARCHIVED'


class TestValidateForcePayment:
    def _manager(self, db, username='zz_gk_mgr'):
        u = User(username=username, email=f'{username}@x.com', full_name='م',
                 role='manager', is_active=True)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def test_short_reason(self, rollback_db):
        ok, msg = GK.validate_force_payment(1, 1, 'short')
        assert ok is False and 'سبب واضح' in msg

    def test_user_not_found(self, rollback_db):
        ok, msg = GK.validate_force_payment(1, 99999999, 'a valid long reason here')
        assert ok is False and 'المستخدم غير موجود' in msg

    def test_user_wrong_role(self, rollback_db):
        u = User(username='zz_gk_recep', email='zz_gk_recep@x.com', full_name='r',
                 role='reception', is_active=True)
        u.set_password('p')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        ok, msg = GK.validate_force_payment(1, u.id, 'a valid long reason here')
        assert ok is False and 'المدير' in msg

    def test_visit_not_found(self, rollback_db):
        u = self._manager(rollback_db)
        ok, msg = GK.validate_force_payment(99999999, u.id, 'a valid long reason here')
        assert ok is False and 'الزيارة غير موجودة' in msg

    def test_creator_cannot_approve(self, rollback_db, make_visit):
        u = self._manager(rollback_db, username='zz_gk_mgr2')
        v = make_visit(created_by=u.id, is_force_payment=False)
        ok, msg = GK.validate_force_payment(v.id, u.id, 'a valid long reason here')
        assert ok is False and 'فصل المهام' in msg

    def test_success(self, rollback_db, make_visit):
        u = self._manager(rollback_db, username='zz_gk_mgr3')
        creator = User(username='zz_gk_creator', email='zz_gk_creator@x.com',
                       full_name='c', role='reception', is_active=True)
        creator.set_password('p')
        rollback_db.session.add(creator)
        rollback_db.session.commit()
        v = make_visit(created_by=creator.id, is_force_payment=False)
        ok, msg = GK.validate_force_payment(v.id, u.id, 'a valid long reason here')
        assert ok is True

    def test_percentage_exceeded(self, rollback_db, monkeypatch):
        u = self._manager(rollback_db, username='zz_gk_mgr4')

        class _Col:
            def __ge__(self, o):
                return True

            def __eq__(self, o):
                return True

        class _Q:
            def filter(self, *a, **k):
                return self

            def count(self):
                return 10

        fake_visit = types.SimpleNamespace(created_by=12345)
        fake_visit_cls = types.SimpleNamespace(created_at=_Col(), is_force_payment=_Col(), query=_Q())
        monkeypatch.setattr(gk_mod, 'Visit', fake_visit_cls)

        real_get = gk_mod.db.session.get

        def fake_get(model, ident):
            if model is gk_mod.User:
                return u
            return fake_visit

        monkeypatch.setattr(gk_mod.db.session, 'get', fake_get)
        ok, msg = GK.validate_force_payment(1, u.id, 'a valid long reason here')
        assert ok is False and 'نسبة الدفع القسري' in msg

    def test_exception(self, rollback_db, monkeypatch):
        monkeypatch.setattr(gk_mod.db.session, 'get',
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')))
        ok, msg = GK.validate_force_payment(1, 1, 'a valid long reason here')
        assert ok is False and 'خطأ' in msg


class TestForcePaymentStatistics:
    def test_returns_structure(self, rollback_db):
        stats = GK.get_force_payment_statistics(days=30)
        assert 'total_visits' in stats and 'force_percentage' in stats
        assert 'is_within_limit' in stats and stats['days'] == 30

    def test_exception(self, monkeypatch):
        class _BoomQ:
            def filter(self, *a, **k):
                raise RuntimeError('x')

        monkeypatch.setattr(gk_mod, 'Visit', types.SimpleNamespace(
            created_at=type('C', (), {'__ge__': lambda s, o: True})(),
            query=_BoomQ()))
        stats = GK.get_force_payment_statistics()
        assert 'error' in stats
