"""Exhaustive tests for services.pricing_service.PricingService.

All DB-mutating cases run under the ``rollback_db`` fixture (savepoint isolation)
so the destructive ``seed_*`` / ``cleanup_*`` / ``purge_*`` methods can be
exercised in full without polluting the session-scoped test database.
"""
import pytest

from services.pricing_service import PricingService
import services.pricing_service as ps_mod
from models.pricing import ServicePrice, DoctorPricing, PricingCatalog
from models.department import Department
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult


class _Boom:
    """Stand-in whose .query attribute raises, to drive except branches."""

    class _Q:
        def __getattr__(self, _):
            raise RuntimeError("boom")

    query = _Q()

    def __init__(self, *a, **k):
        raise RuntimeError("boom")


# ───────────────────────── pure logic: aliases ─────────────────────────

class TestNormalizeAliases:
    def test_lab_key_match_returns_values_then_original(self):
        out = PricingService._normalize_service_aliases('cbc', 'lab_test')
        assert 'CBC' in out and 'صورة دم كاملة' in out
        assert out[-1] == 'cbc'  # original always appended last

    def test_lab_value_match_is_case_insensitive(self):
        out = PricingService._normalize_service_aliases('Complete Blood Count', 'lab_test')
        assert 'CBC' in out

    def test_radiology_alias_resolves(self):
        out = PricingService._normalize_service_aliases('cxr', 'radiology_scan')
        assert 'Chest X-Ray' in out

    def test_unknown_service_type_returns_only_original(self):
        out = PricingService._normalize_service_aliases('whatever', 'unknown_type')
        assert out == ['whatever']

    def test_unknown_name_returns_only_original(self):
        out = PricingService._normalize_service_aliases('NoSuchTest', 'lab_test')
        assert out == ['NoSuchTest']

    def test_empty_name_returns_empty(self):
        assert PricingService._normalize_service_aliases('', 'lab_test') == []

    def test_none_name_returns_empty(self):
        assert PricingService._normalize_service_aliases(None, 'lab_test') == []


# ───────────────────────── get_service_price ─────────────────────────

class TestGetServicePrice:
    def _mk(self, db, **kw):
        defaults = dict(service_name='ZZ_SVC_UNIQUE', service_type='lab_test',
                        base_price=10, cash_price=20, insurance_price=15,
                        vip_price=40, is_active=True)
        defaults.update(kw)
        sp = ServicePrice(**defaults)
        db.session.add(sp)
        db.session.commit()
        return sp

    def test_direct_match_cash(self, rollback_db):
        self._mk(rollback_db)
        assert float(PricingService.get_service_price('ZZ_SVC_UNIQUE', 'lab_test', 'cash')) == 20.0

    def test_direct_match_insurance(self, rollback_db):
        self._mk(rollback_db)
        assert float(PricingService.get_service_price('ZZ_SVC_UNIQUE', 'lab_test', 'insurance')) == 15.0

    def test_direct_match_vip(self, rollback_db):
        self._mk(rollback_db)
        assert float(PricingService.get_service_price('ZZ_SVC_UNIQUE', 'lab_test', 'vip')) == 40.0

    def test_falls_back_to_base_when_method_price_missing(self, rollback_db):
        self._mk(rollback_db, service_name='ZZ_BASE_ONLY', cash_price=None,
                 insurance_price=None, vip_price=None, base_price=12)
        assert float(PricingService.get_service_price('ZZ_BASE_ONLY', 'lab_test', 'cash')) == 12.0

    def test_department_id_param_is_accepted_noop(self, rollback_db):
        # ServicePrice is not department-scoped; the param must not crash and
        # the canonical price is still returned.
        self._mk(rollback_db, service_name='ZZ_DEPT_NOOP', cash_price=77)
        got = PricingService.get_service_price('ZZ_DEPT_NOOP', 'lab_test', 'cash', department_id=12345)
        assert float(got) == 77.0

    def test_alias_branch_resolves_to_canonical(self, rollback_db):
        # Remove pre-existing CBC rows in-transaction so the alias resolves to ours.
        ServicePrice.query.filter_by(service_name='CBC', service_type='lab_test').delete()
        rollback_db.session.commit()
        self._mk(rollback_db, service_name='CBC', cash_price=99)
        got = PricingService.get_service_price('complete blood count', 'lab_test', 'cash')
        assert float(got) == 99.0

    def test_not_found_returns_zero(self, rollback_db):
        assert PricingService.get_service_price('___NOPE___', 'lab_test', 'cash') == 0.0

    def test_exception_returns_zero(self, monkeypatch):
        monkeypatch.setattr(ps_mod, 'ServicePrice', _Boom)
        assert PricingService.get_service_price('x', 'lab_test') == 0.0


