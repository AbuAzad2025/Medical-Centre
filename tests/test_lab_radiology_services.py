"""Tests for services.lab_service.LabService and services.radiology_service.RadiologyService.

Covers latent bugs fixed in this change:
  - LabService.log_action / RadiologyService.log_action (AuditTrail field mismatch)
  - LabService.create_results_from_form (missing NOT NULL patient_id/test_code on new rows)
  - RadiologyService.create_or_update_result (wrote to non-existent report_text/conclusion)
All DB work runs under ``rollback_db`` isolation.
"""
import types
import uuid

import pytest

from services.lab_service import LabService as LAB
from services.radiology_service import RadiologyService as RAD
from models.patient import Patient
from models.visit import Visit
from models.lab_test_catalog import LabTestCatalog
from models.lab_request import LabRequest, LabResult
from models.lab_reagent import LabReagent
from models.radiology_request import RadiologyRequest
from models.audit_trail import AuditTrail


@pytest.fixture
def fx(rollback_db):
    db = rollback_db

    def patient():
        p = Patient(first_name='ل', last_name='ر')
        db.session.add(p)
        db.session.commit()
        return p

    def visit(patient_id=None):
        pid = patient_id or patient().id
        v = Visit(patient_id=pid)
        db.session.add(v)
        db.session.commit()
        return v

    def catalog(code=None, active=True):
        code = code or 'C' + uuid.uuid4().hex[:6]
        c = LabTestCatalog(code=code, name_ar='تحليل', name_en='Test',
                           unit='mg', is_active=active)
        db.session.add(c)
        db.session.commit()
        return c

    def reagent(name=None, qty=5, minimum=10):
        r = LabReagent(name=(name or 'Reagent' + uuid.uuid4().hex[:4]),
                       stock_quantity=qty, minimum_stock=minimum)
        db.session.add(r)
        db.session.commit()
        return r

    return types.SimpleNamespace(db=db, patient=patient, visit=visit,
                                 catalog=catalog, reagent=reagent)


# ════════════════════════════ LabService ════════════════════════════

class TestLabCreateRequest:
    def test_no_test_ids(self, fx):
        ok, res = LAB.create_request(1, [])
        assert ok is False and 'error' in res

    def test_visit_not_found(self, fx):
        ok, res = LAB.create_request(99999999, [1])
        assert ok is False and res['error'] == 'Visit not found'

    def test_unknown_test_id_rolls_back(self, fx):
        v = fx.visit()
        ok, res = LAB.create_request(v.id, [99999998])
        assert ok is False and 'Unknown' in res['error']

    def test_success_creates_request_and_results(self, fx):
        v = fx.visit()
        c1, c2 = fx.catalog(), fx.catalog()
        ok, res = LAB.create_request(v.id, [c1.id, c2.id], notes='n')
        assert ok is True
        assert res['request_number'].startswith('LR-')
        results = LabResult.query.filter_by(request_id=res['lab_request_id']).all()
        assert len(results) == 2
        assert all(r.status == 'PENDING' for r in results)


class TestLabWorklistAndCounts:
    def test_get_worklist_invalid_status_defaults(self, fx):
        v = fx.visit()
        c = fx.catalog()
        LAB.create_request(v.id, [c.id])
        wl = LAB.get_worklist(status='NOPE')
        assert isinstance(wl, list)
        assert all(r.status == 'REQUESTED' for r in wl)

    def test_get_worklist_all(self, fx):
        assert isinstance(LAB.get_worklist(status='ALL'), list)

    def test_get_request_counts(self, fx):
        counts = LAB.get_request_counts()
        assert set(counts) == {'requested', 'in_progress', 'done_today'}

    def test_get_request_by_id_and_results(self, fx):
        v = fx.visit()
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id])
        rid = res['lab_request_id']
        assert LAB.get_request_by_id(rid).id == rid
        assert len(LAB.get_results_by_request(rid)) == 1

    def test_get_results_by_patient_empty(self, fx):
        p = fx.patient()
        assert LAB.get_results_by_patient(p.id) == []


