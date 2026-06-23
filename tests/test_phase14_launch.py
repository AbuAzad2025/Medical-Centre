"""Tests for phase 14 — launch gate: G-134, ReportTemplate, §8, BS4 debt (§11.8)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

TECHNICAL_LEAK_PATTERNS = [
    re.compile(r'Traceback \(most recent call last\)'),
    re.compile(r'sqlalchemy\.exc\.'),
    re.compile(r'jinja2\.exceptions'),
    re.compile(r'UndefinedError'),
    re.compile(r'Internal Server Error'),
    re.compile(r'\b403 Forbidden\b'),
    re.compile(r'NoneType object'),
    re.compile(r'ModuleNotFoundError'),
    re.compile(r'Invalid entity'),
    re.compile(r'Model not found'),
]

# G-134 — 20 شاشة عينة عبر الأدوار
SCREEN_SAMPLES = [
    ('/auth/login', None),
    ('/pwa/offline', None),
    ('/kiosk/check-in', None),
    ('/__health', None),
    ('/medication/dashboard', 'pharmacist'),
    ('/medication/pos', 'pharmacist'),
    ('/manager/dashboard', 'manager'),
    ('/manager/reports-center', 'manager'),
    ('/report-builder/', 'manager'),
    ('/reception/dashboard', 'reception'),
    ('/reception/queue', 'reception'),
    ('/doctor/dashboard', 'doctor'),
    ('/doctor/patient-queue', 'doctor'),
    ('/lab/dashboard', 'lab'),
    ('/radiology/dashboard', 'radiology'),
    ('/emergency/dashboard', 'emergency'),
    ('/accountant/dashboard', 'accountant'),
    ('/finance/dashboard', 'accountant'),
    ('/nurse/tasks', 'nurse'),
    ('/dashboard', 'manager'),
]

BS4_LEGACY_MARKERS = ('font-weight-bold', 'data-dismiss="modal"')
# دين مُوثّق — لا يزيد دون قرار صريح (codemod لاحقاً)
BS4_DEBT_CEILING = 350


def _ensure_role_user(db, tenant, role: str) -> str:
    username = f'phase14_{role}'
    from models.user import User

    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(
            username=username,
            email=f'{username}@test.local',
            full_name=f'مستخدم {role}',
            role=role,
            is_active=True,
            tenant_id=tenant.id,
        )
        user.set_password('test123')
        db.session.add(user)
        db.session.commit()
    return username


def _login_as(client, tenant, role: str | None, db):
    if not role:
        return client
    from app.core.rate_limiter import _shared_store

    _shared_store.clear()
    username = _ensure_role_user(db, tenant, role)
    client.post(
        '/auth/login',
        data={'username': username, 'password': 'test123', 'tenant_slug': tenant.slug},
    )
    return client


class TestReportTemplateIntegration:
    def test_save_list_run_template(self, manager_auth_client, app):
        save_resp = manager_auth_client.post(
            '/report-builder/templates',
            json={
                'name': 'تقرير مرضى اختبار',
                'entity': 'patients',
                'fields': ['id', 'full_name'],
                'limit': 5,
            },
            content_type='application/json',
        )
        assert save_resp.status_code == 200
        payload = save_resp.get_json()
        assert payload['success'] is True
        tpl_id = payload['template']['id']

        list_resp = manager_auth_client.get('/report-builder/templates')
        assert list_resp.status_code == 200
        items = list_resp.get_json()['templates']
        assert any(t['id'] == tpl_id for t in items)

        run_resp = manager_auth_client.post(f'/report-builder/templates/{tpl_id}/run', json={})
        assert run_resp.status_code == 200
        run_data = run_resp.get_json()
        assert run_data['success'] is True
        assert run_data['headers'] == ['id', 'full_name']

    def test_builder_page_shows_saved_templates(self, manager_auth_client, app):
        manager_auth_client.post(
            '/report-builder/templates',
            json={'name': 'قالب واجهة', 'entity': 'visits', 'fields': ['id'], 'limit': 3},
            content_type='application/json',
        )
        resp = manager_auth_client.get('/report-builder/')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'قالب واجهة' in text
        assert 'saveTemplateBtn' in text

    def test_reports_center_lists_templates(self, manager_auth_client, app):
        manager_auth_client.post(
            '/report-builder/templates',
            json={'name': 'قالب مركز', 'entity': 'patients', 'fields': ['id'], 'limit': 2},
            content_type='application/json',
        )
        resp = manager_auth_client.get('/manager/reports-center')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'قوالب التقارير المحفوظة' in text
        assert 'قالب مركز' in text


class TestG134ScreenAudit:
    @pytest.mark.parametrize('path,role', SCREEN_SAMPLES)
    def test_no_technical_leaks_on_sample_screens(self, client, test_tenant, path, role, db):
        c = _login_as(client, test_tenant, role, db)
        resp = c.get(path, follow_redirects=True)
        assert resp.status_code in (200, 302), f'{path} returned {resp.status_code}'
        if resp.status_code != 200:
            return
        text = resp.get_data(as_text=True)
        for pattern in TECHNICAL_LEAK_PATTERNS:
            match = pattern.search(text)
            assert match is None, f'{path}: technical leak {match.group(0) if match else ""}'


class TestSection8LaunchChecks:
    def test_no_window_alert_in_pages_js(self):
        pages = ROOT / 'static' / 'js' / 'pages'
        offenders = []
        for js in pages.rglob('*.js'):
            if 'adminlte' in str(js):
                continue
            text = js.read_text(encoding='utf-8', errors='ignore')
            if re.search(r'window\.alert', text):
                offenders.append(str(js.relative_to(ROOT)))
        assert not offenders, f'window.alert in: {offenders}'

    def test_hero_has_animate_in(self):
        hero = (ROOT / 'templates' / 'dashboards' / '_hero.html').read_text(encoding='utf-8')
        assert 'animate-in' in hero

    def test_no_template_references_deleted_adminlte_vendor(self):
        """static/adminlte/ was deleted; sweetalert2 now lives under vendor/."""
        assert not (ROOT / 'static' / 'adminlte').exists()
        assert (ROOT / 'static' / 'vendor' / 'sweetalert2' / 'sweetalert2.all.min.js').exists()
        offenders = []
        for html in (ROOT / 'templates').rglob('*.html'):
            if 'adminlte' in html.read_text(encoding='utf-8', errors='ignore'):
                offenders.append(str(html.relative_to(ROOT)))
        assert not offenders, f'templates still reference adminlte: {offenders}'

    def test_bs4_compat_layer_in_clinical_css(self):
        css = (ROOT / 'static' / 'css' / 'clinical.css').read_text(encoding='utf-8')
        assert '.font-weight-bold' in css
        assert 'BS4' in css or 'compat' in css.lower()


class TestStatusLocalization:
    def test_enum_label_templates_compile(self, app):
        """Every template using the enum_label status filter must compile."""
        root = ROOT / 'templates'
        errors = []
        with app.app_context():
            for path in root.rglob('*.html'):
                text = path.read_text(encoding='utf-8', errors='ignore')
                if 'enum_label' not in text:
                    continue
                rel = path.relative_to(root).as_posix()
                try:
                    app.jinja_env.get_template(rel)
                except Exception as e:  # noqa: BLE001
                    errors.append((rel, type(e).__name__, str(e)[:160]))
        assert not errors, errors

    def test_no_raw_displayed_status_in_clinical_templates(self):
        """No raw `>{{ x.status }}<` display leaks in clinical/patient-facing dirs."""
        import re
        dirs = ['doctor', 'reception', 'nurse', 'lab', 'radiology', 'emergency', 'portal', 'pharmacy']
        pattern = re.compile(r'>\s*\{\{\s*[a-zA-Z_][\w.]*\.status\s*\}\}\s*<')
        offenders = []
        for d in dirs:
            base = ROOT / 'templates' / d
            if not base.exists():
                continue
            for html in base.rglob('*.html'):
                text = html.read_text(encoding='utf-8', errors='ignore')
                if pattern.search(text):
                    offenders.append(str(html.relative_to(ROOT)))
        assert not offenders, f'raw displayed status in: {offenders}'


class TestBS4DocumentedDebt:
    def test_legacy_marker_count_within_ceiling(self):
        count = 0
        for html in (ROOT / 'templates').rglob('*.html'):
            text = html.read_text(encoding='utf-8', errors='ignore')
            for marker in BS4_LEGACY_MARKERS:
                count += text.count(marker)
        assert count <= BS4_DEBT_CEILING, (
            f'BS4 legacy markers={count} exceeds documented ceiling {BS4_DEBT_CEILING}; '
            'run codemod or raise ceiling in test_phase14_launch.py after review'
        )

    def test_debt_snapshot_recorded_in_plan(self):
        plan = (ROOT / 'docs' / 'FRONTEND_TEMPLATES_DEVELOPMENT_PLAN.md').read_text(encoding='utf-8')
        assert '§11.8' in plan
        assert 'BS4' in plan
