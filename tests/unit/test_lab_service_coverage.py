"""
Coverage for services/lab_service.py - the service-level contract.

Every DB-writing test runs under ``rollback_db`` so the session-scoped test
database stays pristine. Rows are created through the real service wherever
possible (``create_request``) and directly through the models otherwise.
Tenant binding (``g.tenant_id`` and ``session.info['_tenant_id']``) is set up
by the autouse conftest fixtures, exactly as in production requests.

Latent defects in ``notify_results_ready`` were fixed in
``services/lab_service.py`` (patient.full_name, recipient_id) and in
``can_transition_lab`` (to_status is now upper-cased).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent
from models.lab_request import LabRequest, LabResult
from models.lab_test_catalog import LabTestCatalog
from models.patient import Patient
from models.visit import Visit
from services.lab_service import LabService as LAB


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:10]}'


@pytest.fixture
def fx(rollback_db, app):
    """Small factory bundle: patient/visit/catalog/reagent/request/user."""

    def patient(**kw):
        p = Patient(
            tenant_id=g.tenant_id,
            first_name=kw.get('first_name', 'Test'),
            last_name=kw.get('last_name', _uniq('Pat')),
            gender=kw.get('gender', 'F'),
            phone=kw.get('phone', f'059{uuid.uuid4().int % 10**7:07d}'),
            national_id=kw.get('national_id', _uniq('NAT')),
        )
        db.session.add(p)
        db.session.commit()
        return p

    def visit(patient_id=None, **kw):
        pid = patient_id or patient().id
        v = Visit(tenant_id=g.tenant_id, patient_id=pid, status=kw.get('status', 'OPEN'))
        db.session.add(v)
        db.session.commit()
        return v

    def catalog(code=None, active=True, **kw):
        c = LabTestCatalog(
            tenant_id=g.tenant_id,
            code=code or _uniq('C').upper(),
            name_ar=kw.get('name_ar', 'Hemoglobin'),
            name_en=kw.get('name_en', 'Hemoglobin'),
            unit=kw.get('unit', 'g/dL'),
            default_reference_range=kw.get('default_reference_range', '12-16'),
            critical_low=kw.get('critical_low'),
            critical_high=kw.get('critical_high'),
            is_active=active,
            sort_order=kw.get('sort_order', 0),
        )
        db.session.add(c)
        db.session.commit()
        return c

    def reagent(name=None, qty=5, minimum=10):
        r = LabReagent(
            tenant_id=g.tenant_id,
            name=name or _uniq('Reagent'),
            stock_quantity=qty,
            minimum_stock=minimum,
        )
        db.session.add(r)
        db.session.commit()
        return r

    def user(role='doctor'):
        from models.user import User

        un = _uniq('lr_user')
        u = User(
            username=un,
            email=f'{un}@test.local',
            full_name=un,
            role=role,
            is_active=True,
            tenant_id=g.tenant_id,
        )
        u.set_password('ValidPass123!')
        db.session.add(u)
        db.session.commit()
        return u

    def request(status='REQUESTED', patient_id=None, notes='n', completed_at=None):
        pid = patient_id or patient().id
        req = LabRequest(
            tenant_id=g.tenant_id,
            patient_id=pid,
            requested_by=None,
            request_number=_uniq('LR'),
            status=status,
            notes=notes,
            completed_at=completed_at,
        )
        db.session.add(req)
        db.session.commit()
        return req

    def result(request_id, patient_id=None, **kw):
        res = LabResult(
            tenant_id=g.tenant_id,
            request_id=request_id,
            patient_id=patient_id or request(status='REQUESTED').patient_id,
            test_code=kw.get('test_code', 'HB'),
            test_name=kw.get('test_name', 'Hemoglobin'),
            value=kw.get('value'),
            unit=kw.get('unit'),
            reference_range=kw.get('reference_range'),
            status=kw.get('status', 'PENDING'),
            notes=kw.get('notes'),
            is_critical=kw.get('is_critical', False),
        )
        db.session.add(res)
        db.session.commit()
        return res

    return SimpleNamespace(
        patient=patient,
        visit=visit,
        catalog=catalog,
        reagent=reagent,
        user=user,
        request=request,
        result=result,
    )


class _RaisingSession:
    def execute(self, *_a, **_kw):
        raise RuntimeError('boom')


class _RaisingDB:
    session = _RaisingSession()


@pytest.fixture
def raising_db(monkeypatch):
    """Swap the db handle the service sees for one whose session always raises."""
    import importlib

    lab_module = importlib.import_module('services.lab_service')

    monkeypatch.setattr(lab_module, 'db', _RaisingDB())


# ---------------------------------------------------------------------------
# create_request - walk-in / standalone-lab branch (doctor & reception off)
# ---------------------------------------------------------------------------
class TestCreateRequestWalkIn:
    @pytest.fixture
    def standalone_lab_only(self, monkeypatch):
        """Lab module enabled; doctor and reception disabled."""
        from services.feature_gate_service import FeatureGateService

        monkeypatch.setattr(
            FeatureGateService,
            'module_enabled',
            staticmethod(lambda _tenant_id, module: module == 'lab'),
        )

    def test_walk_in_requires_patient_id(self, fx, standalone_lab_only):
        c = fx.catalog()
        ok, res = LAB.create_request(None, [c.id])
        assert ok is False
        assert res['error'] == 'patient_id is required for a walk-in lab request without a visit'

    def test_walk_in_patient_not_found(self, fx, standalone_lab_only):
        c = fx.catalog()
        ok, res = LAB.create_request(None, [c.id], patient_id=99999999)
        assert ok is False
        assert res['error'] == 'Patient not found'

    def test_walk_in_success_creates_request_without_visit(self, fx, standalone_lab_only):
        p = fx.patient()
        c = fx.catalog()
        ok, res = LAB.create_request(None, [c.id], patient_id=str(p.id))
        assert ok is True
        req = db.session.get(LabRequest, res['lab_request_id'])
        assert req is not None
        assert req.visit_id is None
        assert req.patient_id == p.id
        assert res['request_number'].startswith('LR-0-')

    def test_walk_in_does_not_require_prescriber(self, fx, standalone_lab_only):
        p = fx.patient()
        c = fx.catalog()
        # requested_by intentionally omitted: doctor module disabled
        ok, _res = LAB.create_request(None, [c.id], patient_id=p.id)
        assert ok is True

    def test_visit_id_required_when_doctor_enabled(self, fx):
        # Default shared tenant has doctor enabled.
        c = fx.catalog()
        ok, res = LAB.create_request(None, [c.id], patient_id=1, requested_by=fx.user().id)
        assert ok is False
        assert res['error'] == 'visit_id is required when the doctor or reception module is enabled'

    def test_explicit_tenant_id_kwarg_is_honoured(self, fx):
        v = fx.visit()
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id], requested_by=fx.user().id, tenant_id=g.tenant_id)
        assert ok is True
        assert db.session.get(LabRequest, res['lab_request_id']).tenant_id == g.tenant_id


class TestGetRequestById:
    def test_returns_request_for_known_id(self, fx):
        req = fx.request()
        found = LAB.get_request_by_id(req.id)
        assert found is not None
        assert found.id == req.id

    def test_returns_none_for_unknown_id(self, fx):
        assert LAB.get_request_by_id(99999999) is None


# ---------------------------------------------------------------------------
# create_request - direct rows (result_id / both name & code fallbacks)
# ---------------------------------------------------------------------------
class TestCreateRequestHelpers:
    def test_no_test_ids_is_rejected(self, fx):
        ok, res = LAB.create_request(1, [])
        assert ok is False
        assert res['error'] == 'No test IDs provided'

    def test_visit_not_found(self, fx):
        c = fx.catalog()
        ok, res = LAB.create_request(99999999, [c.id], requested_by=fx.user().id)
        assert ok is False
        assert res['error'] == 'Visit not found'

    def test_prescriber_required_when_doctor_module_enabled(self, fx):
        v = fx.visit()
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id])
        assert ok is False
        assert res['error'] == (
            'Prescriber (requested_by) is required when the doctor module is enabled'
        )

    def test_unknown_test_rolls_back_pending_request(self, fx):
        v = fx.visit()
        before = db.session.execute(select(LabRequest)).scalars().all()
        ok, res = LAB.create_request(v.id, [99999998], requested_by=fx.user().id)
        assert ok is False
        assert 'Unknown or inactive test IDs' in res['error']
        after = db.session.execute(select(LabRequest)).scalars().all()
        assert len(after) == len(before)

    def test_inactive_catalog_entry_is_rejected(self, fx):
        v = fx.visit()
        c = fx.catalog(active=False)
        ok, res = LAB.create_request(v.id, [c.id], requested_by=fx.user().id)
        assert ok is False
        assert 'Unknown or inactive test IDs' in res['error']

    def test_name_falls_back_to_code_and_back(self, fx):
        v = fx.visit()
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id], requested_by=fx.user().id)
        assert ok is True
        result = (
            db.session.execute(select(LabResult).filter_by(request_id=res['lab_request_id']))
            .scalars()
            .one()
        )
        assert result.test_code == c.code
        assert result.test_name == c.name_ar  # name_ar preferred over name_en


# ---------------------------------------------------------------------------
# Worklist / counts / dashboard
# ---------------------------------------------------------------------------
class TestWorklistAndStats:
    def test_done_today_filter(self, fx):
        done = fx.request(status='DONE', completed_at=datetime.now(UTC))
        fx.request(status='REQUESTED')
        wl = LAB.get_worklist(status='DONE_TODAY')
        assert any(r.id == done.id for r in wl)
        assert all(r.status == 'DONE' for r in wl)

    def test_invalid_status_coerced_to_requested(self, fx):
        req = fx.request(status='REQUESTED')
        other = fx.request(status='ANALYZING')
        wl = LAB.get_worklist(status='NOPE')
        assert any(r.id == req.id for r in wl)
        assert all(r.status == 'REQUESTED' for r in wl)
        assert all(r.id != other.id for r in wl)

    def test_done_filter_matches_status(self, fx):
        done = fx.request(status='DONE', completed_at=datetime.now(UTC))
        assert any(r.id == done.id for r in LAB.get_worklist(status='DONE'))

    def test_all_filter_returns_mixed_statuses(self, fx):
        fx.request(status='REQUESTED')
        wl = LAB.get_worklist(status='ALL')
        assert isinstance(wl, list)
        assert len(wl) >= 1

    def test_worklist_honours_limit(self, fx):
        fx.request(status='REQUESTED')
        assert len(LAB.get_worklist(status='ALL', limit=1)) == 1

    def test_get_request_counts_delta(self, fx):
        before = LAB.get_request_counts()
        v = fx.visit()
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id], requested_by=fx.user().id)
        assert ok is True
        LAB.transition_request(res['lab_request_id'], 'COLLECTED')
        after = LAB.get_request_counts()
        assert after['requested'] - before['requested'] == 0  # moved to COLLECTED
        assert after['in_progress'] - before['in_progress'] == 1

    def test_done_today_count_delta(self, fx):
        before = LAB.get_request_counts()
        fx.request(status='DONE', completed_at=datetime.now(UTC))
        after = LAB.get_request_counts()
        assert after['done_today'] - before['done_today'] == 1

    def test_dashboard_stats_shape_and_delta(self, fx):
        before = LAB.get_dashboard_stats()
        assert set(before) == {'today_requests', 'pending_requests', 'completed_today'}
        fx.request(status='DONE', completed_at=datetime.now(UTC))
        after = LAB.get_dashboard_stats()
        assert after['completed_today'] - before['completed_today'] == 1
        assert after['today_requests'] - before['today_requests'] == 1

    def test_get_results_by_patient_returns_only_completed(self, fx):
        p = fx.patient()
        v = fx.visit(patient_id=p.id)
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id], requested_by=fx.user().id)
        assert ok is True
        rows = LAB.get_results_by_patient(p.id)
        assert rows == []  # PENDING results are excluded
        for r in LAB.get_results_by_request(res['lab_request_id']):
            r.status = 'COMPLETED'
        db.session.commit()
        rows = LAB.get_results_by_patient(p.id)
        assert len(rows) == 1
        assert rows[0].status == 'COMPLETED'


# ---------------------------------------------------------------------------
# create_results_from_form - dict-with-rows path
# ---------------------------------------------------------------------------
class TestCreateResultsFromRows:
    def test_non_dict_row_reports_error(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(req, {'rows': ['not-a-dict']})
        assert created == []
        assert errors == ['Row 0: invalid row']

    def test_empty_row_is_skipped_silently(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(req, {'rows': [{}]})
        assert created == []
        assert errors == []

    def test_row_with_only_a_value_reports_missing_code(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(req, {'rows': [{'value': '5'}]})
        assert created == []
        assert errors == ['Row 0: test_code or test_name required']

    def test_row_creates_result_with_explicit_critical_true(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req,
            {
                'rows': [
                    {
                        'test_code': 'HB',
                        'test_name': 'Hemoglobin',
                        'value': '12',
                        'is_critical': True,
                    }
                ]
            },
        )
        assert errors == []
        res = db.session.get(LabResult, created[0])
        assert res.is_critical is True
        assert res.test_code == 'HB'

    @pytest.mark.parametrize(
        ('raw', 'expected'),
        [
            (1, True),
            (0, False),
            (1.5, True),
            ('yes', True),
            ('ON', True),
            ('true', True),
            ('1', True),
            ('no', False),
            ({'x': 1}, False),
        ],
    )
    def test_parse_critical_raw_variants(self, fx, raw, expected):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'test_code': 'HB', 'value': '12', 'is_critical': raw}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is expected

    def test_auto_critical_high_triggered_from_catalog(self, fx):
        fx.catalog(code='HG', critical_high='4', critical_low=None)
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'test_code': 'HG', 'value': '5'}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is True

    def test_auto_critical_low_triggered_from_catalog(self, fx):
        fx.catalog(code='HL', critical_low='10', critical_high=None)
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'test_code': 'HL', 'value': '5'}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is True

    def test_auto_critical_ignores_unparseable_critical_bounds(self, fx):
        fx.catalog(code='HBAD', critical_low='abc', critical_high='xyz')
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'test_code': 'HBAD', 'value': '999'}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is False

    def test_auto_critical_unparseable_value_is_not_critical(self, fx):
        fx.catalog(code='HNV', critical_low='0', critical_high='100')
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'test_code': 'HNV', 'value': 'not-a-number'}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is False

    def test_auto_critical_unknown_code_is_not_critical(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'test_code': 'NOSUCHCODE', 'value': '999'}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is False

    def test_auto_critical_explicit_wins_over_catalog(self, fx):
        fx.catalog(code='HE', critical_low='0', critical_high='100')
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'test_code': 'HE', 'value': '50', 'is_critical': 'yes'}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is True

    def test_catalog_lookup_failure_is_swallowed(self, fx, monkeypatch):
        fx.catalog(code='HBOOM', critical_low='0', critical_high='1')
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        real_execute = db.session.execute

        def flaky(stmt, *a, **kw):
            if 'lab_test_catalog' in str(stmt):
                raise RuntimeError('catalog boom')
            return real_execute(stmt, *a, **kw)

        monkeypatch.setattr(db.session, 'execute', flaky)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'test_code': 'HBOOM', 'value': '5'}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is False

    def test_value_only_row_never_reaches_catalog(self, fx):
        # value present but no code/name: _auto_critical returns False early
        # (falsy code), then the row-level "code required" error is raised.
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'value': '12', 'unit': 'g/dL'}]}
        )
        assert created == []
        assert errors == ['Row 0: test_code or test_name required']

    def test_update_existing_result_via_rows(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        res = fx.result(req.id, patient_id=v.patient_id, test_code='OLD', value='1')
        created, errors = LAB.create_results_from_form(
            req,
            {
                'rows': [
                    {
                        'result_id': str(res.id),
                        'value': '42',
                        'test_code': 'NEW',
                        'test_name': 'Renamed',
                        'status': 'VALIDATED',
                        'reference_range': '10-20',
                        'notes': 'updated',
                        'is_critical': True,
                    }
                ]
            },
        )
        assert errors == []
        assert created == [res.id]
        updated = db.session.get(LabResult, res.id)
        assert updated.value == '42'
        assert updated.test_code == 'NEW'
        assert updated.status == 'VALIDATED'
        assert updated.reference_range == '10-20'
        assert updated.notes == 'updated'
        assert updated.is_critical is True

    def test_update_existing_result_invalid_status_becomes_pending(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        res = fx.result(req.id, patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'result_id': res.id, 'status': 'BOGUS', 'value': '9'}]}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).status == 'PENDING'

    def test_result_id_not_found_reports_error(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'result_id': '99999999', 'value': '1'}]}
        )
        assert created == []
        assert errors == ['Row 0: result not found']

    def test_result_id_from_id_key_is_accepted(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        res = fx.result(req.id, patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'id': str(res.id), 'value': '7'}]}
        )
        assert errors == []
        assert created == [res.id]

    def test_unparseable_result_id_falls_back_to_create(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'result_id': 'abc', 'test_code': 'HX', 'value': '3'}]}
        )
        assert errors == []
        assert len(created) == 1
        assert db.session.get(LabResult, created[0]).test_code == 'HX'

    def test_row_raising_inside_processing_is_collected_as_error(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        # int value -> (value or '').strip() raises AttributeError inside the row handler
        created, errors = LAB.create_results_from_form(
            req, {'rows': [{'value': 123, 'test_code': 'HX'}]}
        )
        assert created == []
        assert len(errors) == 1
        assert errors[0].startswith('Row 0: ')

    def test_row_reference_range_keys(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req,
            {
                'rows': [
                    {'test_code': 'A', 'range': '1-9'},
                    {'test_code': 'B', 'reference_range': None, 'range': None},
                ]
            },
        )
        assert errors == []
        a, b = (db.session.get(LabResult, rid) for rid in created)
        assert a.reference_range == '1-9'
        assert b.reference_range == ''


# ---------------------------------------------------------------------------
# create_results_from_form - parallel arrays path
# ---------------------------------------------------------------------------
class TestCreateResultsFromArrays:
    def test_empty_form_data_returns_two_empty_lists(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        assert LAB.create_results_from_form(req, {}) == ([], [])

    def test_test_names_feed_missing_test_codes(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'test_names': ['Glucose'], 'values': ['90'], 'units': ['mg']}
        )
        assert errors == []
        res = db.session.get(LabResult, created[0])
        assert res.test_code == 'Glucose'
        assert res.test_name == 'Glucose'

    def test_test_codes_without_names_become_names(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'test_codes': ['HB'], 'values': ['13']}
        )
        assert errors == []
        res = db.session.get(LabResult, created[0])
        assert res.test_name == 'HB'

    def test_code_only_pair_updates_existing_result(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        res = fx.result(req.id, patient_id=v.patient_id, test_code='OLD')
        created, errors = LAB.create_results_from_form(
            req,
            {
                'result_ids': [str(res.id)],
                'test_codes': ['NEWC'],
                'test_names': ['NEWN'],
                'values': ['8'],
                'units': ['g/dL'],
                'ranges': ['1-20'],
                'statuses': ['COMPLETED'],
                'notes_list': ['note'],
                'is_critical': [True],
            },
        )
        assert errors == []
        assert created == [res.id]
        updated = db.session.get(LabResult, res.id)
        assert updated.test_code == 'NEWC'
        assert updated.value == '8'
        assert updated.status == 'COMPLETED'
        assert updated.is_critical is True

    def test_result_id_not_found_reports_error(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'result_ids': ['99999999'], 'values': ['1'], 'test_codes': ['HB']}
        )
        assert created == []
        assert errors == ['Row 0: result not found']

    def test_unparseable_result_id_falls_back_to_create(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'result_ids': ['abc'], 'test_codes': ['HX'], 'values': ['1']}
        )
        assert errors == []
        assert len(created) == 1

    def test_row_with_all_empty_fields_is_skipped(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(req, {'statuses': ['PENDING']})
        assert created == []
        assert errors == []

    def test_value_only_arrays_skip_rows_without_code(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(req, {'values': ['5'], 'units': ['mg']})
        assert created == []
        assert errors == []

    def test_none_entries_in_arrays_are_tolerated(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req,
            {
                'test_codes': [None],
                'test_names': ['Fallback'],
                'values': [None],
                'units': [None],
                'ranges': [None],
                'statuses': [None],
                'notes_list': [None],
                'is_critical': [False],
            },
        )
        assert errors == []
        res = db.session.get(LabResult, created[0])
        assert res.status == 'PENDING'
        assert res.value == ''
        assert res.unit == ''
        assert res.notes == ''

    def test_invalid_status_becomes_pending(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'test_codes': ['HB'], 'values': ['1'], 'statuses': ['BOGUS']}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).status == 'PENDING'

    def test_explicit_critical_from_is_critical_list(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req,
            {'test_codes': ['HB'], 'values': ['1'], 'is_critical_list': ['true']},
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is True

    def test_explicit_critical_from_critical_flags(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req,
            {'test_codes': ['HB'], 'values': ['1'], 'critical_flags': [1]},
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is True

    def test_auto_critical_from_catalog_via_arrays(self, fx):
        fx.catalog(code='HARR', critical_high='4')
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(
            req, {'test_codes': ['HARR'], 'values': ['9']}
        )
        assert errors == []
        assert db.session.get(LabResult, created[0]).is_critical is True

    def test_non_string_code_raises_row_exception_collected_as_error(self, fx):
        v = fx.visit()
        req = fx.request(patient_id=v.patient_id)
        created, errors = LAB.create_results_from_form(req, {'test_codes': [123], 'values': ['1']})
        assert created == []
        assert len(errors) == 1
        assert errors[0].startswith('Row 0: ')


# ---------------------------------------------------------------------------
# validate_lab_results / finalize_results
# ---------------------------------------------------------------------------
class TestValidateAndFinalize:
    def test_validate_reports_missing_name_and_unit(self, fx):
        rows = [
            SimpleNamespace(test_name='X', value='1', unit='mg'),
            SimpleNamespace(test_name='', value='', unit=''),
            SimpleNamespace(test_name='Y', value='5', unit=''),
        ]
        errs = LAB.validate_lab_results(rows)
        assert 'Test name is required' in errs
        assert any('Unit required for Y' in e for e in errs)
        assert len(errs) == 2

    def test_validate_no_errors_for_well_formed_rows(self, fx):
        rows = [SimpleNamespace(test_name='X', value='1', unit='mg')]
        assert LAB.validate_lab_results(rows) == []

    def test_finalize_marks_results_completed_and_request_done(self, fx):
        v = fx.visit()
        c = fx.catalog()
        _ok, res = LAB.create_request(v.id, [c.id], requested_by=fx.user().id)
        rid = res['lab_request_id']
        assert LAB.finalize_results(rid) is True
        req = db.session.get(LabRequest, rid)
        assert req.status == 'DONE'
        assert req.completed_at is not None
        assert all(
            r.status == 'COMPLETED'
            for r in db.session.execute(select(LabResult).filter_by(request_id=rid)).scalars().all()
        )

    def test_finalize_unknown_request_still_commits(self, fx):
        assert LAB.finalize_results(99999999) is True

    def test_finalize_returns_false_when_commit_fails(self, fx, monkeypatch):
        import importlib

        lab_module = importlib.import_module('services.lab_service')
        monkeypatch.setattr(lab_module, 'safe_commit', lambda *_a, **_k: False)
        assert LAB.finalize_results(fx.request().id) is False

    def test_finalize_returns_false_on_exception(self, fx, raising_db):
        assert LAB.finalize_results(fx.request().id) is False


# ---------------------------------------------------------------------------
# Quality control
# ---------------------------------------------------------------------------
class TestQualityEntries:
    def test_create_and_fetch_entries_with_limit(self, fx):
        e1 = LAB.create_quality_entry(
            {
                'test_code': 'QCLIM',
                'measured_value': '5.1',
                'control_level': 'LOW',
                'status': 'PASS',
            }
        )
        assert e1 is not None
        entries = LAB.get_quality_entries(limit=1)
        assert len(entries) == 1
        assert entries[0].test_code == 'QCLIM'

    def test_create_entry_invalid_payload_returns_none(self, fx):
        assert LAB.create_quality_entry({'bogus_field': 1}) is None

    def test_create_entry_constraint_violation_returns_none(self, fx):
        # control_level outside LOW/NORMAL/HIGH violates chk_lab_qc_control_level
        assert (
            LAB.create_quality_entry(
                {
                    'test_code': 'QCBAD',
                    'measured_value': '5',
                    'control_level': 'BOGUS',
                    'status': 'PASS',
                }
            )
            is None
        )

    def test_create_entry_returns_none_when_commit_fails(self, fx, monkeypatch):
        import importlib

        lab_module = importlib.import_module('services.lab_service')
        monkeypatch.setattr(lab_module, 'safe_commit', lambda *_a, **_k: False)
        assert LAB.create_quality_entry({'test_code': 'QCMK', 'measured_value': '5'}) is None

    def test_quality_entries_ordered_newest_first(self, fx):
        older = LabQualityControlEntry(
            tenant_id=g.tenant_id,
            test_code='QCO',
            measured_value='1',
            control_level='NORMAL',
            status='PASS',
            recorded_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        db.session.add(older)
        db.session.commit()
        newest = LAB.create_quality_entry({'test_code': 'QCO', 'measured_value': '2'})
        assert newest is not None
        entries = [e for e in LAB.get_quality_entries() if e.test_code == 'QCO']
        assert entries[0].id == newest.id


# ---------------------------------------------------------------------------
# Reagents
# ---------------------------------------------------------------------------
class TestReagents:
    def test_get_reagents_returns_all_sorted(self, fx):
        fx.reagent(name='ZZ_reagent_marker', qty=1, minimum=1)
        names = [r.name for r in LAB.get_reagents()]
        assert 'ZZ_reagent_marker' in names
        assert names == sorted(names)

    def test_low_stock_default_uses_minimum_stock(self, fx):
        low = fx.reagent(name=_uniq('lowstock'), qty=3, minimum=10)
        fine = fx.reagent(name=_uniq('finestock'), qty=99, minimum=1)
        ids = [r.id for r in LAB.get_low_stock_reagents()]
        assert low.id in ids
        assert fine.id not in ids

    def test_low_stock_with_explicit_threshold(self, fx):
        r = fx.reagent(qty=40, minimum=1)
        ids = [x.id for x in LAB.get_low_stock_reagents(threshold=50)]
        assert r.id in ids

    def test_low_stock_ordered_ascending(self, fx):
        fx.reagent(qty=8, minimum=100)
        fx.reagent(qty=1, minimum=100)
        stocks = [r.stock_quantity for r in LAB.get_low_stock_reagents()]
        assert stocks == sorted(stocks)

    def test_update_reagent_quantity_success(self, fx):
        r = fx.reagent(qty=2, minimum=10)
        assert LAB.update_reagent_quantity(r.id, 42) is True
        assert db.session.get(LabReagent, r.id).stock_quantity == 42

    def test_update_reagent_quantity_missing_returns_false(self, fx):
        assert LAB.update_reagent_quantity(99999999, 1) is False

    def test_update_reagent_quantity_false_when_commit_fails(self, fx, monkeypatch):
        r = fx.reagent()
        import importlib

        lab_module = importlib.import_module('services.lab_service')
        monkeypatch.setattr(lab_module, 'safe_commit', lambda *_a, **_k: False)
        assert LAB.update_reagent_quantity(r.id, 7) is False

    def test_update_reagent_quantity_false_on_exception(self, fx, raising_db):
        assert LAB.update_reagent_quantity(1, 1) is False


# ---------------------------------------------------------------------------
# Notification - pinned contract (see module docstring)
# ---------------------------------------------------------------------------
class TestNotifyResultsReady:
    def test_missing_patient_and_request_is_silent_noop(self, fx):
        LAB.notify_results_ready(99999999, 99999999)  # must not raise

    def test_existing_row_does_not_raise(self, fx):
        p = fx.patient()
        req = fx.request(patient_id=p.id)
        LAB.notify_results_ready(p.id, req.id)

    def test_notify_reaches_send_notification(self, fx, monkeypatch):
        """notify_results_ready delivers a lab_result info notification.

        The message must reference ``patient.full_name``, and the call must
        use ``recipient_id``/``related_entity_id`` — matching the real
        NotificationService.send_notification contract.
        """
        calls = []
        from services.notification_service import NotificationService

        monkeypatch.setattr(NotificationService, 'send_notification', lambda **kw: calls.append(kw))
        p = fx.patient()
        req = fx.request(patient_id=p.id)
        LAB.notify_results_ready(p.id, req.id)
        assert len(calls) == 1
        assert calls[0].get('related_entity_type') == 'lab_request'
        assert calls[0].get('related_entity_id') == req.id
        assert calls[0].get('notification_type') == 'info'

    def test_notification_service_exception_is_swallowed(self, fx, monkeypatch):
        from services.notification_service import NotificationService

        def boom(**_kw):
            raise RuntimeError('smtp down')

        monkeypatch.setattr(NotificationService, 'send_notification', boom)
        p = fx.patient()
        req = fx.request(patient_id=p.id)
        LAB.notify_results_ready(p.id, req.id)  # must not raise


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
class TestLogAction:
    def test_disallowed_action_is_recorded_as_update(self, fx):
        from models.audit_trail import AuditTrail

        LAB.log_action('bogus_action', 'details', user_id=None)
        row = (
            db.session.execute(
                select(AuditTrail).filter_by(entity_type='lab_test').order_by(AuditTrail.id.desc())
            )
            .scalars()
            .first()
        )
        assert row.action == 'update'

    def test_allowed_action_and_empty_details_are_recorded(self, fx):
        from models.audit_trail import AuditTrail

        LAB.log_action('create', None)
        row = (
            db.session.execute(
                select(AuditTrail).filter_by(entity_type='lab_test').order_by(AuditTrail.id.desc())
            )
            .scalars()
            .first()
        )
        assert row.action == 'create'
        assert row.description == '[lab] create'

    def test_details_are_included_in_description(self, fx):
        from models.audit_trail import AuditTrail

        LAB.log_action('update', 'something happened')
        row = (
            db.session.execute(
                select(AuditTrail).filter_by(entity_type='lab_test').order_by(AuditTrail.id.desc())
            )
            .scalars()
            .first()
        )
        assert row.description == '[lab] update: something happened'

    def test_commit_failure_is_swallowed(self, fx, monkeypatch):
        def boom(*_a, **_k):
            raise RuntimeError('audit boom')

        import importlib

        lab_module = importlib.import_module('services.lab_service')
        monkeypatch.setattr(lab_module, 'safe_commit', boom)
        LAB.log_action('update', 'x')  # must not raise


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
class TestStateMachine:
    @pytest.mark.parametrize(
        ('from_status', 'to_status', 'expected'),
        [
            ('REQUESTED', 'COLLECTED', True),
            ('REQUESTED', 'DONE', False),
            ('COLLECTED', 'RECEIVED', True),
            ('RECEIVED', 'ANALYZING', True),
            ('ANALYZING', 'REVIEWED', True),
            ('REVIEWED', 'APPROVED', True),
            ('APPROVED', 'IN_PROGRESS', True),
            ('APPROVED', 'DONE', True),
            ('IN_PROGRESS', 'DONE', True),
            ('DONE', 'COLLECTED', False),
            ('CANCELLED', 'COLLECTED', False),
            ('done', 'collected', False),
            (None, 'COLLECTED', False),
            ('REQUESTED', None, False),
        ],
    )
    def test_can_transition_lab(self, from_status, to_status, expected):
        assert LAB.can_transition_lab(from_status, to_status) is expected

    def test_can_transition_lab_is_case_insensitive(self):
        # both from_status and to_status are upper-cased before comparison
        assert LAB.can_transition_lab('requested', 'collected') is True
        assert LAB.can_transition_lab('REQUESTED', 'COLLECTED') is True
        assert LAB.can_transition_lab('done', 'CONFIRMED') is False

    def test_transition_request_not_found(self, fx):
        ok, res = LAB.transition_request(99999999, 'COLLECTED')
        assert ok is False
        assert res['error'] == 'Lab request not found'

    def test_transition_request_invalid_transition(self, fx):
        req = fx.request(status='REQUESTED')
        ok, res = LAB.transition_request(req.id, 'DONE')
        assert ok is False
        assert res['error'] == 'Invalid transition REQUESTED -> DONE'

    def test_transition_request_none_status(self, fx):
        req = fx.request(status='REQUESTED')
        ok, res = LAB.transition_request(req.id, None)
        assert ok is False
        assert 'Invalid transition' in res['error']

    def test_collection_time_set_on_collect(self, fx):
        req = fx.request(status='REQUESTED')
        ok, res = LAB.transition_request(req.id, 'collected', actor_id=fx.user(role='lab').id)
        assert ok is True
        assert res['status'] == 'COLLECTED'
        assert db.session.get(LabRequest, req.id).collection_time is not None

    def test_received_time_set_on_receive(self, fx):
        req = fx.request(status='COLLECTED')
        ok, _res = LAB.transition_request(req.id, 'RECEIVED')
        assert ok is True
        assert db.session.get(LabRequest, req.id).received_time is not None

    def test_completed_at_set_on_done(self, fx):
        req = fx.request(status='IN_PROGRESS')
        ok, _res = LAB.transition_request(req.id, 'DONE')
        assert ok is True
        assert db.session.get(LabRequest, req.id).completed_at is not None

    def test_transition_fails_when_commit_fails(self, fx, monkeypatch):
        import importlib

        lab_module = importlib.import_module('services.lab_service')
        monkeypatch.setattr(lab_module, 'safe_commit', lambda *_a, **_k: False)
        req = fx.request(status='REQUESTED')
        ok, res = LAB.transition_request(req.id, 'COLLECTED')
        assert ok is False
        assert res['error'] == 'Error transitioning lab request'


# ---------------------------------------------------------------------------
# Cancel & amend
# ---------------------------------------------------------------------------
class TestCancelAndAmend:
    def test_cancel_request_success_with_reason_appends_note(self, fx):
        req = fx.request(status='REQUESTED', notes='original note')
        ok, res = LAB.cancel_request(req.id, cancelled_by=fx.user().id, reason='patient refused')
        assert ok is True
        assert res['status'] == 'CANCELLED'
        note = db.session.get(LabRequest, req.id).notes
        assert 'original note' in note
        assert '[CANCELLED by' in note
        assert 'patient refused' in note

    def test_cancel_request_success_without_reason(self, fx):
        req = fx.request(status='REQUESTED', notes=None)
        ok, _res = LAB.cancel_request(req.id, cancelled_by=fx.user().id)
        assert ok is True
        assert db.session.get(LabRequest, req.id).notes is None

    def test_cancel_terminal_request_is_rejected(self, fx):
        for status in ('DONE', 'CANCELLED'):
            req = fx.request(status=status)
            ok, res = LAB.cancel_request(req.id, cancelled_by=fx.user().id)
            assert ok is False
            assert f'status {status}' in res['error']

    def test_cancel_not_found(self, fx):
        ok, res = LAB.cancel_request(99999999, cancelled_by=fx.user().id)
        assert ok is False
        assert res['error'] == 'Lab request not found'

    def test_cancel_fails_when_commit_fails(self, fx, monkeypatch):
        import importlib

        lab_module = importlib.import_module('services.lab_service')
        monkeypatch.setattr(lab_module, 'safe_commit', lambda *_a, **_k: False)
        req = fx.request(status='REQUESTED')
        ok, res = LAB.cancel_request(req.id, cancelled_by=1)
        assert ok is False
        assert res['error'] == 'Error cancelling lab request'

    def test_cancel_fails_on_exception(self, fx, raising_db):
        ok, res = LAB.cancel_request(1, cancelled_by=1)
        assert ok is False
        assert res['error'] == 'Error cancelling lab request'

    def test_amend_result_success(self, fx):
        req = fx.request()
        res = fx.result(req.id, patient_id=req.patient_id, value='1', unit='mg')
        ok, payload = LAB.amend_result(
            res.id,
            value='12',
            unit='g/dL',
            notes='amended',
            is_critical=True,
            amended_by=fx.user(role='lab').id,
        )
        assert ok is True
        assert payload == {'result_id': res.id, 'is_critical': True}
        updated = db.session.get(LabResult, res.id)
        assert updated.value == '12'
        assert updated.unit == 'g/dL'
        assert updated.notes == 'amended'
        assert updated.amended_at is not None
        assert updated.amended_by is not None

    def test_amend_result_keeps_omitted_fields(self, fx):
        req = fx.request()
        res = fx.result(req.id, patient_id=req.patient_id, value='99', unit='mmol')
        ok, _payload = LAB.amend_result(res.id)
        assert ok is True
        updated = db.session.get(LabResult, res.id)
        assert updated.value == '99'
        assert updated.unit == 'mmol'
        assert updated.is_critical is False

    def test_amend_result_not_found(self, fx):
        ok, res = LAB.amend_result(99999999, value='1')
        assert ok is False
        assert res['error'] == 'Lab result not found'

    def test_amend_result_fails_when_commit_fails(self, fx, monkeypatch):
        import importlib

        lab_module = importlib.import_module('services.lab_service')
        monkeypatch.setattr(lab_module, 'safe_commit', lambda *_a, **_k: False)
        req = fx.request()
        res = fx.result(req.id, patient_id=req.patient_id)
        ok, payload = LAB.amend_result(res.id, value='1')
        assert ok is False
        assert payload['error'] == 'Error amending lab result'

    def test_amend_result_fails_on_exception(self, fx, raising_db):
        ok, payload = LAB.amend_result(1, value='1')
        assert ok is False
        assert payload['error'] == 'Error amending lab result'


# ---------------------------------------------------------------------------
# Catalog lookup / listing
# ---------------------------------------------------------------------------
class TestCatalogLookup:
    def test_lookup_without_tenant_filter(self, fx):
        c = fx.catalog()
        assert LAB.lookup_catalog_by_code(c.code).id == c.id

    def test_lookup_with_matching_tenant(self, fx):
        c = fx.catalog()
        assert LAB.lookup_catalog_by_code(c.code, tenant_id=g.tenant_id).id == c.id

    def test_lookup_with_foreign_tenant_finds_nothing(self, fx):
        c = fx.catalog()
        assert LAB.lookup_catalog_by_code(c.code, tenant_id=99999999) is None

    def test_lookup_missing_code_returns_none(self, fx):
        assert LAB.lookup_catalog_by_code('NOSUCHCODE123') is None

    def test_get_active_catalog_excludes_inactive(self, fx):
        active = fx.catalog()
        inactive = fx.catalog(active=False)
        ids = [c.id for c in LAB.get_active_catalog()]
        assert active.id in ids
        assert inactive.id not in ids

    def test_get_active_catalog_tenant_filter(self, fx):
        c = fx.catalog()
        ids = [x.id for x in LAB.get_active_catalog(tenant_id=g.tenant_id)]
        assert c.id in ids
        assert LAB.get_active_catalog(tenant_id=99999999) == []

    def test_get_active_catalog_sorted_by_sort_order(self, fx):
        fx.catalog(code='ZZZSORT', sort_order=10)
        fx.catalog(code='AAASORT', sort_order=1)
        entries = [c for c in LAB.get_active_catalog() if 'SORT' in c.code]
        orders = [(c.sort_order or 0, c.code) for c in entries]
        assert orders == sorted(orders)


# ---------------------------------------------------------------------------
# Module gate
# ---------------------------------------------------------------------------
class TestModuleGate:
    def test_lab_module_disabled_raises(self, fx, monkeypatch):
        from services.feature_gate_service import FeatureGateService
        from utils.exceptions import ModuleNotEnabledError

        monkeypatch.setattr(
            FeatureGateService, 'module_enabled', staticmethod(lambda _t, _m: False)
        )
        with pytest.raises(ModuleNotEnabledError):
            LAB.get_reagents()
