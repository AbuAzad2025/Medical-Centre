"""Agent8 — Telemedicine M1 rooms/lifecycle + LIS P1 import edge cases (no comments)."""

from datetime import UTC, date, datetime, timedelta

import jwt as pyjwt
import pytest
from sqlalchemy import select

from routes.telemedicine_consult import _sign_room_token
from services.lis_import_service import (
    LISImportError,
    import_results,
    map_rows,
    parse_csv,
)
from tests.tenant_context import ensure_test_user, login_test_client


def _mk_patient(db, tenant_id: int, nid: str):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name='سلمى',
        last_name='الاختبار',
        national_id=nid,
    )
    db.session.add(p)
    db.session.flush()
    return p


def _mk_visit(db, tenant_id: int, patient_id: int):
    from models.visit import Visit

    v = Visit(
        tenant_id=tenant_id,
        patient_id=patient_id,
        visit_type='REGULAR',
        status='OPEN',
        visit_date=date.today(),
        currency='ILS',
        payment_method='CASH',
        total_amount=0,
        paid_amount=0,
        is_inpatient=False,
        created_at=datetime.now(UTC),
    )
    db.session.add(v)
    db.session.flush()
    return v


def _mk_consultation(
    db, tenant_id: int, doctor_id: int, patient_id: int, visit_id: int, status: str
):
    from models.consultation import Consultation

    cons = Consultation(
        tenant_id=tenant_id,
        visit_id=visit_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        status=status,
        scheduled_at=datetime.now(UTC),
        created_by_id=doctor_id,
    )
    db.session.add(cons)
    db.session.commit()
    return cons


@pytest.mark.usefixtures('rollback_db')
class TestTelemedCreateConsultation:
    def test_doctor_creates_consultation_returns_room_url(self, app, client, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='a8_doc_c', role='doctor')
        login_test_client(client, u, test_tenant)
        p = _mk_patient(db, test_tenant.id, 'A8NATC00001')
        v = _mk_visit(db, test_tenant.id, p.id)

        resp = client.post('/telemedicine/consultations', json={'visit_id': v.id})
        assert resp.status_code == 201, resp.get_data(as_text=True)[:300]
        body = resp.get_json()
        assert body['success'] is True
        assert body['consultation']['status'] == 'SCHEDULED'
        assert f'/telemedicine/consult/{body["consultation"]["id"]}?token=' in body['room_url']

    def test_reception_cannot_create_consultation_403(self, client, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='a8_rec_c', role='reception')
        login_test_client(client, u, test_tenant)

        resp = client.post('/telemedicine/consultations', json={'visit_id': 1})
        assert resp.status_code == 403
        assert resp.get_json()['success'] is False

    def test_unknown_visit_404(self, client, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='a8_doc_u', role='doctor')
        login_test_client(client, u, test_tenant)

        resp = client.post('/telemedicine/consultations', json={'visit_id': 99999999})
        assert resp.status_code == 404

    def test_missing_visit_id_400(self, client, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='a8_doc_m', role='doctor')
        login_test_client(client, u, test_tenant)

        resp = client.post('/telemedicine/consultations', json={})
        assert resp.status_code == 400


