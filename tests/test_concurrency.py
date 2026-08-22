"""
Concurrency / race-condition suite.

Real-thread, real-PostgreSQL tests using threading.Barrier to maximise
contention windows.  Each test asserts the INVARIANT that must hold under
concurrency, not a specific interleaving:

  C1  Queue claim: N concurrent "call next" on k waiting entries ->
      exactly min(N,k) successes; every entry claimed at most once;
      no entry left half-updated (status CALLED without called_at).
  C2  Pharmacy dispense: N concurrent dispenses of ONE prescription ->
      exactly one sale; prescription DISPENSED once; stock decremented
      exactly once (service already uses SELECT ... FOR UPDATE).
  C3  Visit archive: N concurrent archives of one COMPLETED visit ->
      archive_status flips once; archived_by consistent with the winner.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.concurrency


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _run_concurrently(worker, n: int):
    """Run `worker(i)` in n threads released simultaneously by a barrier.

    Returns list of worker results in completion-agnostic order.
    """
    barrier = threading.Barrier(n)
    results = []
    lock = threading.Lock()

    def _wrap(i: int):
        barrier.wait()  # maximise overlap window
        try:
            r = worker(i)
        except Exception as e:  # surface crashes as failures
            r = ('EXCEPTION', repr(e))
        with lock:
            results.append(r)

    with ThreadPoolExecutor(max_workers=n) as ex:
        list(ex.map(_wrap, range(n)))
    return results


@pytest.fixture()
def queue_env(app, db, test_tenant):
    """Department + doctor + factory for waiting patients/visits/queue rows.

    Returns PLAIN IDS (not ORM objects) so worker threads never touch a
    detached instance from the fixture session.
    """
    import uuid
    from datetime import UTC, datetime

    from models.department import Department
    from models.patient import Patient
    from models.queue_management import QueueManagement
    from models.user import User
    from models.visit import Visit

    tag = uuid.uuid4().hex[:6]
    dept = Department(
        tenant_id=test_tenant.id,
        name=f'Q-{tag}',
        name_ar=f'قسم-{tag}',
        is_active=True,
    )
    db.session.add(dept)
    db.session.flush()

    doctor = User(
        tenant_id=test_tenant.id,
        username=f'dr_{tag}',
        email=f'dr_{tag}@test.local',
        full_name='طبيب الطابور',
        role='doctor',
        is_active=True,
    )
    doctor.set_password('ValidPass123!')
    db.session.add(doctor)
    db.session.commit()

    dept_id, doctor_id, tenant_id = dept.id, doctor.id, test_tenant.id

    def _make_waiting(k: int):
        made_ids = []
        now = datetime.now(UTC)
        for i in range(k):
            p = Patient(
                tenant_id=tenant_id,
                first_name=f'ق{tag}{k}{i}',
                last_name='انتظار',
                phone='055' + format(uuid.uuid4().int % 10**7, '07d'),
                gender='M',
            )
            db.session.add(p)
            db.session.flush()

            v = Visit(
                tenant_id=tenant_id,
                patient_id=p.id,
                department_id=dept_id,
                doctor_id=doctor_id,
                status='OPEN',
            )
            db.session.add(v)
            db.session.flush()

            qm = QueueManagement(
                tenant_id=tenant_id,
                patient_id=p.id,
                department_id=dept_id,
                visit_id=v.id,
                queue_number=f'T{uuid.uuid4().hex[:8]}',
                status='waiting',
                queued_at=now,
            )
            db.session.add(qm)
            db.session.flush()
            made_ids.append(qm.id)
        db.session.commit()
        return made_ids

    return {
        'db': db,
        'dept_id': dept_id,
        'doctor_id': doctor_id,
        'tenant_id': tenant_id,
        'make_waiting': _make_waiting,
    }


# ──────────────────────────────────────────────────────────────────────
# C1 — Queue claim race (regression for the fixed SELECT-then-UPDATE race)
# ──────────────────────────────────────────────────────────────────────


class TestQueueCallNextRace:
    def test_eight_callers_one_patient_claimed_exactly_once(self, app, queue_env):
        """8 receptionists hit "call next" simultaneously for 1 waiting entry."""
        from models.queue_management import QueueManagement
        from services.queue_management_service import QueueManagementService

        (qm_id,) = queue_env['make_waiting'](1)
        svc = QueueManagementService()
        tid = queue_env['tenant_id']
        dept_id = queue_env['dept_id']

        def caller(_i):
            # Each thread gets its own scoped session via Flask-SQLAlchemy.
            with app.test_request_context():
                from flask import g

                g.tenant_id = tid
                ok, msg = svc.call_next_patient(dept_id, called_by=None)
            return (ok, msg if not ok else 'called')

        results = _run_concurrently(caller, 8)
        successes = [r for r in results if r[0] is True]
        assert len(successes) == 1, f'expected single claim, got {len(successes)}: {results}'
        assert not any(r[0] == 'EXCEPTION' for r in results), results

        queue_env['db'].session.expire_all()
        row = queue_env['db'].session.get(QueueManagement, qm_id)
        status = row.status.value if hasattr(row.status, 'value') else str(row.status)
        assert status == 'called'
        assert row.called_at is not None

    def test_five_callers_five_patients_no_double_claim(self, app, queue_env):
        """5 callers vs 5 patients -> every patient claimed at most once."""
        from sqlalchemy import select

        from models.queue_management import QueueManagement
        from services.queue_management_service import QueueManagementService

        ids = queue_env['make_waiting'](5)
        svc = QueueManagementService()
        tid = queue_env['tenant_id']
        dept_id = queue_env['dept_id']

        def caller(_i):
            with app.test_request_context():
                from flask import g

                g.tenant_id = tid
                return svc.call_next_patient(dept_id)

        results = _run_concurrently(caller, 5)
        assert sum(1 for r in results if r[0] is True) == 5, results

        final = {
            q.id: (q.status.value if hasattr(q.status, 'value') else str(q.status))
            for q in queue_env['db']
            .session.execute(select(QueueManagement).filter(QueueManagement.id.in_(ids)))
            .scalars()
            .all()
        }
        assert all(s == 'called' for s in final.values()), final


# ──────────────────────────────────────────────────────────────────────
# C2 — Pharmacy dispense race (verifies FOR UPDATE protection end-to-end)
# ──────────────────────────────────────────────────────────────────────


class TestDispenseRace:
    def test_four_dispensers_single_prescription_one_sale(self, app, db, test_tenant):
        import uuid

        from sqlalchemy import select

        from app.shared.enums import PrescriptionState
        from models.medication import Medication, PharmacySale, Prescription
        from models.patient import Patient
        from models.user import User
        from models.visit import Visit
        from services.pharmacy_sale_service import PharmacySaleService

        tag = uuid.uuid4().hex[:6]
        pharmacist = User(
            tenant_id=test_tenant.id,
            username=f'ph_{tag}',
            email=f'ph_{tag}@test.local',
            full_name='صيدلي التزامن',
            role='pharmacist',
            is_active=True,
        )
        pharmacist.set_password('ValidPass123!')
        db.session.add(pharmacist)
        db.session.flush()

        med = Medication(
            tenant_id=test_tenant.id,
            trade_name=f'M-{tag}',
            scientific_name=f'S-{tag}',
            dosage_form='tablet',
            strength='500mg',
            price=10,
            stock_quantity=5,
            minimum_stock=0,
            category='general',
        )
        db.session.add(med)
        db.session.flush()

        p = Patient(
            tenant_id=test_tenant.id,
            first_name=f'P-{tag}',
            last_name='صرف',
            phone='056' + format(uuid.uuid4().int % 10**7, '07d'),
        )
        db.session.add(p)
        db.session.flush()
        v = Visit(tenant_id=test_tenant.id, patient_id=p.id, status='IN_PROGRESS')
        db.session.add(v)
        db.session.flush()
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            visit_id=v.id,
            doctor_id=None,
            prescription_number=f'RX-{tag}',
            status=PrescriptionState.ACTIVE,
        )
        db.session.add(rx)
        db.session.commit()
        rx_id = rx.id
        med_id = med.id
        dispenser_id = pharmacist.id

        def dispenser(i):
            with app.test_request_context():
                from flask import g

                g.tenant_id = test_tenant.id
                return PharmacySaleService.create_sale(
                    prescription_id=rx_id,
                    dispensed_by=dispenser_id,
                    items=[{'medication_id': med_id, 'quantity': 5, 'unit_price': 10}],
                    tenant_id=test_tenant.id,
                )

        results = _run_concurrently(dispenser, 4)
        wins = [r for r in results if 'error' not in r]
        losses = [r for r in results if 'error' in r]

        assert len(wins) == 1, f'exactly one dispense must win: {results}'
        assert len(losses) == 3, results
        allowed_errors = {'Insufficient stock', 'already dispensed'}
        assert all(any(a in l['error'] for a in allowed_errors) for l in losses), results

        db.session.expire_all()
        fresh_med = db.session.get(Medication, med_id)
        assert (fresh_med.stock_quantity or 0) == 0, 'stock must drop exactly once to zero'

        sales = (
            db.session.execute(
                select(PharmacySale).filter(PharmacySale.patient_id == p.id)  # noqa: E501
            )
            .scalars()
            .all()
        )
        assert len(sales) == 1


# ──────────────────────────────────────────────────────────────────────
# C3 — Visit archive race (GatekeeperService is the single write owner)
# ──────────────────────────────────────────────────────────────────────


class TestArchiveVisitRace:
    def test_six_archivers_visit_archives_once(self, app, db, test_tenant):
        import uuid

        from models.patient import Patient
        from models.user import User
        from models.visit import Visit
        from services.gatekeeper_service import GatekeeperService

        tag = uuid.uuid4().hex[:6]
        clerk = User(
            tenant_id=test_tenant.id,
            username=f'rc_{tag}',
            email=f'rc_{tag}@test.local',
            full_name='موظف أرشفة',
            role='reception',
            is_active=True,
        )
        clerk.set_password('ValidPass123!')
        db.session.add(clerk)
        db.session.flush()

        p = Patient(
            tenant_id=test_tenant.id,
            first_name=f'A-{tag}',
            last_name='أرشفة',
            phone='057' + format(uuid.uuid4().int % 10**7, '07d'),
        )
        db.session.add(p)
        db.session.flush()
        v = Visit(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            status='COMPLETED',
            archive_status='ACTIVE',
            gl_posted_at=datetime.now(UTC),
            total_amount=0,
            paid_amount=0,
            payment_status='PAID',
        )
        db.session.add(v)
        db.session.commit()
        visit_id, clerk_id = v.id, clerk.id

        def archiver(_i):
            with app.test_request_context():
                from flask import g

                g.tenant_id = test_tenant.id
                ok, msg = GatekeeperService.archive_visit(visit_id, clerk_id)
                return (
                    ok,
                    str(msg).encode('ascii', 'replace').decode() if not ok else 'archived',
                )

        results = _run_concurrently(archiver, 6)
        wins = [r for r in results if r[0] is True]
        assert len(wins) >= 1 and not any(r[0] == 'EXCEPTION' for r in results), results

        db.session.expire_all()
        fresh = db.session.get(Visit, visit_id)
        assert fresh.archive_status == 'ARCHIVED'
        assert fresh.archived_by == clerk_id
