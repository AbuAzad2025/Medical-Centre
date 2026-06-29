"""Front-end E2E — renders staff GET pages; asserts no 500s and no technical leaks."""
from __future__ import annotations

import re

import pytest

from tests.test_phase14_launch import (
    TECHNICAL_LEAK_PATTERNS,
    _login_as,
)

# blueprint name (endpoint prefix) -> role that may access it. Covers every
# page-bearing blueprint (staff + admin + portal + shared app pages). Pure
# API / integration blueprints (fhir, dicom, sso, telemedicine, ...) are
# validated via the static template checks below, not live render.
BP_ROLE = {
    'reception': 'reception',
    'doctor': 'doctor',
    'lab': 'lab',
    'radiology': 'radiology',
    'emergency': 'emergency',
    'nurse': 'nurse',
    'medication': 'pharmacist',
    'accountant': 'accountant',
    'finance': 'accountant',
    'payment': 'accountant',
    'manager': 'manager',
    'super_admin': 'super_admin',
    'main': 'manager',
    'inbox': 'manager',
    'report_builder': 'manager',
    'booking': 'reception',
    'specialty_forms': 'doctor',
    'quality': 'manager',
    'portal': 'patient',
    'owner': 'super_admin',  # owner_required accepts super_admin/admin/owner
}

# Skip only non-HTML / binary / session-ending GET endpoints. Detail pages,
# print pages, and JSON endpoints are INCLUDED (no exclusion of any page).
_SKIP_RE = re.compile(
    r'(logout|export|download|\.pdf\b|/pdf\b|/csv\b|/xlsx\b|/stream\b|/feed\b|'
    r'/raw\b|/ws\b|/sse\b)',
    re.IGNORECASE,
)

# concrete path builder — <int:visit_id> -> seeded id; unknown *_id -> 999999
_ARG_RE = re.compile(r'<(?:[^:>]+:)?([^>]+)>')


def _fill_path(rule_str: str, id_map: dict) -> str:
    def repl(m):
        name = m.group(1)
        if name in id_map:
            return str(id_map[name])
        if name.endswith('_id') or name in ('id', 'pk'):
            return '999999'  # non-existent -> route must handle gracefully (no 500)
        return 'test'
    return _ARG_RE.sub(repl, rule_str)


def _discover_pages(app):
    """All (path, role) for GET routes on page-bearing blueprints, including
    parametrized detail/print pages (kept as rule templates for arg filling)."""
    rules = []
    seen = set()
    for rule in app.url_map.iter_rules():
        if 'GET' not in (rule.methods or set()):
            continue
        endpoint = rule.endpoint
        bp = endpoint.split('.')[0]
        role = BP_ROLE.get(bp)
        if not role:
            continue
        rule_str = str(rule.rule)
        if _SKIP_RE.search(rule_str) or _SKIP_RE.search(endpoint):
            continue
        if rule_str in seen:
            continue
        seen.add(rule_str)
        rules.append((rule_str, role))
    return rules


@pytest.fixture(scope='function')
def e2e_seed(app, test_tenant, db):
    """Seed core entities so parametrized detail/print pages render real data."""
    from models.patient import Patient
    from models.visit import Visit

    db.session.rollback()
    p = Patient.query.filter_by(national_id='E2ESEED01').first()
    if not p:
        p = Patient(tenant_id=test_tenant.id, first_name='مريض', last_name='شامل',
                    phone='0599123456', national_id='E2ESEED01')
        db.session.add(p)
        db.session.flush()
    v = Visit.query.filter_by(patient_id=p.id).first()
    if not v:
        v = Visit(tenant_id=test_tenant.id, patient_id=p.id, payment_status='PENDING',
                  total_amount=100, paid_amount=0, status='OPEN')
        db.session.add(v)
    db.session.commit()
    return {'patient_id': p.id, 'visit_id': v.id}


