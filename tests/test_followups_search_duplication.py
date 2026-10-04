"""The /reception/follow-ups search must not duplicate rows.

The view builds ``select(FollowUpRequest)`` and, when a search term is given,
filters it with ``FollowUpRequest.patient_id.in_(Patient.search_ids(...))``. Naming the Patient
entity in that predicate put ``patients`` into the FROM clause next to
``follow_up_requests``, with nothing joining the two, so PostgreSQL cross joined
them. The predicate then matched once for every patient the search returned, and
the page rendered each follow-up once per hit.

The fix correlates through ``FollowUpRequest.patient_id`` instead, which needs
only the id list and leaves ``patients`` out of the query entirely.
"""

import warnings
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import SAWarning


def _build_follow_ups_query(search):
    """The query the view builds, kept in step with routes/reception/appointments.py."""
    from models.follow_up import FollowUpRequest
    from models.patient import Patient

    query = select(FollowUpRequest)
    if search:
        query = query.filter(FollowUpRequest.patient_id.in_(Patient.search_ids(search, limit=1000)))
    return query


def test_search_returns_each_follow_up_once(app, rollback_db):
    """Two matching follow-ups must come back as two rows, not one per patient."""
    from app.extensions import db
    from models.follow_up import FollowUpRequest
    from models.patient import Patient

    patient = Patient(first_name='Duplicatesearch', last_name='Patient')
    db.session.add(patient)
    db.session.flush()

    for _ in range(2):
        db.session.add(
            FollowUpRequest(
                patient_id=patient.id,
                suggested_date=date.today(),
                status='PENDING',
                notes='x',
            )
        )
    db.session.flush()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', SAWarning)
        rows = db.session.execute(_build_follow_ups_query('Duplicatesearch')).scalars().all()

    cartesian = [str(w.message) for w in caught if 'cartesian' in str(w.message).lower()]
    assert not cartesian, f'unexpected cartesian product: {cartesian}'
    assert len(rows) == 2, f'expected 2 follow-ups, got {len(rows)}'
