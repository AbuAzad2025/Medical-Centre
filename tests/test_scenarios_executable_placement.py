"""Execute the inpatient placement and pricing surfaces.

Phase 7b. Two questions the bed module does not answer for itself.

The first is what a nurse is shown. The second is what a bed costs. Both are
narrow, both have a definite answer, and both matter more than the state machine
already covered in the admission module.

Driven through:

  GET /bed/api/available-beds
  GET /bed/api/bed-status
  POST /bed/api/admissions/admit

What execution established:

  * The endpoint named for available beds returns every bed. There is no status
    filter on the query and no status field in the response, so an occupied bed, a
    bed in CLEANING and a bed that is OUT_OF_ORDER are all presented exactly like a
    free one. A caller cannot tell them apart from the response, which is the part
    that turns a naming problem into a placement error.

  * Nothing prices a bed. Bed carries bed_type and no money; ServicePrice prices
    services and doctors, and nothing links either to a bed or a room. An ICU bed
    and a standard bed in the same ward cost the same because neither has a cost.
    The specification names this as the finding, and it holds.

Both are asserted against behaviour rather than against source, because both could
be fixed by a template change that leaves the route alone.
"""

from __future__ import annotations

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.bed_management import Admission, Bed, Room, Ward
from tests.scenario_execution_registry import covers


