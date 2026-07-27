"""G-06 / G-34: Bootstrap 5 migration — reception modals and template audit."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_FORBIDDEN_BS4 = (
    (re.compile(r'data-dismiss="modal"'), 'data-dismiss (use data-bs-dismiss)'),
    (re.compile(r'data-toggle="(?:modal|tooltip|popover|tab|collapse|dropdown)"'), 'data-toggle (use data-bs-toggle)'),
    (re.compile(r'data-target="#'), 'data-target (use data-bs-target)'),
    (re.compile(r'class="close"'), 'class="close" (use btn-close)'),
)


def scan_templates():
    violations = []
    for root in (REPO_ROOT / 'templates', REPO_ROOT / 'static'):
        if not root.is_dir():
            continue
        for fpath in sorted(root.rglob('*')):
            if fpath.suffix not in ('.html', '.htm', '.js'):
                continue
            try:
                text = fpath.read_text(encoding='utf-8', errors='replace')
            except Exception as e:
                continue
            for regex, label in _FORBIDDEN_BS4:
                for m in regex.finditer(text):
                    line_num = text[:m.start()].count('\n') + 1
                    violations.append({
                        'file': str(fpath.relative_to(REPO_ROOT)),
                        'line': line_num,
                        'pattern': label,
                    })
    return violations


RECEPTION_QUEUE_PATH = REPO_ROOT / 'templates' / 'reception' / 'queue_management.html'
ADD_QUEUE_PATH = REPO_ROOT / 'templates' / 'reception' / 'add_patient_to_queue.html'
ADD_QUEUE_JS = REPO_ROOT / 'static' / 'js' / 'pages' / 'reception' / 'add_patient_to_queue.js'
BASE_HTML = REPO_ROOT / 'templates' / 'base.html'
PORTAL_BASE = REPO_ROOT / 'templates' / 'portal' / 'base.html'
CLINICAL_CSS = REPO_ROOT / 'static' / 'css' / 'clinical.css'


class TestBs4TemplateAudit:
    def test_no_forbidden_bs4_patterns_in_templates(self):
        violations = scan_templates()
        assert not violations, (
            'BS4 legacy patterns remain:\n'
            + '\n'.join(
                f"  {v['file']}:{v['line']} {v['pattern']}" for v in violations[:20]
            )
        )


class TestReceptionQueueBs5Modals:
    def test_queue_management_uses_bs5_dismiss(self):
        html = RECEPTION_QUEUE_PATH.read_text(encoding='utf-8')
        assert 'data-bs-dismiss="modal"' in html
        assert 'data-dismiss=' not in html
        assert re.search(r'class="btn-close"', html)

    def test_add_patient_modal_bs5_markup(self):
        html = ADD_QUEUE_PATH.read_text(encoding='utf-8')
        assert 'id="confirmAddModal"' in html
        assert 'data-bs-dismiss="modal"' in html
        assert 'data-dismiss=' not in html
        assert 'class="close"' not in html
        assert 'btn-close' in html

    def test_add_patient_js_uses_bootstrap_modal_api(self):
        js = ADD_QUEUE_JS.read_text(encoding='utf-8')
        assert 'bootstrap.Modal' in js
        assert '.modal(' not in js
        assert '$(' not in js


class TestClinicalThemeLinked:
    def test_main_base_links_bs5_and_clinical_css(self):
        html = BASE_HTML.read_text(encoding='utf-8')
        assert 'bootstrap@5.3.2' in html
        assert 'clinical.css' in html

    def test_portal_base_links_bs5_and_clinical_css(self):
        html = PORTAL_BASE.read_text(encoding='utf-8')
        assert 'bootstrap@5.3.2' in html
        assert 'clinical.css' in html

    def test_clinical_css_has_compat_bridge(self):
        css = CLINICAL_CSS.read_text(encoding='utf-8')
        assert 'BS4' in css or 'compat' in css.lower()
        assert '.fw-bold' in css or '.font-weight-bold' in css


class TestReceptionQueuePagesHttp:
    @pytest.fixture
    def reception_client(self, app, client, test_tenant):
        from app.extensions import db as _db
        from sqlalchemy import text
        from werkzeug.security import generate_password_hash
        from app.core.rate_limiter import _shared_store

        # Enable SaaS mode so ORM tenant filter + reassert_set_local work
        app.config['ENABLE_SAAS_MODE'] = True

        tenant_id = int(test_tenant.id)
        _shared_store.clear()
        _db.session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        row = _db.session.execute(
            text("""INSERT INTO users AS u
                (username, email, password_hash, full_name, role, is_active, tenant_id,
                 session_version, created_at, updated_at)
                VALUES (:u, :e, :p, :fn, :r, true, :t, 0, now(), now())
                ON CONFLICT (username, tenant_id) DO UPDATE
                SET password_hash = EXCLUDED.password_hash, email = EXCLUDED.email
                WHERE u.tenant_id = :t2
                RETURNING u.id, u.session_version"""),
            {
                'u': 'reception_bs4',
                'e': 'reception_bs4@test.local',
                'p': generate_password_hash('ValidPass123!'),
                'fn': 'استقبال BS4',
                'r': 'reception',
                't': tenant_id,
                't2': tenant_id,
            },
        ).fetchone()
        _db.session.commit()

        _shared_store.clear()
        from tests.tenant_context import login_test_client
        fake_user = type('FakeUser', (), {
            'id': row[0],
            'tenant_id': tenant_id,
            'session_version': row[1] or 0,
            'username': 'reception_bs4',
        })()
        login_test_client(client, fake_user, test_tenant)
        yield client

    def test_queue_management_page_renders_bs5_modals(self, reception_client):
        resp = reception_client.get('/reception/queue')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'data-bs-dismiss="modal"' in text
        assert 'data-dismiss=' not in text

    def test_add_patient_page_renders_bs5_confirm_modal(self, reception_client):
        resp = reception_client.get('/reception/queue/add-patient', follow_redirects=True)
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'confirmAddModal' in text
        assert 'data-bs-dismiss="modal"' in text
        assert 'data-dismiss=' not in text
        assert 'add_patient_to_queue.js' in text