class TestLabResultForm:
    def test_update_existing_result(self, fx):
        v = fx.visit()
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id])
        existing = LabResult.query.filter_by(request_id=res['lab_request_id']).first()
        req = LabRequest.query.get(res['lab_request_id'])
        created, errors = LAB.create_results_from_form(req, {
            'result_ids': [str(existing.id)],
            'test_names': ['T'], 'values': ['12'], 'units': ['mg'],
            'ranges': ['1-20'], 'statuses': ['COMPLETED'], 'notes_list': ['ok'],
        })
        assert errors == []
        assert created == [existing.id]
        assert LabResult.query.get(existing.id).value == '12'

    def test_create_new_result_sets_required_fields(self, fx):
        v = fx.visit()
        req = LabRequest(visit_id=v.id, patient_id=v.patient_id,
                         request_number='LR-x', status='REQUESTED')
        fx.db.session.add(req)
        fx.db.session.commit()
        created, errors = LAB.create_results_from_form(req, {
            'result_ids': [], 'test_names': ['Glucose'], 'values': ['90'],
            'units': ['mg'], 'ranges': [''], 'statuses': ['PENDING'], 'notes_list': [''],
        })
        assert errors == []
        new = LabResult.query.get(created[0])
        assert new.patient_id == v.patient_id
        assert new.test_code == 'Glucose'

    def test_validate_lab_results(self, fx):
        good = types.SimpleNamespace(test_name='X', value='1', unit='mg')
        no_name = types.SimpleNamespace(test_name='', value='', unit='')
        no_unit = types.SimpleNamespace(test_name='Y', value='5', unit='')
        errs = LAB.validate_lab_results([good, no_name, no_unit])
        assert any('required' in e for e in errs)
        assert len(errs) == 2

    def test_finalize_results(self, fx):
        v = fx.visit()
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id])
        assert LAB.finalize_results(res['lab_request_id']) is True
        req = LabRequest.query.get(res['lab_request_id'])
        assert req.status == 'DONE'
        assert all(r.status == 'COMPLETED' for r in
                   LabResult.query.filter_by(request_id=req.id).all())


class TestLabQualityAndReagents:
    def test_create_and_get_quality_entry(self, fx):
        entry = LAB.create_quality_entry({
            'test_code': 'QC1', 'measured_value': 5.0,
            'control_level': 'NORMAL', 'status': 'PASS',
        })
        assert entry is not None
        assert any(e.id == entry.id for e in LAB.get_quality_entries())

    def test_create_quality_entry_invalid_returns_none(self, fx):
        assert LAB.create_quality_entry({'test_code': 'QC2', 'measured_value': 1.0,
                                         'control_level': 'BAD', 'status': 'PASS'}) is None

    def test_reagents_listing_and_low_stock(self, fx):
        r = fx.reagent(qty=2, minimum=10)
        assert any(x.id == r.id for x in LAB.get_reagents())
        assert any(x.id == r.id for x in LAB.get_low_stock_reagents())
        assert any(x.id == r.id for x in LAB.get_low_stock_reagents(threshold=5))

    def test_update_reagent_quantity(self, fx):
        r = fx.reagent(qty=2)
        assert LAB.update_reagent_quantity(r.id, 50) is True
        assert float(LabReagent.query.get(r.id).stock_quantity) == 50.0
        assert LAB.update_reagent_quantity(99999999, 1) is False


class TestLabCatalogAndDashboard:
    def test_lookup_catalog_by_code(self, fx):
        c = fx.catalog(code='ABC123')
        assert LAB.lookup_catalog_by_code('ABC123').id == c.id
        assert LAB.lookup_catalog_by_code('NOPE') is None

    def test_get_active_catalog(self, fx):
        c = fx.catalog()
        fx.catalog(active=False)
        active = LAB.get_active_catalog()
        assert any(x.id == c.id for x in active)
        assert all(x.is_active for x in active)

    def test_dashboard_stats(self, fx):
        stats = LAB.get_dashboard_stats()
        assert set(stats) == {'today_requests', 'pending_requests', 'completed_today'}


class TestLabMisc:
    def test_log_action_persists(self, fx):
        p = fx.patient()
        LAB.log_action('result_finalized', 'details here', user_id=None)
        row = AuditTrail.query.filter_by(entity_type='lab_test').order_by(
            AuditTrail.id.desc()).first()
        assert row is not None
        assert 'result_finalized' in row.description

    def test_notify_results_ready_no_raise(self, fx):
        p = fx.patient()
        v = fx.visit(patient_id=p.id)
        c = fx.catalog()
        ok, res = LAB.create_request(v.id, [c.id])
        LAB.notify_results_ready(p.id, res['lab_request_id'])


# ════════════════════════════ RadiologyService ════════════════════════════

class TestRadCreateRequest:
    def test_visit_not_found(self, fx):
        ok, res = RAD.create_request(99999999)
        assert ok is False and res['error'] == 'Visit not found'

    def test_success(self, fx):
        v = fx.visit()
        ok, res = RAD.create_request(v.id, modality='ct', body_part=' chest ', notes='n')
        assert ok is True
        assert res['request_number'].startswith('RAD-')
        req = RadiologyRequest.query.get(res['radiology_request_id'])
        assert req.modality == 'CT'
        assert req.body_part == 'chest'


