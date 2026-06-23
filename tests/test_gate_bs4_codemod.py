"""G-06 / G-34: Bootstrap 5 migration — reception modals and template audit."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.bs4_audit import REPO_ROOT, scan_templates

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
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='reception_bs4').first()
        if not u:
            u = User(
                username='reception_bs4',
                email='reception_bs4@test.local',
                full_name='استقبال BS4',
                role='reception',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'reception_bs4',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        yield client

    def test_queue_management_page_renders_bs5_modals(self, reception_client):
        resp = reception_client.get('/reception/queue')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'data-bs-dismiss="modal"' in text
        assert 'data-dismiss=' not in text

    def test_add_patient_page_renders_bs5_confirm_modal(self, reception_client):
        resp = reception_client.get('/reception/queue/add-patient')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'confirmAddModal' in text
        assert 'data-bs-dismiss="modal"' in text
        assert 'data-dismiss=' not in text
        assert 'add_patient_to_queue.js' in text
