"""Execute the wrong-patient read surfaces and check what they leak.

Phase 6. The clinical record surfaces are where a wrong-patient read hides, and
the specification says so directly: a result set built for a clinical chart and
one built for an administrative list can legitimately differ, and the difference
is where the mistake lives.

These endpoints return identity data — full_name, national_id, phone — so what
they omit matters more than what they add. The question asked of each is narrow
and answerable: can a caller in one tenant see a patient belonging to another?

Driven through:

  GET /doctor/api/patient-search
  GET /doctor/patients

What execution established:

  * The search endpoint carries no tenant predicate of its own. It builds
    ``select(Patient)`` and, when given a query, narrows it through
    Patient.search_ids. There is no ``Patient.tenant_id`` in that handler, and
    Patient.search only adds one when a tenant_id is passed — which this call
    site does not do.

  * Reading the handler alone therefore suggests a cross-tenant read of
    full_name, national_id and phone, which is identity data. That reading is
    wrong, and it is worth recording why, because the wrong reading is the
    dangerous one.

    Two layers sit underneath the query, neither of them in this file.
    ``do_orm_execute`` in app/shared/tenant_filter.py injects a tenant predicate
    into every ORM select, so the session hands the database a scoped query
    whatever the handler wrote. Row-level security on patients is the second,
    independent layer: policy ``tenant_isolation_patients`` compares tenant_id
    against ``current_setting('app.tenant_id')``.

    Measured, not assumed: with a patient staged in each of two tenants, a bare
    ``select(Patient)`` through the session returns one row, while raw SQL of
    the same table under the same connection returns both. The difference is
    the ORM event, which is what makes the endpoint safe.

  * The patient list states its scope in the query and does not depend on the
    event.

The case at the end asserts the handler still carries no tenant predicate. Its
failure is the good kind: it means someone added defence in depth and the marker
should be removed.
"""

from __future__ import annotations

import pytest
from flask import g

from app.extensions import db
from models.patient import Patient
from tests.scenario_execution_registry import covers