class TestRadWorklist:
    def _make(self, fx, status='REQUESTED'):
        v = fx.visit()
        ok, res = RAD.create_request(v.id)
        req = RadiologyRequest.query.get(res['radiology_request_id'])
        req.status = status
        fx.db.session.commit()
        return req

    def test_counts(self, fx):
        self._make(fx)
        counts = RAD.get_request_counts()
        assert counts['requested'] >= 1

    def test_worklist_status(self, fx):
        self._make(fx)
        assert all(r.status == 'REQUESTED' for r in RAD.get_worklist('REQUESTED'))

    def test_worklist_done_today(self, fx):
        assert isinstance(RAD.get_worklist('DONE_TODAY'), list)

    def test_get_request_by_id(self, fx):
        req = self._make(fx)
        assert RAD.get_request_by_id(req.id).id == req.id

    def test_results_for_request_none(self, fx):
        req = self._make(fx)
        assert RAD.get_results_for_request(req.id) is None

    def test_build_visit_map(self, fx):
        req = self._make(fx)
        vmap = RAD.build_visit_map([req])
        assert req.visit_id in vmap

    def test_build_visit_map_empty(self, fx):
        assert RAD.build_visit_map([]) == {}


class TestRadResults:
    def test_create_or_update_result_not_found(self, fx):
        assert RAD.create_or_update_result(99999999, 'report') is None

    def test_create_result_maps_to_findings(self, fx):
        v = fx.visit()
        ok, res = RAD.create_request(v.id)
        rid = res['radiology_request_id']
        result = RAD.create_or_update_result(rid, 'my findings', conclusion='my impression',
                                             is_critical=True)
        assert result is not None
        assert result.findings == 'my findings'
        assert result.impression == 'my impression'
        assert result.is_critical is True

    def test_create_or_update_result_updates_existing(self, fx):
        v = fx.visit()
        ok, res = RAD.create_request(v.id)
        rid = res['radiology_request_id']
        RAD.create_or_update_result(rid, 'first')
        again = RAD.create_or_update_result(rid, 'second')
        assert again.findings == 'second'

    def test_finalize_result(self, fx):
        v = fx.visit()
        ok, res = RAD.create_request(v.id)
        rid = res['radiology_request_id']
        RAD.create_or_update_result(rid, 'report')
        assert RAD.finalize_result(rid) is True
        assert RadiologyRequest.query.get(rid).status == 'DONE'

    def test_finalize_result_not_found(self, fx):
        assert RAD.finalize_result(99999999) is False

    def test_claim_request(self, fx):
        v = fx.visit()
        u = _make_user(fx.db)
        ok, res = RAD.create_request(v.id)
        rid = res['radiology_request_id']
        assert RAD.claim_request(rid, u.id) is True
        req = RadiologyRequest.query.get(rid)
        assert req.status == 'IN_PROGRESS'

    def test_claim_request_wrong_status(self, fx):
        v = fx.visit()
        u = _make_user(fx.db)
        ok, res = RAD.create_request(v.id)
        rid = res['radiology_request_id']
        RAD.claim_request(rid, u.id)
        assert RAD.claim_request(rid, u.id) is False

    def test_claim_request_not_found(self, fx):
        assert RAD.claim_request(99999999, 1) is False


class TestRadMisc:
    def test_log_action_persists(self, fx):
        RAD.log_action('report_approved', 'critical', user_id=None)
        row = AuditTrail.query.filter_by(entity_type='radiology_test').order_by(
            AuditTrail.id.desc()).first()
        assert row is not None and 'report_approved' in row.description

    def test_notify_complete_no_raise(self, fx):
        req = types.SimpleNamespace(requester=None, id=1, patient_id=1)
        RAD.notify_complete(req)

    def test_dashboard_stats(self, fx):
        stats = RAD.get_dashboard_stats()
        assert set(stats) == {'today_requests', 'pending', 'completed_today'}

    def test_save_uploaded_files(self, fx, tmp_path, monkeypatch):
        from flask import current_app
        monkeypatch.setitem(current_app.config, 'UPLOAD_FOLDER', str(tmp_path))

        class FakeFile:
            filename = 'scan.png'
            mimetype = 'image/png'

            def save(self, path):
                with open(path, 'wb') as fh:
                    fh.write(b'data')

        saved = RAD.save_uploaded_files([FakeFile(), None], result_id=7)
        assert len(saved) == 1
        assert saved[0].related_entity_id == 7


def _make_user(db):
    from models.user import User
    un = 'lr_' + uuid.uuid4().hex[:8]
    u = User(username=un, email=un + '@x.com', full_name='u', role='lab', is_active=True)
    u.set_password('p')
    db.session.add(u)
    db.session.commit()
    return u