class TestFrontendE2E:
    def test_all_get_pages_render_without_500(self, app, test_tenant, db, e2e_seed):
        rules = _discover_pages(app)
        assert len(rules) >= 100, f'discovery too small ({len(rules)}) — routing changed?'

        by_role: dict[str, list[str]] = {}
        for rule_str, role in rules:
            by_role.setdefault(role, []).append(rule_str)

        failures = []
        rendered = 0
        for role, rule_strs in by_role.items():
            db.session.rollback()  # isolate from any prior aborted txn
            client = app.test_client()
            _login_as(client, test_tenant, role, db)
            for rule_str in rule_strs:
                path = _fill_path(rule_str, e2e_seed)
                try:
                    resp = client.get(path, follow_redirects=False)
                except Exception as exc:  # noqa: BLE001 — a raised exc is a hard fail
                    failures.append((role, path, f'EXC:{type(exc).__name__}:{str(exc)[:140]}'))
                    db.session.rollback()
                    continue
                if resp.status_code == 500:
                    failures.append((role, path, 500))
                    db.session.rollback()  # clear aborted txn so the next page is isolated
                    continue
                rendered += 1
                if resp.status_code == 200 and resp.mimetype == 'text/html':
                    text = resp.get_data(as_text=True)
                    for pat in TECHNICAL_LEAK_PATTERNS:
                        if pat.search(text):
                            failures.append((role, path, f'LEAK:{pat.pattern}'))
                            break
                db.session.rollback()

        assert not failures, (
            f'{len(failures)} page(s) failed E2E (rendered {rendered}/{len(rules)}):\n'
            + '\n'.join(f'  [{r}] {p} -> {why}' for r, p, why in failures)
        )

    def test_migrated_dashboards_emit_unified_header(self, app, test_tenant, db):
        """Spot-check that key migrated staff pages render the unified header."""
        checks = [
            ('lab', '/lab/worklist', 'clinical-page-header'),
            ('radiology', '/radiology/requests', 'clinical-page-header'),
            ('emergency', '/emergency/emergency-visits', 'clinical-page-header'),
            ('pharmacist', '/medication/list', 'clinical-page-header'),
        ]
        missing = []
        for role, path, marker in checks:
            client = app.test_client()
            _login_as(client, test_tenant, role, db)
            resp = client.get(path, follow_redirects=False)
            if resp.status_code != 200:
                continue  # module may be gated for this tenant profile; covered elsewhere
            if marker not in resp.get_data(as_text=True):
                missing.append((path, marker))
        assert not missing, missing


# ── Static integrity: every template, button, link, and asset reference ──
from pathlib import Path  # noqa: E402

_TEMPLATES_ROOT = Path(__file__).parent.parent / 'templates'
_STATIC_ROOT = Path(__file__).parent.parent / 'static'

# url_for('endpoint', ...) — capture literal endpoint name (skip variable endpoints)
_URL_FOR_RE = re.compile(r"url_for\(\s*['\"]([a-zA-Z0-9_.]+)['\"]")
# url_for('static', filename='css/x.css') — capture literal static filename
_STATIC_RE = re.compile(
    r"url_for\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"{}]+)['\"]\s*\)"
)


def _iter_templates():
    for path in _TEMPLATES_ROOT.rglob('*.html'):
        yield path, path.relative_to(_TEMPLATES_ROOT).as_posix()


class TestFrontendStaticIntegrity:
    """Exhaustive, fast checks over EVERY template — no exclusions."""

    def test_every_template_compiles(self, app):
        errors = []
        with app.app_context():
            for _path, rel in _iter_templates():
                try:
                    app.jinja_env.get_template(rel)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f'{rel}: {type(exc).__name__}: {str(exc)[:160]}')
        assert not errors, 'templates failed to compile:\n' + '\n'.join(errors)

    def test_every_url_for_endpoint_is_registered(self, app):
        """Every link/button/form target (url_for) resolves to a real endpoint."""
        known = set(app.url_map._rules_by_endpoint.keys())
        missing = []
        for path, rel in _iter_templates():
            text = path.read_text(encoding='utf-8')
            for ep in _URL_FOR_RE.findall(text):
                if ep == 'static':
                    continue
                if ep not in known:
                    missing.append(f'{rel}: url_for(\'{ep}\') — endpoint not registered')
        assert not missing, 'broken link/button endpoints:\n' + '\n'.join(sorted(set(missing)))

    def test_every_static_asset_reference_exists(self, app):
        """Every literal url_for('static', filename=...) points to a real file."""
        missing = []
        for path, rel in _iter_templates():
            text = path.read_text(encoding='utf-8')
            for filename in _STATIC_RE.findall(text):
                if (_STATIC_ROOT / filename).is_file():
                    continue
                missing.append(f'{rel}: static/{filename} — file not found')
        assert not missing, 'broken static asset references:\n' + '\n'.join(sorted(set(missing)))