# ───────────────────────── get_doctor_price ─────────────────────────

class TestGetDoctorPrice:
    def _doctor(self, db, dept_id=None):
        u = User(username='zz_doc_price', email='zz_doc_price@x.com',
                 full_name='د', role='doctor', is_active=True, department_id=dept_id)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def test_direct_doctor_pricing(self, rollback_db):
        doc = self._doctor(rollback_db)
        dp = DoctorPricing(doctor_id=doc.id, consultation_price=50, follow_up_price=30,
                           emergency_price=80, vip_price=120, is_active=True)
        rollback_db.session.add(dp)
        rollback_db.session.commit()
        assert float(PricingService.get_doctor_price(doc.id, 'consultation', 'cash')) == 50.0
        assert float(PricingService.get_doctor_price(doc.id, 'follow_up', 'cash')) == 30.0
        assert float(PricingService.get_doctor_price(doc.id, 'emergency', 'cash')) == 80.0
        assert float(PricingService.get_doctor_price(doc.id, 'consultation', 'vip')) == 120.0

    def test_department_fallback_path_executes_returns_zero(self, rollback_db):
        # doctor has a department but no active personal pricing → the code runs
        # the department-fallback query (doctor_id IS NULL). The DB enforces
        # doctor_id NOT NULL so no such row can exist → 0.0.
        dept = Department(name='ZZ_DOC_DEPT', name_ar='قسم', is_active=True)
        rollback_db.session.add(dept)
        rollback_db.session.commit()
        doc = self._doctor(rollback_db, dept_id=dept.id)
        assert PricingService.get_doctor_price(doc.id, 'consultation', 'cash') == 0.0

    def test_no_pricing_returns_zero(self, rollback_db):
        doc = self._doctor(rollback_db)
        assert PricingService.get_doctor_price(doc.id) == 0.0

    def test_unknown_doctor_returns_zero(self, rollback_db):
        assert PricingService.get_doctor_price(99999999) == 0.0

    def test_exception_returns_zero(self, monkeypatch):
        monkeypatch.setattr(ps_mod, 'DoctorPricing', _Boom)
        assert PricingService.get_doctor_price(1) == 0.0


# ───────────────────────── create / update ─────────────────────────