@pytest.fixture
def house(app, test_tenant):
    """A ward with a free bed, an occupied bed and one out of order."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['inpatient'])
    nurse = ensure_test_user(db, test_tenant, username='e2e_place_nurse', role='nurse')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, nurse, test_tenant)

    from models.patient import Patient
    from models.visit import Visit

    ward = Ward(tenant_id=test_tenant.id, name='Placement Ward', name_ar='عنبر التوزيع', code='PW1')
    db.session.add(ward)
    db.session.flush()

    room = Room(tenant_id=test_tenant.id, ward_id=ward.id, name='Room 1', code='PR1')
    db.session.add(room)
    db.session.flush()

    free = Bed(tenant_id=test_tenant.id, room_id=room.id, bed_number='PW1-A', status='AVAILABLE')
    taken = Bed(tenant_id=test_tenant.id, room_id=room.id, bed_number='PW1-B', status='OCCUPIED')
    broken = Bed(
        tenant_id=test_tenant.id, room_id=room.id, bed_number='PW1-C', status='OUT_OF_ORDER'
    )
    db.session.add_all([free, taken, broken])
    db.session.flush()

    patient = Patient(
        tenant_id=test_tenant.id, first_name='Place', last_name='Holder', national_id='E2E-PLACE-1'
    )
    db.session.add(patient)
    db.session.flush()
    taken.current_patient_id = patient.id

    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        visit_number='E2E-PLACE-VISIT-1',
        status='IN_PROGRESS',
    )
    db.session.add(visit)
    db.session.commit()

    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'nurse': nurse,
        'ward': ward,
        'free': free,
        'taken': taken,
        'broken': broken,
        'visit': visit,
    }


def _beds_from(resp):
    payload = resp.get_json()
    return payload if isinstance(payload, list) else (payload or {}).get('beds', [])


@covers('INPATIENT_PLACEMENT_BY_WARD_AND_BED')
class TestTheAvailableBedsList:
    def test_the_available_beds_endpoint_returns_only_available_beds(self, house):
        """Beds that cannot take a patient must not look like beds that can.

        The route selects every Bed with no status predicate, and the response
        carries id, bed_number, room and ward — no status. So a nurse reading this
        list cannot distinguish a free bed from an occupied one, a bed still in
        CLEANING after a discharge, or a bed broken and awaiting repair. The admit
        route does reject them, so the mistake surfaces at the admit, after a bed
        has been chosen and a visit has been opened against it.
        """
        client = house['client']

        resp = client.get('/bed/api/available-beds', follow_redirects=False)
        assert resp.status_code == 200, f'available-beds answered {resp.status_code}'

        rows = _beds_from(resp)
        numbers = {r.get('bed_number') for r in rows}

        assert house['free'].bed_number in numbers, (
            'the free bed is missing from the available-beds list'
        )
        assert house['taken'].bed_number not in numbers, (
            f'an occupied bed ({house["taken"].bed_number}) is listed as available, '
            f'with no status field in the response to tell the caller otherwise. '
            f'The list is {sorted(numbers)}'
        )
        assert house['broken'].bed_number not in numbers, (
            f'a bed that is OUT_OF_ORDER ({house["broken"].bed_number}) is listed as '
            f'available. A bed under repair cannot take a patient'
        )

    def test_the_bed_status_endpoint_can_tell_them_apart(self, house):
        """The neighbouring endpoint does carry status, which is the point.

        Recorded as the contrast that makes the first case concrete: /bed/api/bed-status
        returns status and the current patient for every bed, so the information the
        placement list withholds is already available one route over.
        """
        client = house['client']

        resp = client.get('/bed/api/bed-status', follow_redirects=False)
        assert resp.status_code == 200, f'bed-status answered {resp.status_code}'

        by_number = {r.get('number'): r for r in _beds_from(resp)}
        assert house['free'].bed_number in by_number, 'the free bed is missing from bed-status'
        assert by_number[house['free'].bed_number].get('status') == 'AVAILABLE'
        assert by_number[house['taken'].bed_number].get('status') == 'OCCUPIED'


@covers('INPATIENT_ADMIT_TRANSFER_DISCHARGE')
class TestBedsAreUnpriced:
    def test_a_critical_care_bed_costs_more_than_a_standard_one(self, house):
        """Two beds, same ward, different acuity, and both cost nothing.

        The specification names this as the finding for the template. bed_type is
        descriptive and there is no rate attached to a bed or a room anywhere in
        the pricing models, so a patient occupying an ICU bed is billed as though
        they were in the bed beside it.
        """
        from models.pricing import ServicePrice

        icu = Bed(
            tenant_id=house['tenant'].id,
            room_id=house['free'].room_id,
            bed_number='PW1-ICU',
            bed_type='ICU',
            status='AVAILABLE',
        )
        standard = Bed(
            tenant_id=house['tenant'].id,
            room_id=house['free'].room_id,
            bed_number='PW1-STD',
            bed_type='STANDARD',
            status='AVAILABLE',
        )
        db.session.add_all([icu, standard])
        db.session.commit()

        assert icu.bed_type != standard.bed_type, (
            'the fixture did not produce two different bed types, so the case would '
            'pass without comparing anything'
        )

        rates = (
            db.session.execute(
                select(ServicePrice).where(
                    ServicePrice.service_code.in_(['ICU', 'BED_ICU', icu.bed_type])
                )
            )
            .scalars()
            .all()
        )
        assert rates, (
            f'no ServicePrice exists for an ICU bed (bed_type={icu.bed_type!r}). '
            f'Bed carries no price column and nothing in models/pricing.py links a '
            f'rate to a bed or a room, so {icu.bed_type} and {standard.bed_type} '
            f'both bill at whatever the visit happens to cost — which for a bed is '
            f'nothing. A ward cannot charge for acuity.'
        )
        assert any(r.base_price and r.base_price > 0 for r in rates), (
            f'the ICU bed rates found are {[r.base_price for r in rates]}, none of '
            f'which charges anything'
        )


@covers('INPATIENT_PLACEMENT_BY_WARD_AND_BED')
class TestAdmissionGuardsStillHold:
    def test_an_out_of_order_bed_is_refused_at_admit(self, house):
        """The admit route does reject it, which is why the list matters.

        A caller who picked the broken bed from the list gets a refusal at the
        point of admission rather than a bed they can use, and the message names
        the bed. Pinned so the fix for the list cannot be made by weakening this.
        """
        client = house['client']

        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': house['visit'].id, 'bed_id': house['broken'].id},
            follow_redirects=False,
        )
        assert resp.status_code == 400, (
            f'admitting to an OUT_OF_ORDER bed answered {resp.status_code}'
        )
        body = resp.get_json()
        assert body.get('success') is False
        assert house['broken'].bed_number in (body.get('message') or ''), (
            f'the refusal does not name the bed: {body.get("message")!r}'
        )

        rows = (
            db.session.execute(select(Admission).filter_by(bed_id=house['broken'].id))
            .scalars()
            .all()
        )
        assert not rows, 'an admission was written against a bed that is out of order'


@covers('INPATIENT_SURGERY_SCHEDULING')
class TestTheOperatingRoomCannotBeWritten:
    def test_an_operation_can_be_scheduled(self, house):
        """Booking a list for theatre is the whole of this journey, and it cannot run.

        /or exposes a schedule view and a per-surgery view, both GET. There is no
        create route and no other code path that inserts a SurgerySchedule, so the
        table the specification describes scheduling into is populated by nothing —
        not by the interface, not by a seed, not by a service.

        For a template of 54 scenarios this is the whole thing: a patient cannot be
        put on a theatre list through this application.
        """
        import inspect

        from app.modules import owner as _unused  # noqa: F401  (import side effects only)
        from routes import or_management_routes as or_module

        source = inspect.getsource(or_module)
        # 'method=' never matches real Flask - the decorator keyword is
        # 'methods='. The three spellings below are all forms of that keyword.
        write_methods = ("methods=['POST']", 'methods="POST"', "methods='POST'")
        assert any(m in source for m in write_methods), (
            'no POST route exists in the OR blueprint. SurgerySchedule has required '
            'columns (procedure_name, scheduled_date) and nothing can write it, so '
            'an operation cannot be booked through this application'
        )

        from models.or_management import SurgerySchedule

        # Book through the route, not just through the source text above. A grep
        # proves a writer is declared; only a request proves it writes.
        client = house['client']
        patient = house['visit'].patient
        resp = client.post(
            '/or/schedule',
            data={
                'patient_id': str(patient.id),
                'procedure_name': 'Laparoscopic cholecystectomy',
                'scheduled_date': '2026-12-01',
                'or_room': 'Theatre 1',
                'surgery_type': 'ELECTIVE',
            },
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302), f'booking a surgery answered {resp.status_code}'

        rows = db.session.execute(select(SurgerySchedule)).scalars().all()
        assert len(rows) == 1, (
            f'expected one scheduled operation after booking, found {len(rows)}. '
            f'The POST route is declared but wrote no SurgerySchedule'
        )
        assert rows[0].procedure_name == 'Laparoscopic cholecystectomy'
        assert str(rows[0].scheduled_date) == '2026-12-01'
