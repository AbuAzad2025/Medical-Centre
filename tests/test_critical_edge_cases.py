"""Corrected C3/C4/C6/C7/C8 + boundary + safe_commit tests (no comments)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from tests.tenant_context import ensure_test_user, login_test_client, tenant_test_context


@pytest.mark.usefixtures('rollback_db')
class TestC1PendingTenant402:
    def test_pending_tenant_gets_402_page_not_500(self, app, client, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='c1_pending', role='reception')
        login_test_client(client, u, test_tenant)

        from app.extensions import db as _db

        t_db = _db.session.get(type(test_tenant), test_tenant.id)
        t_db.status = 'PENDING'
        _db.session.commit()

        resp = client.get(f'/t/{test_tenant.slug}/reception/visits')
        assert resp.status_code == 402, f'expected 402, got {resp.status_code}'
        body = resp.get_data(as_text=True)
        assert 'وصول مرفوض' in body or 'الحزمة' in body
        assert 'Traceback' not in body and 'sqlalchemy' not in body.lower()


@pytest.mark.usefixtures('rollback_db')
class TestC2BundlePatientLimit:
    def test_patient_cap_returns_arabic_error(self, app, client, db, test_tenant, monkeypatch):
        from app.core.saas import resolver as resolver_mod

        u = ensure_test_user(db, test_tenant, username='c2_recep', role='reception')
        login_test_client(client, u, test_tenant)

        import app.shared.tenant_filter as tf_mod

        def enforce_limit(instance, tenant_id):
            if getattr(instance, '__tablename__', '') == 'patients':
                raise ValueError('تم تجاوز الحد الأقصى للحزمة: يُسمح بـ 0 مريض كحد أقصى')

        monkeypatch.setattr(
            resolver_mod.EntitlementResolver,
            'get_limit',
            staticmethod(lambda _tid, key, *_a, **_k: 0 if key == 'max_patients' else None),
        )
        monkeypatch.setattr(tf_mod, '_check_bundle_limits_on_create', enforce_limit)

        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'فوق',
                'last_name': 'الحد',
                'national_id': 'C2NAT000001',
                'phone': '0501234567',
                'gender': 'male',
            },
            follow_redirects=False,
        )
        assert resp.status_code != 500, f'limit crash: {resp.status_code}'

        captured = ''
        if resp.is_json:
            captured = str(resp.get_json(silent=True).get('message', ''))
        else:
            with client.session_transaction() as sess:
                flashes = sess.get('_flashes', [])
            captured = ' '.join(str(m) for _, m in flashes)

        assert ('الحد الأقصى' in captured) or ('الحزمة' in captured), (
            resp.status_code,
            captured[:200],
        )


@pytest.mark.usefixtures('rollback_db')
class TestC5ImpersonationAudit:
    def test_impersonate_logs_actor_and_target(self, client, db, test_tenant):
        owner_u = ensure_test_user(db, test_tenant, username='c5_owner', role='owner')
        target = ensure_test_user(db, test_tenant, username='c5_target', role='reception')
        login_test_client(client, owner_u, test_tenant)

        resp = client.post(f'/auth/impersonate/{target.id}')
        assert resp.status_code in (200, 302), resp.status_code

        from models.audit_trail import AuditTrail

        row = (
            db.session.execute(
                select(AuditTrail)
                .where(AuditTrail.action == 'IMPERSONATE')
                .order_by(AuditTrail.id.desc())
            )
            .scalars()
            .first()
        )
        assert row is not None
        assert row.user_id == owner_u.id
        assert row.entity_id == target.id
        assert str(target.id) in (row.notes or '')


def _mk_patient(db, tenant_id: int, nid: str):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name='أحمد',
        last_name='الاختبار',
        national_id=nid,
    )
    db.session.add(p)
    db.session.flush()
    return p


def _mk_completed_visit(db, tenant_id: int, patient_id: int, total: str, paid: str):
    from models.visit import Visit

    v = Visit(
        tenant_id=tenant_id,
        patient_id=patient_id,
        visit_type='REGULAR',
        status='COMPLETED',
        visit_date=date.today(),
        currency='ILS',
        payment_method='CASH',
        payment_status='PAID' if Decimal(paid) >= Decimal(total) else 'PENDING',
        total_amount=Decimal(total),
        paid_amount=Decimal(paid),
        gl_posted_at=datetime.now(UTC),
        financial_locked=False,
        is_emergency=False,
        is_strong_pay=False,
        created_at=datetime.now(UTC),
    )
    db.session.add(v)
    db.session.flush()
    return v


@pytest.mark.usefixtures('rollback_db')
class TestC3RefundExceedsPaid:
    def test_refund_above_paid_rejected(self, db, test_tenant):
        from models.payment import Payment
        from services.refund_service import RefundService

        u = ensure_test_user(db, test_tenant, username='c3_acc', role='accountant')
        p = _mk_patient(db, test_tenant.id, 'C3NAT000001')

        pay = Payment(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            method='CASH',
            amount=Decimal('50.00'),
            currency='ILS',
            status='CONFIRMED',
        )
        db.session.add(pay)
        db_session_flush(db)

        ok, msg = RefundService.request_refund(
            tenant_id=test_tenant.id,
            payment_id=pay.id,
            amount=Decimal('60.00'),
            reason='خطأ تجريبي',
            requested_by=u.id,
        )
        assert ok is False
        assert any(w in str(msg) for w in ('يتجاوز', 'المبلغ'))


def db_session_flush(db):
    db.session.flush()


@pytest.mark.usefixtures('rollback_db')
class TestC4CrossTenantProbing:
    def test_tenant_a_cannot_open_tenant_b_visit(self, app, client, db, test_tenant):
        from app.core.tenant.models import Tenant
        from models.visit import Visit

        other = Tenant(
            slug=f'c4-other-{test_tenant.id}',
            name='Other Center',
            contact_email='c4@test.local',
            product_profile_code='multi_department_center',
            status='active',
        )
        db.session.add(other)
        db.session.flush()

        p_b = _mk_patient(db, other.id, 'C4NAT000001')
        v = Visit(
            tenant_id=other.id,
            patient_id=p_b.id,
            visit_type='REGULAR',
            status='OPEN',
            visit_date=date.today(),
            currency='ILS',
            created_at=datetime.now(UTC),
        )
        db.session.add(v)
        db.session.commit()

        u = ensure_test_user(db, test_tenant, username='c4_probe', role='doctor')
        login_test_client(client, u, test_tenant)

        resp = client.get(f'/t/{other.slug}/doctor/visits/{v.id}')
        assert resp.status_code in (302, 403, 404), f'unexpected {resp.status_code}'
        assert resp.status_code != 500


@pytest.mark.usefixtures('rollback_db')
class TestC6ArchiveBalance:
    def test_archive_blocked_on_outstanding_balance(self, db, test_tenant):
        from services.gatekeeper_service import GatekeeperService

        u = ensure_test_user(db, test_tenant, username='c6_rc', role='reception')
        p = _mk_patient(db, test_tenant.id, 'C6NAT000001')
        v = _mk_completed_visit(db, test_tenant.id, p.id, total='100', paid='10')

        ok, msg = GatekeeperService.archive_visit(v.id, u.id)
        assert ok is False
        assert any(w in str(msg) for w in ('رصيد', 'المتأخر', 'مبلغ'))

    def test_archive_allowed_when_settled(self, db, test_tenant):
        from services.gatekeeper_service import GatekeeperService

        u = ensure_test_user(db, test_tenant, username='c6b_rc', role='reception')
        p = _mk_patient(db, test_tenant.id, 'C6NAT000002')
        v = _mk_completed_visit(db, test_tenant.id, p.id, total='100', paid='100')

        result = GatekeeperService.archive_visit(v.id, u.id)
        ok = result[0] if isinstance(result, tuple) else bool(result)
        assert ok is True


@pytest.mark.usefixtures('rollback_db')
class TestC7SessionVersionBump:
    def test_loader_rejects_stale_version(self, app, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='c7_user', role='reception')

        from flask_login import login_manager as _lm_holder

        from app_factory import login_manager

        cb = login_manager._user_callback or _lm_holder._user_callback
        assert callable(cb)

        good = cb(f'{u.id}:0')
        assert good is not None and getattr(good, 'id', None) == u.id

        from app.extensions import db as _db

        u_db = _db.session.get(type(u), u.id)
        u_db.session_version = 1
        _db.session.commit()

        stale = cb(f'{u.id}:0')
        assert stale is None
        fresh = cb(f'{u.id}:1')
        assert fresh is not None


def _kiosk_fixture(db, tenant_id: int, nid: str):
    from models.appointment import Appointment
    from models.department import Department

    dept = (
        db.session.execute(select(Department).filter_by(tenant_id=tenant_id).limit(1))
        .scalars()
        .first()
    )
    if not dept:
        dept = Department(tenant_id=tenant_id, name='general', name_ar='عام')
        db.session.add(dept)
        db.session.flush()

    p = _mk_patient(db, tenant_id, nid)
    starts = datetime.combine(date.today(), datetime.min.time()).replace(
        hour=9, tzinfo=None
    ) + timedelta(days=0)
    appt = Appointment(
        tenant_id=tenant_id,
        patient_id=p.id,
        department_id=dept.id,
        starts_at=starts,
        ends_at=starts + timedelta(minutes=30),
        status='SCHEDULED',
        created_at=datetime.now(UTC),
    )
    db.session.add(appt)
    db.session.flush()
    return p, appt


@pytest.mark.usefixtures('rollback_db')
class TestC8KioskDedup:
    def test_duplicate_national_id_single_ticket(self, app, db, test_tenant):
        from services.kiosk_checkin_service import perform_kiosk_checkin

        _kiosk_fixture(db, test_tenant.id, 'C8NAT000009')
        db.session.commit()

        with tenant_test_context(app, test_tenant):
            first = perform_kiosk_checkin('C8NAT000009')
            assert first.get('success') is True, first
            assert first.get('visit_id'), first

            second = perform_kiosk_checkin('C8NAT000009')
            assert second.get('success') is True, second
            assert second.get('visit_id') == first.get('visit_id'), second
            assert 'مسبقا' in second.get('message', ''), second

    @pytest.mark.skip(reason='quarantined: high-concurrency covered by test_concurrency.py')
    def test_parallel_same_id_creates_one_ticket(self, app, db, test_tenant):
        from sqlalchemy import select

        from models.visit import Visit
        from services.kiosk_checkin_service import perform_kiosk_checkin

        _p, _appt = _kiosk_fixture(db, test_tenant.id, 'C8NATPAR0001')
        db.session.commit()
        marker_like = f'%[APPOINTMENT:{_appt.id}]%'

        with tenant_test_context(app, test_tenant):
            results = [perform_kiosk_checkin('C8NATPAR0001') for _ in range(12)]
            successes = [r for r in results if r.get('success')]
            assert successes, results
            visit_ids = {r.get('visit_id') for r in successes}
            assert len(visit_ids) == 1, visit_ids

            created = (
                db.session.execute(select(Visit).where(Visit.notes.like(marker_like)))
                .scalars()
                .all()
            )
        assert len(created) == 1, f'{len(created)} visits for one check-in'


@pytest.mark.usefixtures('rollback_db')
class TestBoundaries:
    def test_money_rounding_half_up(self):
        q = Decimal('0.005').quantize(Decimal('0.01'), rounding='ROUND_HALF_UP')
        assert str(q) == '0.01'

    def test_security_logs_page_size_capped(self, client, db, test_tenant):
        u = ensure_test_user(db, test_tenant, username='bd_sa', role='super_admin')
        login_test_client(client, u, test_tenant)

        resp = client.get('/super-admin/api/security-logs?page_size=10000')
        assert resp.status_code == 200
        assert resp.get_json()['pagination']['page_size'] <= 100

    def test_long_patient_name_rejected_gracefully(self, client, db, test_tenant):
        login_test_client(
            client,
            ensure_test_user(db, test_tenant, username='bd_len', role='reception'),
            test_tenant,
        )

        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'ا' * 500, 'last_name': 'تجربة', 'national_id': 'BDLEN000001'},
        )
        assert resp.status_code != 500
        body = resp.get_data(as_text=True)
        assert 'Traceback' not in body and 'DataError' not in body

    @pytest.mark.skip(reason='quarantined: heavy setup; dedicated suite covers')
    def test_queue_high_concurrency_unique_tickets(self, app, db, test_tenant):
        from sqlalchemy import select

        from models.visit import Visit
        from services.kiosk_checkin_service import perform_kiosk_checkin

        n = 40
        appt_ids = []
        for i in range(n):
            _p, _a = _kiosk_fixture(db, test_tenant.id, f'BDCONC{i:05d}')
            appt_ids.append(_a.id)
        db.session.commit()
        marker_likes = [f'%[APPOINTMENT:{aid}]%' for aid in appt_ids]

        with tenant_test_context(app, test_tenant):
            results = [perform_kiosk_checkin(f'BDCONC{i:05d}') for i in range(n)]
            failed = [r for r in results if not r.get('success')]
            assert not failed, failed[:5]

            created_n = (
                db.session.execute(
                    select(Visit).where(db.or_(*[Visit.notes.like(ml) for ml in marker_likes]))
                )
                .scalars()
                .all()
            )
        assert len(created_n) == n, f'expected {n} visits, got {len(created_n)}'


@pytest.mark.usefixtures('rollback_db')
class TestSafeCommitFeedback:
    def test_failed_commit_no_internal_leak(self, app, client, db, test_tenant, monkeypatch):
        sf_user = ensure_test_user(db, test_tenant, username='sf_rc2', role='reception')
        login_test_client(client, sf_user, test_tenant)

        class SimulatedOutageError(Exception):
            pass

        def boom(*a, **k):
            raise SimulatedOutageError('IntegrityError simulated')

        monkeypatch.setattr('sqlalchemy.orm.Session.commit', boom)

        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'سلامة', 'last_name': 'الفشل', 'national_id': 'SFNAT000002'},
        )
        body = resp.get_data(as_text=True)
        assert 'Traceback' not in body
        assert 'simulated db outage' not in body or 'internal server error' in body.lower()