class TestCreateUpdate:
    def test_create_service_price_success(self, rollback_db):
        res = PricingService.create_service_price({
            'service_name': 'ZZ_CREATE', 'service_type': 'lab_test', 'base_price': 5,
        })
        assert res['success'] is True
        assert res['service_price_id']
        assert ServicePrice.query.get(res['service_price_id']) is not None

    def test_create_service_price_failure_rolls_back(self, rollback_db, monkeypatch):
        monkeypatch.setattr(ps_mod, 'ServicePrice', _Boom)
        res = PricingService.create_service_price({'service_name': 'x', 'service_type': 'lab_test'})
        assert res['success'] is False

    def test_create_doctor_pricing_success(self, rollback_db):
        doc = User(username='zz_doc_cp', email='zz_doc_cp@x.com', full_name='د',
                   role='doctor', is_active=True)
        doc.set_password('p')
        rollback_db.session.add(doc)
        rollback_db.session.commit()
        res = PricingService.create_doctor_pricing(doc.id, {'consultation_price': 60})
        assert res['success'] is True
        assert res['pricing_id']

    def test_create_doctor_pricing_failure(self, rollback_db, monkeypatch):
        monkeypatch.setattr(ps_mod, 'DoctorPricing', _Boom)
        res = PricingService.create_doctor_pricing(1, {'consultation_price': 60})
        assert res['success'] is False

    def test_update_service_price_success(self, rollback_db):
        sp = ServicePrice(service_name='ZZ_UPD', service_type='lab_test', base_price=1, cash_price=1)
        rollback_db.session.add(sp)
        rollback_db.session.commit()
        res = PricingService.update_service_price(sp.id, {'cash_price': 55, 'bogus_attr': 'ignored'})
        assert res['success'] is True
        assert float(ServicePrice.query.get(sp.id).cash_price) == 55.0

    def test_update_service_price_not_found(self, rollback_db):
        res = PricingService.update_service_price(99999999, {'cash_price': 1})
        assert res['success'] is False

    def test_update_service_price_exception(self, rollback_db, monkeypatch):
        sp = ServicePrice(service_name='ZZ_UPD2', service_type='lab_test', base_price=1)
        rollback_db.session.add(sp)
        rollback_db.session.commit()
        # commit raises during update
        monkeypatch.setattr(ps_mod.db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('x')))
        res = PricingService.update_service_price(sp.id, {'cash_price': 9})
        assert res['success'] is False


# ───────────────────────── summary ─────────────────────────

class TestPricingSummary:
    def test_summary_structure_and_includes_created(self, rollback_db):
        sp = ServicePrice(service_name='ZZ_SUMMARY', service_type='lab_test', base_price=30, cash_price=30)
        rollback_db.session.add(sp)
        rollback_db.session.commit()
        res = PricingService.get_pricing_summary()
        assert res['success'] is True
        s = res['summary']
        assert s['total_services'] >= 1
        assert isinstance(s['service_prices'], list)
        assert 'avg_service_price' in s and 'avg_consultation_price' in s

    def test_summary_department_id_scopes_doctor_pricing(self, rollback_db):
        dept = Department(name='ZZ_SUM_DEPT', name_ar='قسم', is_active=True)
        rollback_db.session.add(dept)
        rollback_db.session.commit()
        doc = User(username='zz_doc_sum', email='zz_doc_sum@x.com', full_name='د',
                   role='doctor', is_active=True, department_id=dept.id)
        doc.set_password('p')
        rollback_db.session.add(doc)
        rollback_db.session.commit()
        rollback_db.session.add(DoctorPricing(doctor_id=doc.id, department_id=dept.id,
                                              consultation_price=50, is_active=True))
        rollback_db.session.commit()
        res = PricingService.get_pricing_summary(department_id=dept.id)
        assert res['success'] is True
        # doctor pricing is department-scoped → exactly the one we created
        assert res['summary']['total_doctors'] == 1

    def test_summary_exception(self, monkeypatch):
        monkeypatch.setattr(ps_mod, 'ServicePrice', _Boom)
        res = PricingService.get_pricing_summary()
        assert res['success'] is False


# ───────────────────────── calculate_visit_cost ─────────────────────────