@pytest.mark.usefixtures('rollback_db')
class TestTelemedRoomToken:
    def _setup(self, db, test_tenant, username):
        u = ensure_test_user(db, test_tenant, username=username, role='doctor')
        p = _mk_patient(db, test_tenant.id, f'{username.upper()}NAT001')
        v = _mk_visit(db, test_tenant.id, p.id)
        cons = _mk_consultation(db, test_tenant.id, u.id, p.id, v.id, 'SCHEDULED')
        return u, cons

    def test_room_page_requires_token(self, app, client, db, test_tenant):
        u, cons = self._setup(db, test_tenant, 'a8_rt_none')
        login_test_client(client, u, test_tenant)

        resp = client.get(f'/telemedicine/consult/{cons.id}')
        assert resp.status_code == 401, f'expected 401, got {resp.status_code}'
        body = resp.get_data(as_text=True)
        assert 'Traceback' not in body and 'sqlalchemy' not in body.lower()

    def test_expired_token_rejected_clean_401(self, app, client, db, test_tenant):
        u, cons = self._setup(db, test_tenant, 'a8_rt_exp')
        login_test_client(client, u, test_tenant)
        now = datetime.now(UTC)
        expired = pyjwt.encode(
            {
                'consultation_id': cons.id,
                'role': 'moderator',
                'name': u.full_name or u.username,
                'iat': int((now - timedelta(hours=3)).timestamp()),
                'exp': int((now - timedelta(hours=1)).timestamp()),
            },
            app.config['SECRET_KEY'],
            algorithm='HS256',
        )

        resp = client.get(f'/telemedicine/consult/{cons.id}?token={expired}')
        assert resp.status_code == 401, f'expected 401, got {resp.status_code}'
        body = resp.get_data(as_text=True)
        assert 'انتهت صلاحية رابط الغرفة' in body
        assert 'Traceback' not in body

    def test_tampered_token_rejected_clean_401(self, app, client, db, test_tenant):
        u, cons = self._setup(db, test_tenant, 'a8_rt_tam')
        login_test_client(client, u, test_tenant)
        good = _sign_room_token(cons.id, 'doctor', u.full_name or u.username)
        tampered = good[:-3] + ('AAA' if good[-3:] != 'AAA' else 'BBB')

        resp = client.get(f'/telemedicine/consult/{cons.id}?token={tampered}')
        assert resp.status_code == 401, f'expected 401, got {resp.status_code}'
        body = resp.get_data(as_text=True)
        assert 'رابط الغرفة غير صالح' in body
        assert 'Traceback' not in body

    def test_wrong_consultation_token_rejected_clean_401(self, app, client, db, test_tenant):
        u, cons = self._setup(db, test_tenant, 'a8_rt_wrong')
        login_test_client(client, u, test_tenant)
        other_token = _sign_room_token(cons.id + 987654, 'patient', 'مريض آخر')

        resp = client.get(f'/telemedicine/consult/{cons.id}?token={other_token}')
        assert resp.status_code == 401, f'expected 401, got {resp.status_code}'
        body = resp.get_data(as_text=True)
        assert 'هذا الرابط يخص غرفة أخرى' in body
        assert 'Traceback' not in body

    def test_valid_doctor_token_renders_room_page(self, app, client, db, test_tenant):
        u, cons = self._setup(db, test_tenant, 'a8_rt_ok')
        login_test_client(client, u, test_tenant)
        token = _sign_room_token(cons.id, 'doctor', u.full_name or u.username)

        resp = client.get(f'/telemedicine/consult/{cons.id}?token={token}')
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        body = resp.get_data(as_text=True)
        assert f'mc-{test_tenant.id}-c{cons.id}' in body
        assert 'غرفة الاستشارة' in body


@pytest.mark.usefixtures('rollback_db')
class TestTelemedLifecycleTransitions:
    def _setup(self, db, test_tenant, username, role='doctor'):
        u = ensure_test_user(db, test_tenant, username=username, role=role)
        p = _mk_patient(db, test_tenant.id, f'{username.upper()}NAT002')
        v = _mk_visit(db, test_tenant.id, p.id)
        cons = _mk_consultation(db, test_tenant.id, u.id, p.id, v.id, 'SCHEDULED')
        return u, cons

    def _login_and_get_cons(self, client, db, test_tenant, username, role='doctor'):
        u, cons = self._setup(db, test_tenant, username, role)
        login_test_client(client, u, test_tenant)
        return u, cons

    def test_end_from_scheduled_conflict_409(self, client, db, test_tenant):
        _u, cons = self._login_and_get_cons(client, db, test_tenant, 'a8_lc_e1')
        resp = client.post(f'/telemedicine/consult/{cons.id}/end')
        assert resp.status_code == 409, resp.get_data(as_text=True)[:200]
        body = resp.get_json()
        assert body['success'] is False
        assert 'SCHEDULED' in body['message'] and 'COMPLETED' in body['message']

    def test_start_from_completed_conflict_409(self, client, db, test_tenant):
        _u, cons = self._login_and_get_cons(client, db, test_tenant, 'a8_lc_s2')
        cons.status = 'COMPLETED'
        db.session.commit()

        resp = client.post(f'/telemedicine/consult/{cons.id}/start')
        assert resp.status_code == 409
        assert 'LIVE' in resp.get_json()['message']

    def test_cancel_from_live_conflict_409(self, client, db, test_tenant):
        _u, cons = self._login_and_get_cons(client, db, test_tenant, 'a8_lc_x3')
        cons.status = 'LIVE'
        db.session.commit()

        resp = client.post(f'/telemedicine/consult/{cons.id}/cancel')
        assert resp.status_code == 409
        body = resp.get_json()
        assert 'LIVE' in body['message'] and 'CANCELLED' in body['message']

    def test_no_show_from_completed_conflict_409(self, client, db, test_tenant):
        _u, cons = self._login_and_get_cons(client, db, test_tenant, 'a8_lc_n4')
        cons.status = 'NO_SHOW'
        db.session.commit()

        resp = client.post(f'/telemedicine/consult/{cons.id}/no-show')
        assert resp.status_code == 409

    def test_replayed_end_after_completion_conflict_409(self, client, db, test_tenant):
        _u, cons = self._login_and_get_cons(client, db, test_tenant, 'a8_lc_rp5')
        first = client.post(f'/telemedicine/consult/{cons.id}/start')
        assert first.status_code == 200
        second = client.post(f'/telemedicine/consult/{cons.id}/end', json={'notes': 'تم'})
        assert second.status_code == 200
        replay = client.post(f'/telemedicine/consult/{cons.id}/end', json={'notes': 'مرة ثانية'})
        assert replay.status_code == 409

    def test_happy_path_scheduled_live_completed_sets_timestamps(self, client, db, test_tenant):
        _u, cons = self._login_and_get_cons(client, db, test_tenant, 'a8_lc_hp6')

        live = client.post(f'/telemedicine/consult/{cons.id}/start')
        assert live.status_code == 200
        done = client.post(f'/telemedicine/consult/{cons.id}/end', json={'notes': 'خلاص'})
        assert done.status_code == 200

        from models.consultation import Consultation

        fresh = db.session.get(Consultation, cons.id)
        assert fresh.status == 'COMPLETED'
        assert fresh.started_at is not None
        assert fresh.ended_at is not None
        assert fresh.notes == 'خلاص'

    def test_non_doctor_transition_403(self, client, db, test_tenant):
        _u, cons = self._login_and_get_cons(client, db, test_tenant, 'a8_lc_r7', role='reception')
        resp = client.post(f'/telemedicine/consult/{cons.id}/start')
        assert resp.status_code == 403


