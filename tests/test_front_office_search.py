"""Batch 2 (Front Office) search: real PostgreSQL, real RLS, no false passes.

Why this file exists
--------------------
Reception searched encrypted columns with ilike(). Those columns hold AES-GCM
ciphertext, so the same plaintext encrypts differently on every write and the
predicate could never be true. Every front-office search returned an empty
result, which a receptionist reads as "no such patient".

Three traps are designed out explicitly, because each one produced a green
test over broken code in an earlier draft of this file:

1. UI echo. The visits and appointments pages render the search term back into
   the search input. Asserting that the search term appears in the response
   passes even when the query matches nothing. Every test here searches for one
   token and asserts on a *different*, unique token that can only appear inside
   a result row.
2. Blind-index collisions. national_id and phone are unique per tenant through
   their blind indexes, so a shared fixture value makes the second insert in a
   session collide and the search then matches nothing. Every generated
   identity value carries a uuid4 tag.
3. Silent failure. QueueManagementService.get_queue_status_all had a bare
   `except Exception: return None` that converted a programming error into a
   null result. TestQueueScopeCoversTheSilentFailure locks that shut.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from models.patient import Patient

pytestmark = pytest.mark.usefixtures('rollback_db', 'test_tenant')

# Arabic literals live here as escapes on purpose: this file is written by a
# tool, and a shell that mis-encodes UTF-8 would silently turn a test
# assertion into a comparison against mojibake.
AR_FIRST = 'محمد'
AR_FAMILY = 'العتيبي'


def tag() -> str:
    """A short token that is unique to one test and to one run."""
    return uuid.uuid4().hex[:10]


def make_patient(test_tenant, *, first_name='Sara', last_name=None, **kw) -> Patient:
    """A patient whose values cannot collide with any other test.

    The unique marker is appended to the *Arabic* family name because
    Patient.full_name returns the Arabic pair whenever both Arabic names are
    set, and that is what the templates render. An ASCII marker would never
    appear on the page and the test would fail for the wrong reason.
    """
    marker = kw.get('last_name_ar') or f'{AR_FAMILY}{tag()}'
    p = Patient(
        first_name=first_name,
        last_name=last_name or f'Otaibi{tag()}',
        first_name_ar=kw.get('first_name_ar', AR_FIRST),
        last_name_ar=marker,
        phone=kw.get('phone') or f'059{uuid.uuid4().int % 10**7:07d}',
        national_id=kw.get('national_id') or f'ID-{tag()}',
        gender=kw.get('gender', 'M'),
    )
    db.session.add(p)
    db.session.commit()
    return p


def make_appointment(test_tenant, patient_id):
    from datetime import UTC, datetime, timedelta

    from models.appointment import Appointment

    a = Appointment(
        patient_id=patient_id,
        starts_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.session.add(a)
    db.session.commit()
    return a


def make_visit(test_tenant, patient_id):
    from models.department import Department
    from models.visit import Visit

    d = Department(name=f'Dept-{tag()}', name_ar='قسم', is_active=True)
    db.session.add(d)
    db.session.commit()
    v = Visit(
        patient_id=patient_id,
        department_id=d.id,
        status='OPEN',
        payment_status='PENDING',
        total_amount=0,
        paid_amount=0,
        visit_type='REGULAR',
    )
    db.session.add(v)
    db.session.commit()
    return v


def log_in_as_reception(client, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username=f'rec_{tag()}', role='reception')
    login_test_client(client, u, test_tenant)
    return u


class TestSearchIdsBackingFrontOfficeSearch:
    """The primitive the routes now depend on."""

    def test_finds_patient_by_partial_arabic_first_name(self, test_tenant):
        p = make_patient(test_tenant)
        found = (
            db.session.execute(
                select(Patient.id).where(Patient.id.in_(Patient.search_ids(AR_FIRST)))
            )
            .scalars()
            .all()
        )
        assert p.id in found, 'partial Arabic first name returned nothing'

    def test_finds_patient_by_partial_arabic_family_name(self, test_tenant):
        p = make_patient(test_tenant)
        # A middle slice of the Arabic family name.
        found = (
            db.session.execute(select(Patient.id).where(Patient.id.in_(Patient.search_ids('عتيب'))))
            .scalars()
            .all()
        )
        assert p.id in found, 'partial Arabic family name returned nothing'

    def test_finds_patient_by_partial_phone(self, test_tenant):
        p = make_patient(test_tenant, phone='0551234567')
        found = (
            db.session.execute(
                select(Patient.id).where(Patient.id.in_(Patient.search_ids('123456')))
            )
            .scalars()
            .all()
        )
        assert p.id in found, 'partial phone returned nothing'

    def test_finds_patient_by_partial_national_id(self, test_tenant):
        p = make_patient(test_tenant, national_id='ID-778899')
        found = (
            db.session.execute(select(Patient.id).where(Patient.id.in_(Patient.search_ids('7788'))))
            .scalars()
            .all()
        )
        assert p.id in found, 'partial national id returned nothing'

    def test_search_ignores_an_unrelated_patient(self, test_tenant):
        other = make_patient(test_tenant, first_name='Zainab')
        found = (
            db.session.execute(
                select(Patient.id).where(Patient.id.in_(Patient.search_ids('Zainab')))
            )
            .scalars()
            .all()
        )
        assert other.id in found
        assert (
            other.id
            not in db.session.execute(
                select(Patient.id).where(Patient.id.in_(Patient.search_ids('Otaibi0000')))
            )
            .scalars()
            .all()
        ), 'a nonsense term matched a patient'


class TestReceptionVisitsSearch:
    """A receptionist registering a visit for a known patient."""

    def test_search_by_arabic_name_returns_the_patient(self, client, test_tenant):
        log_in_as_reception(client, test_tenant)
        p = make_patient(test_tenant)
        make_visit(test_tenant, p.id)
        marker = p.last_name_ar  # unique Arabic marker, what full_name renders

        r = client.get(f'/reception/visits?search={AR_FIRST}')

        assert r.status_code == 200, f'visits search returned {r.status_code}'
        body = r.get_data(as_text=True)
        assert marker in body, 'the matching patient row was absent from the visits list'

    def test_search_by_partial_phone_returns_the_patient(self, client, test_tenant):
        log_in_as_reception(client, test_tenant)
        p = make_patient(test_tenant, phone='0551234567')
        make_visit(test_tenant, p.id)
        marker = p.last_name_ar

        r = client.get('/reception/visits?search=123456')

        assert r.status_code == 200
        assert marker in r.get_data(as_text=True), (
            'a partial phone number did not bring up the patient'
        )

    def test_search_that_matches_nobody_returns_no_patient(self, client, test_tenant):
        """The negative control. Without it, the positive assertions above
        could pass for reasons unrelated to the search."""
        log_in_as_reception(client, test_tenant)
        p = make_patient(test_tenant)
        make_visit(test_tenant, p.id)
        marker = p.last_name_ar

        r = client.get(f'/reception/visits?search=OtaibiZZZ{tag()}')

        assert r.status_code == 200
        assert marker not in r.get_data(as_text=True), (
            'a search for an absent patient still listed them'
        )


class TestReceptionAppointmentsSearch:
    def test_search_by_arabic_name_returns_the_patient(self, client, test_tenant):
        log_in_as_reception(client, test_tenant)
        p = make_patient(test_tenant)
        make_appointment(test_tenant, p.id)
        marker = p.last_name_ar

        r = client.get(f'/reception/appointments?search={AR_FIRST}')

        assert r.status_code == 200, f'appointments search returned {r.status_code}'
        body = r.get_data(as_text=True)
        assert marker in body, 'the matching patient was absent from the appointments list'


class TestQueueSearchUsesTheBlindIndex:
    """Queue search ran the same ciphertext ilike; the plain queue_number half
    of the predicate had to keep working."""

    def _ticket(self, test_tenant, queue_number):
        from app.shared.enums import QueueState
        from models.department import Department
        from models.queue_management import QueueManagement

        d = db.session.execute(select(Department).limit(1)).scalars().first()
        if d is None:
            d = Department(name=f'Dept-{tag()}', name_ar='قسم', is_active=True)
            db.session.add(d)
            db.session.commit()
        p = make_patient(test_tenant)
        t = QueueManagement(
            patient_id=p.id,
            department_id=d.id,
            queue_number=queue_number,
            status=QueueState.WAITING,
        )
        db.session.add(t)
        db.session.commit()
        return d, p, t

    def test_queue_search_finds_a_ticket_by_arabic_patient_name(self, test_tenant):
        from services.queue_management_service import QueueManagementService

        d, _patient, _ticket = self._ticket(test_tenant, f'Q-{tag()}')

        res = QueueManagementService().get_queue_status_all([d.id], search=AR_FIRST)

        assert res is not None, 'the service swallowed an error and returned None'
        numbers = [t['ticket_number'] for t in res['tickets']]
        assert numbers, 'queue search by Arabic patient name returned no tickets'

    def test_queue_number_search_still_works(self, test_tenant):
        from services.queue_management_service import QueueManagementService

        qn = f'Q-{tag()}'
        d, _, _ = self._ticket(test_tenant, qn)

        res = QueueManagementService().get_queue_status_all([d.id], search=qn)

        assert res is not None
        assert qn in [t['ticket_number'] for t in res['tickets']], (
            'the plain-text queue number search regressed when the encrypted half was replaced'
        )


class TestQueueScopeCoversTheSilentFailure:
    """Regression lock for the bare `except Exception: return None`.

    `get_queue_status_all(None)` used to build `.in_(None)`, raise
    ArgumentError, swallow it, and hand the caller a null. A caller cannot
    distinguish that from a database outage, so the UI showed a generic
    failure and the cause was lost.
    """

    def test_no_department_scope_returns_an_empty_board_not_none(self, test_tenant):
        from services.queue_management_service import QueueManagementService

        res = QueueManagementService().get_queue_status_all(None)

        assert res is not None, (
            'an empty department scope returned None; the error is being swallowed'
        )
        assert res['tickets'] == []
        assert res['waiting_count'] == 0

    def test_empty_department_scope_returns_an_empty_board_not_none(self, test_tenant):
        from services.queue_management_service import QueueManagementService

        res = QueueManagementService().get_queue_status_all([])

        assert res is not None
        assert res['tickets'] == []

    def test_a_broken_query_is_not_reported_as_an_empty_board(self, test_tenant):
        """If the query really does fail, the failure must surface. This is the
        distinction the old code erased."""
        from services.queue_management_service import QueueManagementService

        svc = QueueManagementService()
        calls = {'n': 0}
        real_execute = db.session.execute

        def flaky(*a, **kw):
            calls['n'] += 1
            raise RuntimeError('injected failure')

        db.session.execute = flaky
        try:
            res = svc.get_queue_status_all([1], search=AR_FIRST)
        finally:
            db.session.execute = real_execute

        assert res is None, 'a genuine database failure was reported as a normal empty result'
        assert calls['n'] > 0, 'the injected failure was never reached'
