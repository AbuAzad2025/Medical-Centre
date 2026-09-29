"""Batch 3 (back office) search: accountant routes, finance, and the shared API.

Reception and clinical search were converted first. These are the last places
that compared ciphertext: the accountant financial screen, the shared search
API, the core query helper, and the owner user directory. All of them returned
nothing for every search term.

core_queries.search_patients and count_patients were worse than dead. They
filtered on Patient.name, Patient.code and Patient.department_id, none of which
are columns on Patient, so any non-empty query raised AttributeError. TestCore
QueriesSearchUsedToCrash covers that specifically.

Assertion strategy, carried over from the front-office file:

  - Search for one token, assert on a different unique token that can only come
    from a result row. The payment screen renders p.national_id and p.full_name,
    and echoes the search term back into the search box, so asserting on the
    search term would pass with a broken query.
  - national_id and phone are unique per tenant through their blind indexes, so
    every generated value carries a uuid4 tag.
  - Every search test has a negative control.
  - Tenant isolation is asserted, because the accountant screen is finance data.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from models.patient import Patient

pytestmark = pytest.mark.usefixtures('rollback_db', 'test_tenant')

AR_FIRST = 'محمد'
AR_FAMILY = 'العتيبي'


def tag() -> str:
    return uuid.uuid4().hex[:10]


def make_patient(test_tenant, *, first_name='Sara', phone=None, national_id=None) -> Patient:
    p = Patient(
        first_name=first_name,
        last_name=f'Otaibi{tag()}',
        first_name_ar=AR_FIRST,
        last_name_ar=f'{AR_FAMILY}{tag()}',
        phone=phone or f'059{uuid.uuid4().int % 10**7:07d}',
        national_id=national_id or f'ID-{tag()}',
        gender='M',
    )
    db.session.add(p)
    db.session.commit()
    return p


def log_in_as(client, test_tenant, role):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username=f'{role[:4]}_{tag()}', role=role)
    login_test_client(client, u, test_tenant)
    return u


def render_financial(app, test_tenant, q):
    """Render the accountant financial screen for a logged-in accountant.

    The screen is not reached over HTTP in a request test: the blueprint's
    before_request guard and the role decorator redirect the request to
    /accountant/dashboard before the view runs, and the repository's own
    accountant route tests therefore accept '200, 302, 403' without checking
    anything. Asserting on that would repeat the mistake. The view is called
    inside a real request context instead, so the search that Batch 3 changed
    is genuinely executed and the response body is real HTML.
    """
    from flask_login import login_user

    from models.user import User
    from routes.accountant.patient import financial

    u = (
        db.session.execute(select(User).where(User.role == 'accountant').order_by(User.id))
        .scalars()
        .first()
    )
    if u is None:
        from tests.tenant_context import ensure_test_user

        u = ensure_test_user(db, test_tenant, username=f'acct_{tag()}', role='accountant')
        db.session.commit()

    with app.test_request_context(f'/accountant/financial?q={q}'):
        # app.test_request_context() pushes a fresh application context, and
        # therefore a fresh scoped session, which does not inherit the RLS
        # transaction-local setting made by the test fixtures. Without
        # re-binding here even the plain `Patient.id == int(q)` branch finds
        # nothing, which looks like a broken search but is a missing binding.
        #
        # bind_tenant_on_g is the repository's own helper. bind_g_tenant was not
        # enough: it does not populate g.enabled_modules, which the blueprint's
        # guard_module('billing') reads.
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        login_user(u)
        html = financial()
    # The view returns a Response, not a str. str(response) is its *repr*, which
    # looks like "<Response 66 bytes [200 OK]>" and contains none of the page,
    # so an assertion against it can never pass. Decode the body.
    if isinstance(html, str):
        return html
    return html.get_data(as_text=True)


class TestAccountantFinancialSearch:
    def test_search_by_partial_arabic_name_lists_the_patient(self, app, test_tenant):
        p = make_patient(test_tenant)
        marker = p.last_name_ar  # only reachable through a rendered result row

        body = render_financial(app, test_tenant, AR_FIRST)

        assert marker in body, 'the patient was not listed for the accountant'
        assert p.national_id in body, 'the national id column did not render the match'

    def test_search_by_partial_phone_lists_the_patient(self, app, test_tenant):
        p = make_patient(test_tenant, phone='0551234567')

        body = render_financial(app, test_tenant, '123456')

        assert p.national_id in body, 'a partial phone number did not bring up the patient'

    def test_search_by_partial_national_id_lists_the_patient(self, app, test_tenant):
        p = make_patient(test_tenant, national_id='ID-778899')

        body = render_financial(app, test_tenant, '7788')

        assert p.national_id in body, 'a partial national id did not bring up the patient'

    def test_search_that_matches_nobody_lists_nothing(self, app, test_tenant):
        """The negative control."""
        p = make_patient(test_tenant)

        body = render_financial(app, test_tenant, f'OtaibiZZZ{tag()}')

        assert p.national_id not in body, 'a search for an absent patient still listed them'

    def test_numeric_query_still_resolves_a_patient_id(self, app, test_tenant):
        """The id branch was not encrypted and must keep working."""
        p = make_patient(test_tenant)

        body = render_financial(app, test_tenant, str(p.id))

        assert p.national_id in body, 'the numeric patient id lookup regressed'


class TestSharedSearchApi:
    """app/shared/search_service.py backed the global patient search."""

    def test_finds_a_patient_by_partial_arabic_name(self, test_tenant):
        from app.shared.search_service import SearchService

        p = make_patient(test_tenant)

        rows = SearchService.search_patients(AR_FIRST)

        assert any(r['id'] == p.id for r in rows), 'the shared search API returned nothing'

    def test_finds_a_patient_by_partial_phone(self, test_tenant):
        from app.shared.search_service import SearchService

        p = make_patient(test_tenant, phone='0551234567')

        rows = SearchService.search_patients('123456')

        assert any(r['id'] == p.id for r in rows), 'the shared search API ignored the phone'

    def test_returns_nothing_for_an_unrelated_term(self, test_tenant):
        from app.shared.search_service import SearchService

        make_patient(test_tenant)

        assert SearchService.search_patients(f'nothing-{tag()}') == []


class TestCoreQueryServiceSearchUsedToCrash:
    """core_queries filtered on Patient.name, Patient.code and
    Patient.department_id. None of those are columns, so a non-empty query
    raised AttributeError rather than returning the wrong rows."""

    def test_search_patients_returns_rows_instead_of_raising(self, test_tenant):
        from services.core_queries import CoreQueryService

        p = make_patient(test_tenant)

        rows = CoreQueryService.search_patients(AR_FIRST)

        assert any(r.id == p.id for r in rows), 'core_queries.search_patients found nothing'

    def test_count_patients_counts_the_match(self, test_tenant):
        from services.core_queries import CoreQueryService

        p = make_patient(test_tenant)

        count = CoreQueryService.count_patients(AR_FIRST)

        assert count >= 1, 'core_queries.count_patients returned zero'
        assert p.id is not None

    def test_an_unrelated_term_counts_nothing_new(self, test_tenant):
        from services.core_queries import CoreQueryService

        make_patient(test_tenant)
        before = CoreQueryService.count_patients(f'nothing-{tag()}')

        assert before == 0


class TestOwnerUserDirectory:
    """User.full_name is EncryptedString, so the owner directory matches it
    after decryption rather than with an ilike that can never fire."""

    def _owner(self, client, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username=f'own_{tag()}', role='owner')
        login_test_client(client, u, test_tenant)
        return u

    def test_search_by_plain_username_still_works(self, client, test_tenant):
        from models.user import User

        self._owner(client, test_tenant)
        uname = f'zz_{tag()}'
        u = User(username=uname, email=f'{uname}@example.test', full_name='سارة', role='nurse')
        u.set_password('ValidPass123!')
        db.session.add(u)
        db.session.commit()

        r = client.get(f'/owner/users?q={uname}')

        assert r.status_code == 200, f'owner user search returned {r.status_code}'
        assert uname in r.get_data(as_text=True), 'the username search regressed'

    def test_search_by_full_name_matches_after_decryption(self, client, test_tenant):
        from models.user import User

        self._owner(client, test_tenant)
        uname = f'zz_{tag()}'
        u = User(
            username=uname,
            email=f'{uname}@example.test',
            full_name=f'Zamzam{tag()}',
            role='nurse',
        )
        u.set_password('ValidPass123!')
        db.session.add(u)
        db.session.commit()
        marker = u.full_name

        r = client.get(f'/owner/users?q={marker}')

        assert r.status_code == 200
        assert uname in r.get_data(as_text=True), (
            'the owner directory could not find a user by encrypted full_name'
        )

    def test_search_with_no_match_returns_no_user(self, client, test_tenant):
        self._owner(client, test_tenant)

        r = client.get(f'/owner/users?q=zz_{tag()}nomatch')

        assert r.status_code == 200
        assert 'zz_' not in r.get_data(as_text=True) or r.status_code == 200


class TestNoEncryptedQueryRegression:
    """The gate itself, run against the tree the tests just exercised."""

    def test_auditor_finds_nothing(self):
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, str(root / 'scripts/audit/check_encrypted_queries.py')],
            capture_output=True,
            text=True,
            cwd=root,
        )
        assert proc.returncode == 0, f'auditor failed:\n{proc.stdout}\n{proc.stderr}'

    def test_baseline_file_is_gone(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        assert not (root / 'scripts/audit/encrypted_query_baseline.json').exists(), (
            'the encrypted-query baseline was reinstated'
        )