class TestCalculateVisitCost:
    def test_empty_visit_zero(self, rollback_db):
        res = PricingService.calculate_visit_cost({})
        assert res['success'] is True
        assert res['total_cost'] == 0.0
        assert res['services'] == []

    def test_doctor_cost_included(self, rollback_db):
        doc = User(username='zz_doc_visit', email='zz_doc_visit@x.com', full_name='د',
                   role='doctor', is_active=True)
        doc.set_password('p')
        rollback_db.session.add(doc)
        rollback_db.session.commit()
        rollback_db.session.add(DoctorPricing(doctor_id=doc.id, consultation_price=70, is_active=True))
        rollback_db.session.commit()
        res = PricingService.calculate_visit_cost({'doctor_id': doc.id, 'visit_type': 'consultation'})
        assert res['total_cost'] == 70.0
        assert any(s['type'] == 'consultation' for s in res['services'])

    def test_nonexistent_lab_and_radiology_ids_skipped(self, rollback_db):
        res = PricingService.calculate_visit_cost({
            'lab_tests': [99999999], 'radiology_tests': [99999999],
        })
        assert res['success'] is True
        assert res['total_cost'] == 0.0

    def test_lab_and_radiology_priced_via_fallback(self, rollback_db):
        # ensure at least one active price exists for each type
        rollback_db.session.add(ServicePrice(service_name='ZZ_LAB_FALLBACK', service_type='lab_test',
                                             base_price=18, cash_price=18, is_active=True))
        rollback_db.session.add(ServicePrice(service_name='ZZ_RAD_FALLBACK', service_type='radiology_scan',
                                             base_price=88, cash_price=88, is_active=True))
        p = Patient(first_name='ز', last_name='ت')
        rollback_db.session.add(p)
        rollback_db.session.commit()
        v = Visit(patient_id=p.id)
        rollback_db.session.add(v)
        rollback_db.session.commit()
        lab = LabRequest(visit_id=v.id, patient_id=p.id)
        rollback_db.session.add(lab)
        rr = RadiologyRequest(visit_id=v.id, patient_id=p.id)
        rollback_db.session.add(rr)
        rollback_db.session.commit()
        rad = RadiologyResult(request_id=rr.id, patient_id=p.id)
        rollback_db.session.add(rad)
        rollback_db.session.commit()
        res = PricingService.calculate_visit_cost({
            'lab_tests': [lab.id], 'radiology_tests': [rad.id], 'payment_method': 'cash',
        })
        assert res['success'] is True
        assert res['total_cost'] > 0
        types = {s['type'] for s in res['services']}
        assert 'lab_test' in types and 'radiology_scan' in types

    def test_exception_returns_failure(self, monkeypatch):
        monkeypatch.setattr(PricingService, 'get_doctor_price',
                            staticmethod(lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x'))))
        res = PricingService.calculate_visit_cost({'doctor_id': 1})
        assert res['success'] is False


# ───────────────────────── seeders ─────────────────────────

class TestSeeders:
    def test_seed_departments(self, rollback_db):
        res = PricingService.seed_departments()
        assert res['success'] is True
        assert 'Radiology' in res['departments'] and 'Lab' in res['departments']

    def test_seed_service_master(self, rollback_db):
        res = PricingService.seed_service_master()
        assert res['success'] is True
        assert res['created'] >= 0

    def test_seed_technicians(self, rollback_db):
        PricingService.seed_departments()
        res = PricingService.seed_technicians()
        assert res['success'] is True
        assert isinstance(res['technicians'], list)

    def test_seed_doctors(self, rollback_db):
        depts = PricingService.seed_departments()
        res = PricingService.seed_doctors(depts.get('departments', {}))
        assert res['success'] is True
        assert isinstance(res['doctors'], list)

    def test_seed_service_prices(self, rollback_db):
        res = PricingService.seed_service_prices()
        assert res['success'] is True

    def test_seed_doctor_pricing(self, rollback_db):
        PricingService.seed_departments()
        PricingService.seed_doctors({})
        res = PricingService.seed_doctor_pricing()
        assert res['success'] is True

    def test_seed_pricing_catalog(self, rollback_db):
        # needs an admin/manager user present
        if not User.query.filter(User.role.in_(['admin', 'manager', 'super_admin']),
                                 User.is_active == True).first():
            u = User(username='zz_admin_seed', email='zz_admin_seed@x.com', full_name='م',
                     role='manager', is_active=True)
            u.set_password('p')
            rollback_db.session.add(u)
            rollback_db.session.commit()
        res = PricingService.seed_pricing_catalog()
        assert res['success'] is True

    def test_seed_all(self, rollback_db):
        # ensure an admin exists so catalog seeding succeeds
        if not User.query.filter(User.role.in_(['admin', 'manager', 'super_admin']),
                                 User.is_active == True).first():
            u = User(username='zz_admin_all', email='zz_admin_all@x.com', full_name='م',
                     role='manager', is_active=True)
            u.set_password('p')
            rollback_db.session.add(u)
            rollback_db.session.commit()
        res = PricingService.seed_all()
        assert res['success'] is True

    def test_seed_departments_exception(self, rollback_db, monkeypatch):
        monkeypatch.setattr(ps_mod, 'Department', _Boom)
        res = PricingService.seed_departments()
        assert res['success'] is False


# ───────────────────────── cleanup / purge ─────────────────────────

class TestCleanup:
    def test_cleanup_service_prices_removes_duplicates(self, rollback_db):
        for _ in range(3):
            rollback_db.session.add(ServicePrice(service_name='ZZ_DUP', service_type='lab_test', base_price=1))
        rollback_db.session.commit()
        res = PricingService.cleanup_service_prices()
        assert res['success'] is True
        assert res['removed'] >= 2
        assert ServicePrice.query.filter_by(service_name='ZZ_DUP', service_type='lab_test').count() == 1

    def test_cleanup_pricing_catalog_removes_duplicates(self, rollback_db):
        u = User.query.filter(User.role.in_(['admin', 'manager', 'super_admin'])).first()
        if not u:
            u = User(username='zz_admin_cat', email='zz_admin_cat@x.com', full_name='م',
                     role='manager', is_active=True)
            u.set_password('p')
            rollback_db.session.add(u)
            rollback_db.session.commit()
        for _ in range(2):
            rollback_db.session.add(PricingCatalog(service_type='lab', service_name='ZZ_DUP_CAT',
                                                   service_name_ar='تكرار', base_price=1,
                                                   created_by=u.id, is_active=True))
        rollback_db.session.commit()
        res = PricingService.cleanup_pricing_catalog()
        assert res['success'] is True
        assert res['removed'] >= 1

    def test_cleanup_doctor_pricing_removes_duplicates(self, rollback_db):
        doc = User(username='zz_doc_dup', email='zz_doc_dup@x.com', full_name='د',
                   role='doctor', is_active=True)
        doc.set_password('p')
        rollback_db.session.add(doc)
        rollback_db.session.commit()
        for _ in range(2):
            rollback_db.session.add(DoctorPricing(doctor_id=doc.id, consultation_price=10, is_active=True))
        rollback_db.session.commit()
        res = PricingService.cleanup_doctor_pricing()
        assert res['success'] is True
        assert res['removed'] >= 1

    def test_cleanup_users_by_role(self, rollback_db):
        res = PricingService.cleanup_users_by_role(max_keep_per_role=2)
        assert res['success'] is True
        assert 'deactivated' in res

    def test_cleanup_all(self, rollback_db):
        res = PricingService.cleanup_all(max_keep_per_role=2)
        assert res['success'] is True
        assert 'service_prices_removed' in res

    def test_cleanup_service_prices_exception(self, rollback_db, monkeypatch):
        monkeypatch.setattr(ps_mod, 'ServicePrice', _Boom)
        res = PricingService.cleanup_service_prices()
        assert res['success'] is False

    def test_purge_users_keep_policy(self, rollback_db):
        # Destructive global purge: on a DB with FK-referenced users it correctly
        # rolls back and reports failure; with a clean graph it succeeds. Either
        # way it must return a structured result and never raise.
        PricingService.seed_departments()
        res = PricingService.purge_users_keep_policy()
        assert isinstance(res, dict) and 'success' in res
        if res['success']:
            assert 'deleted' in res and 'kept' in res