@pytest.mark.usefixtures('rollback_db')
class TestLISParseCsvEdgeCases:
    def test_parses_utf8_bom(self):
        content = b'\xef\xbb\xbf' + b'test_code,value,request_id\nHGB,13.5,\n'
        out = parse_csv(content)
        assert out['errors'] == []
        assert len(out['rows']) == 1
        row = out['rows'][0]
        assert row['test_code'] == 'HGB'
        assert row['value'] == '13.5'
        assert row['request_id'] is None

    def test_sniffs_semicolon_delimiter(self):
        content = b'test_code;value;unit\nGLU;6.2;mg/dL\nCREA;1.1;\n'
        out = parse_csv(content)
        assert out['rows'][0]['test_code'] == 'GLU'
        assert out['rows'][0]['unit'] == 'mg/dL'
        assert out['rows'][1]['test_code'] == 'CREA'

    def test_header_case_and_spaces_normalized(self):
        content = b'Test Code, Value, Request ID\nK, 4.0, \n'
        out = parse_csv(content)
        assert out['rows'] == [
            {
                'line': 2,
                'request_id': None,
                'patient_national_id': '',
                'test_code': 'K',
                'value': '4.0',
                'unit': None,
                'performed_at': None,
            }
        ]

    def test_missing_columns_error_code_names_them(self):
        with pytest.raises(LISImportError) as ei:
            parse_csv(b'patient_id,test_name\n7,HGB\n')
        assert str(ei.value) == 'missing_columns:test_code,value'

        with pytest.raises(LISImportError) as ei2:
            parse_csv(b'test_code,value_extra\nHGB,x\n')
        assert str(ei2.value) == 'missing_columns:value'

    def test_blank_file_raises_empty_file(self):
        for blob in (b'', b'\n', b'   \r\n  \n'):
            with pytest.raises(LISImportError) as ei:
                parse_csv(blob)
            assert str(ei.value) == 'empty_file'

    def test_malformed_rows_collected_not_fatal(self):
        content = b'test_code,value\n,\nHGB,\nWBC,11.2\n'
        out = parse_csv(content)
        assert [r['test_code'] for r in out['rows']] == ['WBC']
        assert [e['error'] for e in out['errors']] == ['missing_required_field'] * 2
        assert out['errors'][0]['line'] == 2


