"""G-120: Arabic payment status labels in visit templates (no raw enum codes)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.shared.enum_labels import (
    ENUM_LABELS_AR,
    enum_label,
    resolve_visit_payment_status_badge,
)


class TestPaymentStatusEnumLabels:
    """Unit coverage for PaymentStatus Arabic labels — not duplicated in test_payment_enum_unification."""

    @pytest.mark.parametrize('code,expected_ar', [
        ('PENDING', 'قيد الانتظار'),
        ('PAID', 'مدفوع'),
        ('PARTIAL', 'دفع جزئي'),
        ('DEBT', 'دين'),
        ('EMERGENCY_DEBT', 'دين طوارئ'),
        ('REFUNDED', 'مسترد'),
    ])
    def test_payment_status_has_arabic_label(self, code, expected_ar):
        assert enum_label(code, 'PaymentStatus') == expected_ar
        assert code not in enum_label(code, 'PaymentStatus')

    def test_all_payment_status_keys_labeled(self):
        for code in ENUM_LABELS_AR['PaymentStatus']:
            label = enum_label(code, 'PaymentStatus')
            assert label
            assert label != code


class TestResolveVisitPaymentStatusBadge:
    def test_pending_variant_and_label(self):
        badge = resolve_visit_payment_status_badge('PENDING', 0, 100)
        assert badge['variant'] == 'warning'
        assert badge['label'] == 'قيد الانتظار'
        assert 'PENDING' not in badge['label']

    def test_paid_when_remaining_zero(self):
        badge = resolve_visit_payment_status_badge('PENDING', 50, 0)
        assert badge['variant'] == 'success'
        assert badge['label'] == 'مدفوع'

    def test_partial_from_amounts(self):
        badge = resolve_visit_payment_status_badge('PENDING', 30, 70)
        assert badge['variant'] == 'info'
        assert 'جزئي' in badge['label']

    def test_emergency_debt(self):
        badge = resolve_visit_payment_status_badge('EMERGENCY_DEBT', 0, 50)
        assert badge['variant'] == 'danger'
        assert badge['label'] == 'دين طوارئ'


class TestPaymentStatusBadgeTemplate:
    def test_macro_renders_arabic_not_raw_code(self, app):
        visit = SimpleNamespace(
            payment_status='DEBT',
            paid_amount=0,
            remaining_amount=120,
        )
        with app.app_context():
            from flask import render_template_string
            html = render_template_string(
                '{% from "partials/_payment_status_badge.html" import payment_status_badge %}'
                '{{ payment_status_badge(visit) }}',
                visit=visit,
            )
        assert 'DEBT' not in html
        assert 'دين' in html
        assert 'badge bg-danger' in html


class TestReceptionVisitsPageLabels:
    @pytest.fixture
    def reception_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.patient import Patient
        from models.user import User
        from models.visit import Visit

        _shared_store.clear()
        u = User.query.filter_by(username='reception_g120').first()
        if not u:
            u = User(
                username='reception_g120',
                email='reception_g120@test.local',
                full_name='استقبال G120',
                role='reception',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        p = Patient(
            tenant_id=test_tenant.id,
            first_name='مريض',
            last_name='اختبار',
            phone='0599000001',
            national_id='G120TEST01',
        )
        _db.session.add(p)
        _db.session.flush()
        v = Visit(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            payment_status='EMERGENCY_DEBT',
            total_amount=200,
            paid_amount=0,
            status='OPEN',
        )
        _db.session.add(v)
        _db.session.commit()

        client.post('/auth/login', data={
            'username': 'reception_g120',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        yield client, v.id
        try:
            _db.session.delete(v)
            _db.session.delete(p)
            _db.session.commit()
        except Exception:
            _db.session.rollback()

    def test_visits_list_shows_arabic_payment_status(self, reception_client):
        client, _visit_id = reception_client
        resp = client.get('/reception/visits')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'دين طوارئ' in text
        assert 'bg-danger' in text