@pytest.fixture
def two_tenants(app, test_tenant):
    """A patient in this tenant, a patient in another, and a doctor for the first."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['doctor'])
    doctor = ensure_test_user(db, test_tenant, username='e2e_read_doctor', role='doctor')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, doctor, test_tenant)

    mine = Patient(
        tenant_id=test_tenant.id,
        first_name='Belongs',
        last_name='Here',
        national_id='E2E-READ-MINE',
        phone='0550000001',
    )
    db.session.add(mine)
    db.session.commit()
    mine_id, mine_national_id = mine.id, mine.national_id

    # A second tenant, with a patient whose name matches the search fragment.
    from app.core.tenant.models import Tenant

    other = Tenant(
        slug='e2e-read-other',
        name='Read Other',
        contact_email='other@example.com',
        status='ACTIVE',
        product_profile_code=None,
    )
    db.session.add(other)
    db.session.flush()

    theirs = Patient(
        tenant_id=other.id,
        first_name='Belongs',
        last_name='Elsewhere',
        national_id='E2E-READ-THEIRS',
        phone='0550000002',
    )
    db.session.add(theirs)
    db.session.commit()

    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'other': other,
        'doctor': doctor,
        'mine_id': mine_id,
        'mine_national_id': mine_national_id,
        'theirs_id': theirs.id,
        'theirs_national_id': theirs.national_id,
    }


def _search(client, fragment='Belongs'):
    resp = client.get(f'/doctor/api/patient-search?q={fragment}', follow_redirects=False)
    return resp, resp.get_json()


def _national_ids(payload):
    """Pull the national ids out of either shape the endpoint may return."""
    if isinstance(payload, dict):
        rows = payload.get('results') or payload.get('patients') or payload.get('data') or []
    else:
        rows = payload or []
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row.get('national_id'))
    return out


@covers('READ_DOCTOR_RECORDS_AND_PATIENTS')
class TestPatientSearchIsTenantScoped:
    def test_search_never_returns_a_patient_from_another_tenant(self, two_tenants):
        """The search fragment matches a patient in this tenant and one outside it.

        The endpoint answers with full_name, national_id and phone for everything
        it returns, so a leak here is a leak of identity data rather than a
        mislabelled row. The assertion is on the national id, because it is
        unique per patient and therefore cannot be satisfied by coincidence.
        """
        client = two_tenants['client']

        resp, payload = _search(client)
        assert resp.status_code == 200, f'patient-search answered {resp.status_code}'

        ids = _national_ids(payload)
        assert ids, f'the search returned no rows at all: {payload!r}'
        assert two_tenants['mine_national_id'] in ids, (
            f'the search did not return this tenant own patient. rows={ids}'
        )
        assert two_tenants['theirs_national_id'] not in ids, (
            f'patient-search returned national_id {two_tenants["theirs_national_id"]}, '
            f'which belongs to another tenant. rows={ids}. The handler builds '
            f'select(Patient) with no tenant predicate of its own, so this surface '
            f'relies on the do_orm_execute listener and on the patients RLS policy '
            f'rather than on its query.'
        )

    def test_the_patient_list_is_scoped_explicitly(self, two_tenants):
        """The administrative list states its scope in the query.

        Recorded next to the search case because the contrast is the useful part:
        this surface does not depend on the ORM listener to stay inside its
        tenant, and the search one does. Neither is currently wrong; only one of
        them would survive the listener being switched off.
        """
        client = two_tenants['client']

        resp = client.get('/doctor/patients', follow_redirects=False)
        assert resp.status_code == 200, f'the patient list answered {resp.status_code}'

        body = resp.get_data(as_text=True)
        assert two_tenants['theirs_national_id'] not in body, (
            f'the patient list rendered national_id {two_tenants["theirs_national_id"]} '
            f'from another tenant'
        )


@covers('READ_DOCTOR_RECORDS_AND_PATIENTS')
class TestWhereTheIsolationActuallyLives:
    """Pin the mechanism, so the next reader is not misled by the handler source.

    Written after getting this wrong. The handler states no tenant, which reads
    like a defect and is not one: do_orm_execute in app/shared/tenant_filter.py
    adds the predicate to every ORM select, and RLS is a second independent layer.
    Staging two tenants and reading the handler's source gives no hint of either.

    The first case is the measurement that settles it. Raw SQL of the same table,
    on the same connection, in the same test, returns both patients; the ORM
    select returns one. The difference between those two results is the entire
    subject of this class.
    """

    def test_a_bare_orm_select_is_scoped_while_raw_sql_is_not(self, two_tenants):
        """One connection, one transaction, two answers — and the ORM one is right."""
        from sqlalchemy import select as sa_select
        from sqlalchemy import text as sql_text

        raw_count = db.session.execute(sql_text('SELECT count(*) FROM patients')).scalar()
        assert raw_count >= 2, (
            f'the fixture staged {raw_count} patient row(s); this comparison only '
            f'means anything with a patient in each of two tenants'
        )

        scoped = db.session.execute(sa_select(Patient)).scalars().all()
        assert all(p.tenant_id == two_tenants['tenant'].id for p in scoped), (
            'a bare ORM select returned a patient outside this tenant: '
            f'{[(p.id, p.tenant_id) for p in scoped]}. Tenant isolation for ORM '
            f'selects is supplied by the do_orm_execute listener in '
            f'app/shared/tenant_filter.py, not by the individual queries.'
        )

    def test_the_search_handler_still_states_no_tenant_of_its_own(self, two_tenants):
        """A change here is an improvement and is meant to break this case."""
        import inspect

        from routes.doctor import patients as patients_module

        source = inspect.getsource(patients_module.api_patient_search)
        assert 'Patient.tenant_id' not in source, (
            'the patient search now filters on Patient.tenant_id itself. Good — that '
            'is defence in depth beyond the ORM listener and the RLS policy. Delete '
            'this case; the one above still holds and now has a fallback.'
        )
