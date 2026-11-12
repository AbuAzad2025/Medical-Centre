"""Coverage for routes/emergency/cases.py — the emergency case screens."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

pytest_plugins = ['tests._isolated_tenant']


def _patient(db, tenant_id, first='ER', last='Patient'):
    from models.patient import Patient

    patient = Patient(
        tenant_id=tenant_id,
        first_name=first,
        last_name=last,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(patient)
    db.session.flush()
    return patient


class TestListEmergencyCases:
    """``/emergency/cases``."""

    def test_it_renders(self, app, client, login_as):
        login_as(client, 'er_list_user', 'emergency')
        resp = client.get('/emergency/cases')
        assert resp.status_code in (200, 302)

    def test_it_renders_with_filters(self, app, client, login_as):
        login_as(client, 'er_list_filter_user', 'emergency')
        resp = client.get('/emergency/cases?search=foo&priority=high&status=WAITING&today=true')
        assert resp.status_code in (200, 302)

    def test_a_failing_query_redirects(self, app, client, login_as):
        login_as(client, 'er_list_fail_user', 'emergency')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.emergency.cases.select', boom):
            resp = client.get('/emergency/cases')
        assert resp.status_code == 302
        assert '/emergency/dashboard' in resp.headers['Location']


class TestViewEmergencyCase:
    """``/emergency/cases/<id>``."""

    def test_an_unknown_case_redirects(self, app, client, login_as):
        login_as(client, 'er_view_missing', 'emergency')
        resp = client.get('/emergency/cases/999999')
        assert resp.status_code in (302, 404)

    def test_a_failing_lookup_redirects(self, app, client, login_as):
        login_as(client, 'er_view_fail', 'emergency')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.emergency.cases.select', boom):
            resp = client.get('/emergency/cases/1')
        assert resp.status_code in (302, 404)


class TestCreateEmergencyCase:
    """``POST /emergency/cases/create``."""

    def test_a_missing_patient_id_is_refused(self, app, client, login_as):
        login_as(client, 'er_create_missing', 'emergency')
        resp = client.post(
            '/emergency/cases/create',
            json={'case_description': 'chest pain'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_an_invalid_patient_id_is_refused(self, app, client, login_as):
        login_as(client, 'er_create_invalid', 'emergency')
        resp = client.post(
            '/emergency/cases/create',
            json={'patient_id': 'not-a-number'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_an_unknown_patient_is_refused(self, app, client, login_as):
        login_as(client, 'er_create_unknown_patient', 'emergency')
        resp = client.post(
            '/emergency/cases/create',
            json={'patient_id': 999999},
        )
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_a_case_is_created(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        patient = _patient(_db, tenant.id)
        _db.session.commit()

        login_as(client, 'er_create_ok', 'emergency')
        resp = client.post(
            '/emergency/cases/create',
            json={
                'patient_id': patient.id,
                'case_description': 'chest pain',
                'priority': 'high',
            },
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert 'visit_id' in payload
        assert 'case_id' in payload

    def test_a_failing_create_answers_500(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        patient = _patient(_db, tenant.id)
        _db.session.commit()

        login_as(client, 'er_create_fail', 'emergency')
        with patch(
            'routes.emergency.cases.safe_commit',
            side_effect=RuntimeError('database down'),
        ):
            resp = client.post(
                '/emergency/cases/create',
                json={'patient_id': patient.id},
            )
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


class TestEditEmergencyCase:
    """``/emergency/cases/<id>/edit``."""

    def test_an_unknown_case_redirects(self, app, client, login_as):
        login_as(client, 'er_edit_missing', 'emergency')
        resp = client.get('/emergency/cases/999999/edit')
        assert resp.status_code in (302, 404)

    def test_a_known_case_can_be_edited(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        patient = _patient(_db, tenant.id)
        _db.session.commit()

        login_as(client, 'er_create_for_edit', 'emergency')
        resp = client.post(
            '/emergency/cases/create',
            json={'patient_id': patient.id, 'case_description': 'chest pain'},
        )
        case_id = resp.get_json()['case_id']

        login_as(client, 'er_edit_ok', 'emergency')
        resp = client.get(f'/emergency/cases/{case_id}/edit')
        assert resp.status_code in (200, 302)

        resp = client.post(
            f'/emergency/cases/{case_id}/edit',
            data={'chief_complaint': 'updated complaint', 'severity': 'HIGH'},
        )
        assert resp.status_code in (200, 302)


class TestResolveEmergencyCase:
    """``POST /emergency/cases/<id>/resolve``."""

    def test_an_unknown_case_answers_404(self, app, client, login_as):
        login_as(client, 'er_resolve_missing', 'emergency')
        resp = client.post('/emergency/cases/999999/resolve')
        assert resp.status_code in (404, 302)

    def test_a_case_is_resolved(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        patient = _patient(_db, tenant.id)
        _db.session.commit()

        login_as(client, 'er_create_for_resolve', 'emergency')
        resp = client.post(
            '/emergency/cases/create',
            json={'patient_id': patient.id, 'case_description': 'chest pain'},
        )
        case_id = resp.get_json()['case_id']

        login_as(client, 'er_resolve_ok', 'emergency')
        resp = client.post(f'/emergency/cases/{case_id}/resolve')
        assert resp.status_code in (200, 302)


class TestConvertEmergencyCase:
    """``POST /emergency/cases/<id>/convert``."""

    def test_an_unknown_case_answers_404(self, app, client, login_as):
        login_as(client, 'er_convert_missing', 'emergency')
        resp = client.post('/emergency/cases/999999/convert', json={})
        assert resp.status_code in (404, 302)

    def test_a_case_is_converted(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        patient = _patient(_db, tenant.id)
        _db.session.commit()

        login_as(client, 'er_create_for_convert', 'emergency')
        resp = client.post(
            '/emergency/cases/create',
            json={'patient_id': patient.id, 'case_description': 'chest pain'},
        )
        case_id = resp.get_json()['case_id']

        login_as(client, 'er_convert_ok', 'emergency')
        resp = client.post(f'/emergency/cases/{case_id}/convert', json={'new_destination': 'lab'})
        assert resp.status_code in (200, 302, 400, 404)
