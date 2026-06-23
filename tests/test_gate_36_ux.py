"""G-126…G-129: global UX messages, user_message filter, doctor JS, empty states."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.shared.user_messages import resolve_user_message, user_message

REPO = Path(__file__).resolve().parents[1]
DOCTOR_JS = REPO / 'static' / 'js' / 'pages' / 'doctor'


class TestResolveUserMessage:
    def test_known_code(self):
        assert 'جهاز البطاقة' in resolve_user_message('pos_not_enabled')

    def test_arabic_passthrough(self):
        msg = 'المخزون غير كافٍ لدواء الاختبار'
        assert resolve_user_message(msg) == msg

    def test_technical_redacted(self):
        msg = resolve_user_message('IntegrityError on visit_id=12')
        assert 'visit_id' not in msg
        assert 'IntegrityError' not in msg

    def test_error_prefix_stripped_for_arabic(self):
        msg = resolve_user_message('خطأ: المخزون غير كافٍ')
        assert msg == 'المخزون غير كافٍ'

    def test_user_message_lookup(self):
        assert 'غير مصرح' in user_message('pos_unauthorized')


class TestUserMessageJinjaFilter:
    def test_filter_registered(self, app):
        assert 'user_message' in app.jinja_env.filters

    def test_filter_in_template(self, app):
        with app.app_context():
            from flask import render_template_string
            html = render_template_string(
                "{{ 'pos_connection_failed' | user_message }}"
            )
        assert 'الاتصال' in html
        assert 'pos_connection' not in html


class TestEmptyStateMacro:
    def test_renders_title_and_action(self, app):
        with app.app_context():
            from flask import render_template_string
            html = render_template_string(
                "{% from 'partials/_empty_state.html' import empty_state %}"
                "{{ empty_state(title='لا مرضى بالانتظار', action_url='/q', action_label='تحديث') }}"
            )
        assert 'لا مرضى بالانتظار' in html
        assert 'empty-state' in html
        assert 'href="/q"' in html


class TestApiFeedbackGlobal:
    def test_base_template_includes_notify_bundle(self):
        content = (REPO / 'templates' / 'base.html').read_text(encoding='utf-8')
        assert 'js/api-feedback.js' in content
        assert 'notify' not in content  # loaded at runtime, not inline


class TestDoctorJsNoRawAlert:
    @pytest.mark.parametrize('filename', [
        'notes.js',
        'visit_summary.js',
        'dental_chart.js',
        'dashboard.js',
        'diagnosis.js',
        'patient_details.js',
        'prescription.js',
        'patient_queue.js',
    ])
    def test_no_window_alert_in_doctor_pages(self, filename):
        path = DOCTOR_JS / filename
        if not path.exists():
            pytest.skip(f'missing {filename}')
        content = path.read_text(encoding='utf-8')
        assert 'window.alert(' not in content
        assert 'alert(' not in content.replace('// alert(', '')


class TestDoctorPatientQueueEmptyState:
    @pytest.fixture
    def doctor_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='doctor_g36').first()
        if not u:
            u = User(
                username='doctor_g36',
                email='doctor_g36@test.local',
                full_name='طبيب G36',
                role='doctor',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'doctor_g36',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        return client

    def test_queue_page_uses_empty_state_macro(self, doctor_client):
        resp = doctor_client.get('/doctor/patient-queue')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'empty-state' in text or 'لا مرضى بالانتظار' in text
