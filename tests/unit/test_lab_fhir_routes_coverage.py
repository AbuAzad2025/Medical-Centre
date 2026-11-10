"""
Branch-by-branch coverage for routes/lab/fhir.py.

Real HTTP tests through the Flask test client against the migrated test schema.
Every endpoint in the module is exercised: the success paths, the 400/403/404
contracts, and the 500 fallbacks (forced with monkeypatched failure points).
Writes go through ``rollback_db`` so the session-scoped test database stays
pristine.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


def _login(client, db, tenant, username, role, password='ValidPass123!'):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, tenant, username=username, role=role, password=password)
    login_test_client(client, user, tenant, password)
    return user


def _make_patient(db, tenant, **kw):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant.id,
        first_name=kw.get('first_name', 'Test'),
        last_name=kw.get('last_name', f'Patient{uuid.uuid4().hex[:6]}'),
        gender=kw.get('gender', 'F'),
        phone=kw.get('phone', f'059{uuid.uuid4().int % 10**7:07d}'),
        national_id=kw.get('national_id', f'NAT-{uuid.uuid4().hex[:8]}'),
    )
    db.session.add(p)
    db.session.commit()
    return p


def _make_visit(db, tenant, patient_id, doctor_id, **kw):
    from models.visit import Visit

    visit = Visit(
        tenant_id=tenant.id,
        patient_id=patient_id,
        doctor_id=doctor_id,
        status=kw.get('status', 'OPEN'),
        payment_status=kw.get('payment_status', 'PENDING'),
        total_amount=kw.get('total_amount', 0),
        paid_amount=kw.get('paid_amount', 0),
        visit_type=kw.get('visit_type', 'REGULAR'),
    )
    db.session.add(visit)
    db.session.commit()
    return visit


def _make_lab_request(db, tenant, patient_id, **kw):
    from models.lab_request import LabRequest

    req = LabRequest(
        tenant_id=tenant.id,
        visit_id=kw.get('visit_id'),
        patient_id=patient_id,
        requested_by=kw.get('requested_by'),
        status=kw.get('status', 'REQUESTED'),
        request_number=kw.get('request_number', f'LAB-T-{uuid.uuid4().hex[:10]}'),
        notes=kw.get('notes'),
    )
    db.session.add(req)
    db.session.commit()
    return req


def _make_lab_result(db, tenant, request_id, patient_id, **kw):
    from models.lab_request import LabResult

    res = LabResult(
        tenant_id=tenant.id,
        request_id=request_id,
        patient_id=patient_id,
        performed_by=kw.get('performed_by'),
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


def _boom(*_args, **_kwargs):
    raise RuntimeError('forced failure')


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def first(self):
        return self._value


class _TwoStepSession:
    """Minimal session stand-in: first execute() yields a result, second none."""

    def __init__(self, first_value, second_value):
        self._values = [first_value, second_value]

    def execute(self, *_args, **_kwargs):
        return _ScalarResult(self._values.pop(0))


class _FakeDb:
    def __init__(self, session):
        self.session = session


def _patch_request_lookup(monkeypatch, result_row, request_row):
    """Make the export routes see ``result_row`` but ``request_row`` (None)."""
    monkeypatch.setattr(
        'routes.lab.fhir.db',
        _FakeDb(_TwoStepSession(result_row, request_row)),
    )


# ---------------------------------------------------------------------------
# /lab/api/worklist
# ---------------------------------------------------------------------------
class TestWorklist:
    def test_worklist_unauthenticated_redirects(self, app, client, rollback_db):
        resp = client.get('/lab/api/worklist')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_worklist_returns_created_request(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('wl_ok'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)

        resp = client.get('/lab/api/worklist')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        match = next((r for r in data['requests'] if r['id'] == req.id), None)
        assert match is not None
        assert match['patient_id'] == patient.id
        assert match['request_number'] == req.request_number

    def test_worklist_filters_by_visit_and_status(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('wl_filter'), 'lab')
        patient = _make_patient(db, test_tenant)
        visit = _make_visit(db, test_tenant, patient.id, lab.id)
        wanted = _make_lab_request(
            db, test_tenant, patient.id, requested_by=lab.id, visit_id=visit.id, status='DONE'
        )
        _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id, status='REQUESTED')

        resp = client.get(f'/lab/api/worklist?visit_id={visit.id}&status=DONE')
        assert resp.status_code == 200
        data = resp.get_json()
        assert [r['id'] for r in data['requests']] == [wanted.id]

    def test_worklist_non_int_visit_id_is_ignored(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('wl_badid'), 'lab')
        resp = client.get('/lab/api/worklist?visit_id=not-a-number')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_worklist_empty_result_set(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('wl_empty'), 'lab')
        resp = client.get('/lab/api/worklist?visit_id=999999999')
        assert resp.status_code == 200
        assert resp.get_json()['requests'] == []

    def test_worklist_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('wl_403'), 'reception')
        resp = client.get('/lab/api/worklist')
        assert resp.status_code == 403

    def test_worklist_500_on_query_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('wl_500'), 'lab')

        class _BoomLabRequest:
            @property
            def query(self):
                raise RuntimeError('forced failure')

        monkeypatch.setattr('routes.lab.fhir.LabRequest', _BoomLabRequest)
        resp = client.get('/lab/api/worklist')
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


# ---------------------------------------------------------------------------
# /lab/api/fhir/servicerequest
# ---------------------------------------------------------------------------
class TestServiceRequest:
    def test_missing_patient_id_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('sr_400a'), 'lab')
        resp = client.post('/lab/api/fhir/servicerequest', json={'visit_id': 1})
        assert resp.status_code == 400
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_missing_visit_id_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('sr_400b'), 'doctor')
        resp = client.post('/lab/api/fhir/servicerequest', json={'patient_id': 1})
        assert resp.status_code == 400
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_empty_json_body_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('sr_400c'), 'lab')
        resp = client.post('/lab/api/fhir/servicerequest', json={})
        assert resp.status_code == 400

    def test_non_json_body_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('sr_400d'), 'lab')
        resp = client.post('/lab/api/fhir/servicerequest', data='not json')
        assert resp.status_code == 400

    def test_creates_request_with_mixed_test_rows(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabRequest, LabResult

        lab = _login(client, db, test_tenant, _uniq('sr_ok'), 'lab')
        patient = _make_patient(db, test_tenant)
        visit = _make_visit(db, test_tenant, patient.id, lab.id)

        resp = client.post(
            '/lab/api/fhir/servicerequest',
            json={
                'patient_id': patient.id,
                'visit_id': visit.id,
                'requester_id': lab.id,
                'notes': 'fasting sample',
                'tests': [
                    {'test_code': 'HB', 'test_name': 'Hemoglobin'},
                    {'test_code': 'CRP'},  # code only -> name falls back to code
                    {'test_name': 'OnlyName'},  # name only -> test_code falls back to name
                    {'test_code': '   ', 'test_name': ''},  # blank -> skipped
                    {'test_code': '', 'test_name': ''},  # empty -> skipped
                    'not-a-dict',  # non-dict -> skipped
                ],
            },
        )
        assert resp.status_code == 201
        resource = resp.get_json()
        assert resource['resourceType'] == 'ServiceRequest'
        assert resource['status'] == 'active'
        assert resource['subject']['reference'] == f'Patient/{patient.id}'
        assert resource['encounter']['reference'] == f'Encounter/{visit.id}'

        req = db.session.get(LabRequest, int(resource['id']))
        assert req is not None
        assert req.requested_by == lab.id
        assert req.notes == 'fasting sample'
        assert req.request_number.startswith('LAB-')

        results = (
            db.session.execute(
                select(LabResult).filter(LabResult.request_id == req.id).order_by(LabResult.id)
            )
            .scalars()
            .all()
        )
        by_name = {r.test_name: r for r in results}
        assert set(by_name) == {'Hemoglobin', 'CRP', 'OnlyName'}
        assert by_name['CRP'].test_code == 'CRP'
        assert by_name['OnlyName'].test_code == 'OnlyName'
        assert all(r.status == 'PENDING' for r in results)

    def test_requester_id_defaults_to_current_user(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabRequest

        lab = _login(client, db, test_tenant, _uniq('sr_defreq'), 'lab')
        patient = _make_patient(db, test_tenant)
        visit = _make_visit(db, test_tenant, patient.id, lab.id)

        resp = client.post(
            '/lab/api/fhir/servicerequest',
            json={'patient_id': patient.id, 'visit_id': visit.id},
        )
        assert resp.status_code == 201
        req = db.session.get(LabRequest, int(resp.get_json()['id']))
        assert req.requested_by == lab.id

    def test_service_request_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('sr_403'), 'reception')
        resp = client.post('/lab/api/fhir/servicerequest', json={'patient_id': 1, 'visit_id': 1})
        assert resp.status_code == 403

    def test_service_request_500_on_barcode_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        lab = _login(client, db, test_tenant, _uniq('sr_500'), 'lab')
        patient = _make_patient(db, test_tenant)
        visit = _make_visit(db, test_tenant, patient.id, lab.id)
        monkeypatch.setattr('services.barcode_service.setup_barcode_for_lab_request', _boom)
        resp = client.post(
            '/lab/api/fhir/servicerequest',
            json={'patient_id': patient.id, 'visit_id': visit.id},
        )
        assert resp.status_code == 500
        assert resp.get_json()['resourceType'] == 'OperationOutcome'


# ---------------------------------------------------------------------------
# /lab/api/fhir/observation (import)
# ---------------------------------------------------------------------------
class TestObservationImport:
    def test_missing_request_id_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('oi_400a'), 'lab')
        resp = client.post('/lab/api/fhir/observation', json={'patient_id': 1})
        assert resp.status_code == 400
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_missing_patient_id_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('oi_400b'), 'doctor')
        resp = client.post('/lab/api/fhir/observation', json={'request_id': 1})
        assert resp.status_code == 400

    def test_unknown_request_returns_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('oi_404'), 'lab')
        resp = client.post(
            '/lab/api/fhir/observation',
            json={'request_id': 999999999, 'patient_id': 1, 'test_code': 'HB'},
        )
        assert resp.status_code == 404
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_non_integer_request_id_returns_500(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('oi_500a'), 'lab')
        resp = client.post(
            '/lab/api/fhir/observation',
            json={'request_id': 'not-an-int', 'patient_id': 1, 'test_code': 'HB'},
        )
        assert resp.status_code == 500
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_creates_new_result_with_code_only(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabResult

        lab = _login(client, db, test_tenant, _uniq('oi_new'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)

        resp = client.post(
            '/lab/api/fhir/observation',
            json={
                'request_id': req.id,
                'patient_id': patient.id,
                'test_code': 'GL',  # no test_name -> falls back to test_code
                'value': '5.2',
                'unit': 'mmol/L',
                'reference_range': '3.9-5.5',
            },
        )
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Observation'
        assert resource['status'] == 'final'

        res = db.session.get(LabResult, int(resource['id']))
        assert res.test_name == 'GL'
        assert res.test_code == 'GL'
        assert res.value == '5.2'
        assert res.status == 'VALIDATED'
        assert res.performed_by == lab.id

    def test_creates_result_with_no_code_and_no_name(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_request import LabResult

        lab = _login(client, db, test_tenant, _uniq('oi_none'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)

        resp = client.post(
            '/lab/api/fhir/observation',
            json={'request_id': req.id, 'patient_id': patient.id, 'value': '7'},
        )
        assert resp.status_code == 200
        res = db.session.get(LabResult, int(resp.get_json()['id']))
        assert res.test_code == 'Test'
        assert res.test_name == 'Test'

    def test_no_test_code_skips_lookup_and_creates(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabResult

        lab = _login(client, db, test_tenant, _uniq('oi_ntc'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        _make_lab_result(
            db, test_tenant, req.id, patient.id, test_code='HB', test_name='Hemoglobin'
        )

        resp = client.post(
            '/lab/api/fhir/observation',
            json={
                'request_id': req.id,
                'patient_id': patient.id,
                'test_code': '',
                'test_name': 'Ferritin',
                'value': '80',
            },
        )
        assert resp.status_code == 200
        res = db.session.get(LabResult, int(resp.get_json()['id']))
        assert res.test_name == 'Ferritin'
        assert res.test_code == 'Ferritin'

    def test_creates_unmatched_code_as_new_result(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabResult

        lab = _login(client, db, test_tenant, _uniq('oi_unmatched'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        existing = _make_lab_result(
            db, test_tenant, req.id, patient.id, test_code='HB', test_name='Hemoglobin'
        )

        resp = client.post(
            '/lab/api/fhir/observation',
            json={
                'request_id': req.id,
                'patient_id': patient.id,
                'test_code': 'GL',
                'value': '5.5',
            },
        )
        assert resp.status_code == 200
        res = db.session.get(LabResult, int(resp.get_json()['id']))
        assert res.id != existing.id
        assert res.test_code == 'GL'

    def test_updates_existing_result(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabResult

        lab = _login(client, db, test_tenant, _uniq('oi_upd'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        existing = _make_lab_result(
            db, test_tenant, req.id, patient.id, test_code='HB', test_name='Hemoglobin', value=None
        )

        resp = client.post(
            '/lab/api/fhir/observation',
            json={
                'request_id': req.id,
                'patient_id': patient.id,
                'test_code': 'HB',
                'value': '14.1',
                'unit': 'g/dL',
                'reference_range': '12-16',
            },
        )
        assert resp.status_code == 200
        assert int(resp.get_json()['id']) == existing.id
        db.session.expire_all()
        res = db.session.get(LabResult, existing.id)
        assert res.value == '14.1'
        assert res.unit == 'g/dL'
        assert res.reference_range == '12-16'
        assert res.status == 'VALIDATED'

    def test_observation_import_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('oi_403'), 'reception')
        resp = client.post('/lab/api/fhir/observation', json={'request_id': 1, 'patient_id': 1})
        assert resp.status_code == 403

    def test_observation_import_500_on_workflow_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        lab = _login(client, db, test_tenant, _uniq('oi_500b'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        monkeypatch.setattr('routes.lab.fhir._log_lab_workflow', _boom)

        resp = client.post(
            '/lab/api/fhir/observation',
            json={
                'request_id': req.id,
                'patient_id': patient.id,
                'test_code': 'HB',
                'value': '13.0',
            },
        )
        assert resp.status_code == 500
        assert resp.get_json()['resourceType'] == 'OperationOutcome'


# ---------------------------------------------------------------------------
# /lab/api/hl7/import
# ---------------------------------------------------------------------------
class TestHl7Import:
    def test_missing_patient_id_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('hl_400a'), 'lab')
        resp = client.post('/lab/api/hl7/import', json={'visit_id': 1})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_missing_visit_id_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('hl_400b'), 'lab')
        resp = client.post('/lab/api/hl7/import', json={'patient_id': 1})
        assert resp.status_code == 400

    def test_empty_json_returns_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('hl_400c'), 'lab')
        resp = client.post('/lab/api/hl7/import', json={})
        assert resp.status_code == 400

    def test_import_mixed_test_rows(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabRequest, LabResult

        lab = _login(client, db, test_tenant, _uniq('hl_ok'), 'lab')
        patient = _make_patient(db, test_tenant)
        visit = _make_visit(db, test_tenant, patient.id, lab.id)

        resp = client.post(
            '/lab/api/hl7/import',
            json={
                'patient_id': patient.id,
                'visit_id': visit.id,
                'notes': 'hl7 batch',
                'tests': [
                    {
                        'test_code': 'GL',
                        'test_name': 'Glucose',
                        'value': '5.2',
                        'unit': 'mmol/L',
                        'reference_range': '3.9-5.5',
                    },
                    {'test_code': 'HB'},  # name falls back to code
                    {'test_name': 'OnlyName'},  # code falls back to name
                    {'test_code': '', 'test_name': ''},  # both empty -> 'Test'
                    'junk-row',  # non-dict -> skipped
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True

        req = db.session.get(LabRequest, data['request_id'])
        assert req is not None
        assert req.request_number.startswith('HL7-')
        assert req.notes == 'hl7 batch'
        assert req.requested_by == lab.id

        results = (
            db.session.execute(
                select(LabResult).filter(LabResult.request_id == req.id).order_by(LabResult.id)
            )
            .scalars()
            .all()
        )
        by_name = {r.test_name: r for r in results}
        assert set(by_name) == {'Glucose', 'HB', 'OnlyName', 'Test'}
        assert by_name['Glucose'].value == '5.2'
        assert by_name['Glucose'].unit == 'mmol/L'
        assert by_name['Glucose'].reference_range == '3.9-5.5'
        assert by_name['HB'].test_code == 'HB'
        assert by_name['OnlyName'].test_code == 'OnlyName'
        assert by_name['Test'].test_code == 'Test'
        assert all(r.status == 'PENDING' for r in results)

    def test_hl7_import_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('hl_403'), 'reception')
        resp = client.post('/lab/api/hl7/import', json={'patient_id': 1, 'visit_id': 1})
        assert resp.status_code == 403

    def test_hl7_import_500_on_barcode_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        lab = _login(client, db, test_tenant, _uniq('hl_500'), 'lab')
        patient = _make_patient(db, test_tenant)
        visit = _make_visit(db, test_tenant, patient.id, lab.id)
        monkeypatch.setattr('services.barcode_service.setup_barcode_for_lab_request', _boom)
        resp = client.post(
            '/lab/api/hl7/import',
            json={'patient_id': patient.id, 'visit_id': visit.id},
        )
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


# ---------------------------------------------------------------------------
# /lab/api/fhir/observation/lab/<result_id> (export)
# ---------------------------------------------------------------------------
class TestObservationExport:
    def _seed(self, db, tenant, lab, **result_kw):
        patient = _make_patient(db, tenant)
        visit = _make_visit(db, tenant, patient.id, lab.id)
        req = _make_lab_request(db, tenant, patient.id, requested_by=lab.id, visit_id=visit.id)
        res = _make_lab_result(db, tenant, req.id, patient.id, **result_kw)
        return patient, visit, req, res

    def test_unknown_result_returns_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('oe_404'), 'lab')
        resp = client.get('/lab/api/fhir/observation/lab/999999999')
        assert resp.status_code == 404
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_numeric_value_exports_as_value_quantity(
        self, app, client, db, test_tenant, rollback_db
    ):
        lab = _login(client, db, test_tenant, _uniq('oe_num'), 'lab')
        _patient, visit, _req, res = self._seed(
            db,
            test_tenant,
            lab,
            test_code='HB',
            test_name='Hemoglobin',
            value='13.2',
            unit='g/dL',
            reference_range='12-16',
            status='VALIDATED',
            notes='within range',
            performed_by=lab.id,
        )
        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Observation'
        assert resource['status'] == 'final'
        assert resource['valueQuantity'] == {'value': 13.2, 'unit': 'g/dL'}
        assert resource['encounter']['reference'] == f'Encounter/{visit.id}'
        assert resource['referenceRange'] == [{'text': '12-16'}]
        assert resource['performer'] == [{'reference': f'Practitioner/{lab.id}'}]
        assert resource['note'] == [{'text': 'within range'}]
        assert resource['code']['coding'][0]['code'] == 'HB'
        assert resource['code']['text'] == 'Hemoglobin'
        assert resource['effectiveDateTime']

    def test_non_numeric_value_exports_as_value_string(
        self, app, client, db, test_tenant, rollback_db
    ):
        lab = _login(client, db, test_tenant, _uniq('oe_str'), 'lab')
        _patient, _visit, _req, res = self._seed(
            db, test_tenant, lab, value='POSITIVE', status='READY', performed_by=None
        )
        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['valueString'] == 'POSITIVE'
        assert 'valueQuantity' not in resource
        assert resource['status'] == 'final'  # READY maps to final
        assert 'performer' not in resource

    def test_null_value_exports_as_empty_value_string(
        self, app, client, db, test_tenant, rollback_db
    ):
        lab = _login(client, db, test_tenant, _uniq('oe_nullv'), 'lab')
        _patient, _visit, _req, res = self._seed(db, test_tenant, lab, value=None)
        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        assert resp.get_json()['valueString'] == ''

    def test_pending_status_maps_to_preliminary(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('oe_pend'), 'lab')
        _patient, _visit, _req, res = self._seed(db, test_tenant, lab, status='PENDING')
        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'preliminary'

    def test_unmapped_status_maps_to_unknown(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('oe_unk'), 'lab')
        _patient, _visit, _req, res = self._seed(db, test_tenant, lab, status='WEIRD')
        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'unknown'

    def test_minimal_result_omits_optional_blocks(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('oe_min'), 'lab')
        _patient, _visit, req, res = self._seed(
            db,
            test_tenant,
            lab,
            value='1.5',
            status='VALIDATED',
            reference_range=None,
            performed_by=None,
            notes=None,
        )
        # LabRequest without a visit -> no Encounter reference in the resource.
        req.visit_id = None
        db.session.commit()

        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['referenceRange'] == []
        assert resource['note'] == []
        assert 'performer' not in resource
        assert 'encounter' not in resource

    def test_missing_parent_request_omits_encounter(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        lab = _login(client, db, test_tenant, _uniq('oe_noreq'), 'lab')
        _patient, _visit, _req, res = self._seed(db, test_tenant, lab, status='VALIDATED')
        _patch_request_lookup(monkeypatch, res, None)

        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        assert 'encounter' not in resp.get_json()

    def test_export_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('oe_403'), 'reception')
        resp = client.get('/lab/api/fhir/observation/lab/1')
        assert resp.status_code == 403

    def test_export_500_on_query_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('oe_500'), 'lab')
        monkeypatch.setattr('routes.lab.fhir.select', _boom)
        resp = client.get('/lab/api/fhir/observation/lab/1')
        assert resp.status_code == 500
        assert resp.get_json()['resourceType'] == 'OperationOutcome'


# ---------------------------------------------------------------------------
# /lab/api/fhir/diagnosticreport/lab/<result_id> (export)
# ---------------------------------------------------------------------------
class TestDiagnosticReportExport:
    def _seed(self, db, tenant, lab, **result_kw):
        patient = _make_patient(db, tenant)
        visit = _make_visit(db, tenant, patient.id, lab.id)
        req = _make_lab_request(db, tenant, patient.id, requested_by=lab.id, visit_id=visit.id)
        res = _make_lab_result(db, tenant, req.id, patient.id, **result_kw)
        return patient, visit, req, res

    def test_unknown_result_returns_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dr_404'), 'lab')
        resp = client.get('/lab/api/fhir/diagnosticreport/lab/999999999')
        assert resp.status_code == 404
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_full_report(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('dr_full'), 'lab')
        patient, visit, _req, res = self._seed(
            db,
            test_tenant,
            lab,
            test_code='HB',
            test_name='Hemoglobin',
            value='15.0',
            status='VALIDATED',
            notes='normal',
            performed_by=lab.id,
        )
        resp = client.get(f'/lab/api/fhir/diagnosticreport/lab/{res.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'DiagnosticReport'
        assert resource['status'] == 'final'
        assert resource['category'][0]['coding'][0]['code'] == 'LAB'
        assert resource['code']['coding'][0]['code'] == 'HB'
        assert resource['code']['text'] == 'Hemoglobin'
        assert resource['subject']['reference'] == f'Patient/{patient.id}'
        assert resource['encounter']['reference'] == f'Encounter/{visit.id}'
        assert resource['result'] == [{'reference': f'Observation/{res.id}'}]
        assert resource['conclusion'] == 'normal'
        assert resource['performer'] == [{'reference': f'Practitioner/{lab.id}'}]
        assert resource['effectiveDateTime']
        assert resource['issued']

    def test_pending_status_maps_to_preliminary(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('dr_pend'), 'lab')
        _patient, _visit, _req, res = self._seed(db, test_tenant, lab, status='PENDING')
        resp = client.get(f'/lab/api/fhir/diagnosticreport/lab/{res.id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'preliminary'

    def test_ready_status_maps_to_final(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('dr_ready'), 'lab')
        _patient, _visit, _req, res = self._seed(db, test_tenant, lab, status='READY')
        resp = client.get(f'/lab/api/fhir/diagnosticreport/lab/{res.id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'final'

    def test_unmapped_status_maps_to_unknown(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('dr_unk'), 'lab')
        _patient, _visit, _req, res = self._seed(db, test_tenant, lab, status='WEIRD')
        resp = client.get(f'/lab/api/fhir/diagnosticreport/lab/{res.id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'unknown'

    def test_minimal_report_omits_optional_blocks(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('dr_min'), 'lab')
        _patient, _visit, req, res = self._seed(
            db, test_tenant, lab, status='VALIDATED', notes=None, performed_by=None
        )
        req.visit_id = None
        db.session.commit()

        resp = client.get(f'/lab/api/fhir/diagnosticreport/lab/{res.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['conclusion'] == ''
        assert 'performer' not in resource
        assert 'encounter' not in resource

    def test_missing_parent_request_omits_encounter(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        lab = _login(client, db, test_tenant, _uniq('dr_noreq'), 'lab')
        _patient, _visit, _req, res = self._seed(db, test_tenant, lab, status='VALIDATED')
        _patch_request_lookup(monkeypatch, res, None)

        resp = client.get(f'/lab/api/fhir/diagnosticreport/lab/{res.id}')
        assert resp.status_code == 200
        assert 'encounter' not in resp.get_json()

    def test_report_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dr_403'), 'reception')
        resp = client.get('/lab/api/fhir/diagnosticreport/lab/1')
        assert resp.status_code == 403

    def test_report_500_on_query_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('dr_500'), 'lab')
        monkeypatch.setattr('routes.lab.fhir.select', _boom)
        resp = client.get('/lab/api/fhir/diagnosticreport/lab/1')
        assert resp.status_code == 500
        assert resp.get_json()['resourceType'] == 'OperationOutcome'