@pytest.mark.usefixtures('rollback_db')
class TestLISMappingAndImport:
    def _catalog(self, db, tenant_id: int, code: str, *, hi=None, lo=None):
        from models.lab_test_catalog import LabTestCatalog

        cat = LabTestCatalog(
            tenant_id=tenant_id,
            code=code,
            name_ar=f'فحص {code}',
            unit='g/dL',
            default_reference_range='12-16',
            critical_low=lo,
            critical_high=hi,
        )
        db.session.add(cat)
        db.session.flush()
        return cat

    def _lab_request(self, db, tenant_id: int, nid: str):
        from models.lab_request import LabRequest

        p = _mk_patient(db, tenant_id, nid)
        req = LabRequest(tenant_id=tenant_id, patient_id=p.id, status='REQUESTED')
        db.session.add(req)
        db.session.flush()
        return req

    def _row(self, rid, code, value, catalog=None):
        r = {
            'line': 2,
            'request_id': rid,
            'patient_national_id': '',
            'test_code': code,
            'value': value,
            'unit': None,
            'performed_at': None,
        }
        if catalog:
            r['catalog'] = {
                'id': catalog.id,
                'name_ar': catalog.name_ar,
                'unit': catalog.unit,
                'reference_range': catalog.default_reference_range,
                'critical_low': catalog.critical_low,
                'critical_high': catalog.critical_high,
            }
        return r

    def test_map_rows_unmatched_go_to_unknown_queue(self, app, db, test_tenant):
        cat = self._catalog(db, test_tenant.id, 'CBC')
        rows = [self._row(None, 'CBC', '12'), self._row(None, 'XYZ_UNKNOWN', '5')]

        mapping = map_rows(rows)

        assert [m['test_code'] for m in mapping['matched']] == ['CBC']
        assert mapping['matched'][0]['catalog']['id'] == cat.id
        assert len(mapping['unmatched']) == 1
        assert mapping['unmatched'][0]['reason'] == 'unknown_test_code'
        assert mapping['unmatched'][0]['test_code'] == 'XYZ_UNKNOWN'

    def test_import_dedup_second_run_skipped_as_duplicate(self, app, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='a8_lis_dup', role='lab_tech')
        req = self._lab_request(db, test_tenant.id, 'A8LISDUP0001')
        cat = self._catalog(db, test_tenant.id, 'HBA1C')
        rows = [self._row(req.id, 'HBA1C', '7.4', cat)]

        first = import_results(rows, performed_by=u.id)
        assert first['imported_count'] == 1
        assert first['duplicates_count'] == 0
        assert first['skipped'] == []

        second = import_results(rows, performed_by=u.id)
        assert second['imported_count'] == 0
        assert second['duplicates_count'] == 1

        from models.lab_request import LabResult

        count = (
            db.session.execute(select(LabResult).where(LabResult.request_id == req.id))
            .scalars()
            .all()
        )
        assert len(count) == 1

    def test_critical_high_breach_flags_is_critical(self, app, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='a8_lis_crit', role='lab_tech')
        req = self._lab_request(db, test_tenant.id, 'A8LISCRI0001')
        cat = self._catalog(db, test_tenant.id, 'TROP', hi='10')
        ok_cat = self._catalog(db, test_tenant.id, 'ALB')

        rows = [
            self._row(req.id, 'TROP', '15.5', cat),
            self._row(req.id, 'ALB', '4.0', ok_cat),
        ]
        result = import_results(rows, performed_by=u.id)
        assert result['imported_count'] == 2

        from models.lab_request import LabResult

        results = {
            r.test_code: r
            for r in db.session.execute(select(LabResult).where(LabResult.request_id == req.id))
            .scalars()
            .all()
        }
        assert results['TROP'].is_critical is True
        assert results['TROP'].status == 'READY'
        assert results['ALB'].is_critical is False

    def test_missing_request_id_row_skipped_never_inserted(self, app, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='a8_lis_norid', role='lab_tech')
        rows = [
            self._row(None, 'CBC', '12'),
            {'line': 3, 'request_id': '', 'test_code': 'PLT', 'value': '300'},
        ]
        result = import_results(rows, performed_by=u.id)

        assert result['imported_count'] == 0
        assert len(result['skipped']) == 2
        assert all(s['reason'] == 'missing_request_id' for s in result['skipped'])

        from models.lab_request import LabResult

        leftovers = db.session.execute(select(LabResult)).scalars().all()
        assert leftovers == []

    def test_non_numeric_value_never_flagged_critical(self, app, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='a8_lis_txt', role='lab_tech')
        req = self._lab_request(db, test_tenant.id, 'A8LISTXT0001')
        cat = self._catalog(db, test_tenant.id, 'BLOOD_T', hi='10')
        rows = [self._row(req.id, 'BLOOD_T', ' inconclusive ', cat)]

        result = import_results(rows, performed_by=u.id)
        assert result['imported_count'] == 1

        from models.lab_request import LabResult

        lr = (
            db.session.execute(select(LabResult).where(LabResult.request_id == req.id))
            .scalars()
            .first()
        )
        assert lr.is_critical is False
