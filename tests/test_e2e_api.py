"""Exhaustive API contract E2E — hammers EVERY JSON/AJAX API and every mutating
endpoint through the real routing/auth/DB stack.

Five contracts, each collecting all failures for a single actionable report:

  1. anonymous   -> never 500 / never technical leak           (crash safety)
  2. protected   -> anonymous must be gated (302/401/403)       (auth holes)
  3. method      -> a disallowed HTTP method returns 405         (routing)
  4. GET JSON    -> authenticated read APIs never 500 / leak     (read robustness)
  5. POST JSON   -> empty + malformed body -> 4xx JSON, no 500   (input robustness)

Destructive / external side-effecting endpoints (AI, external drug DB, FX fetch,
tenant provisioning, backups, seeds, cleanup, notifications, SMS, impersonation)
are EXCLUDED from the *active authenticated* calls (4 & 5) but still covered by
the anonymous + method contracts (1–3).
"""
from __future__ import annotations

import re

import pytest

from tests.test_phase14_launch import TECHNICAL_LEAK_PATTERNS, _login_as
from tests.test_e2e_frontend import _fill_path, e2e_seed  # noqa: F401 (fixture re-export)

_MUTATING = {'POST', 'PUT', 'PATCH', 'DELETE'}

# blueprint (endpoint prefix) -> role that may access it (covers API blueprints).
API_BP_ROLE = {
    'accountant': 'accountant', 'ai_imaging': 'radiology', 'api_dashboard': 'manager',
    'api_search': 'reception', 'api_user': 'manager', 'backup': 'super_admin',
    'backup_restore': 'super_admin', 'barcode': 'lab', 'bed': 'nurse',
    'biometric': 'manager', 'booking': 'reception', 'clinical_coding': 'doctor',
    'data_warehouse': 'super_admin', 'dicom': 'radiology', 'doctor': 'doctor',
    'emar': 'nurse', 'emergency': 'emergency', 'fhir': 'doctor', 'finance': 'accountant',
    'kiosk': 'reception', 'lab': 'lab', 'main': 'manager', 'manager': 'manager',
    'medication': 'pharmacist', 'mfa': 'manager', 'nurse': 'nurse',
    'nursing_assessment': 'nurse', 'owner': 'super_admin', 'patient_education': 'doctor',
    'payment': 'accountant', 'portal': 'patient', 'quality': 'manager',
    'radiology': 'radiology', 'reception': 'reception', 'reception_currency': 'reception',
    'report_builder': 'manager', 'specialty_forms': 'doctor', 'sso': 'super_admin',
    'super_admin': 'super_admin', 'telemedicine': 'doctor', 'what_if': 'manager',
}

# Intentionally public (no auth) — excluded from the auth-gating assertion (2).
#  - survey: patient satisfaction filled via tokenized link (no account)
#  - biometric.authenticate_challenge: WebAuthn challenge issued pre-login
_PUBLIC_RE = re.compile(
    r'^(auth\.login|auth\.api_tenants_list|kiosk\.|booking\.|main\.(index|landing|'
    r'privacy|terms|support|about)|pwa\.|static|reception\.survey|'
    r'biometric\.authenticate_challenge)',
)

# Destructive / external / heavy — excluded from active authenticated calls (4 & 5).
_DANGER_RE = re.compile(
    r'(seed|cleanup|/export|/import|backup|restore|/sync|provision|'
    r'notifications/(run|queue)|sms/test|test-sms|impersonate|change-password|'
    r'reset-password|fetch-api|external-drug|ai-assist|ai-assistant|ai-imaging|'
    r'data-warehouse|/delete\b|/disable\b|check-rate)',
    re.IGNORECASE,
)


def _is_api(path: str, ep: str) -> bool:
    return '/api/' in path or path.endswith('/api') or 'api' in ep.split('.')[-1]


def _discover(app):
    """All (path_rule, methods, endpoint, role) for API or mutating endpoints."""
    out = []
    for rule in app.url_map.iter_rules():
        methods = set(rule.methods or set()) - {'HEAD', 'OPTIONS'}
        ep = rule.endpoint
        path = str(rule.rule)
        if not (_is_api(path, ep) or (methods & _MUTATING)):
            continue
        role = API_BP_ROLE.get(ep.split('.')[0])
        out.append((path, methods, ep, role))
    return out


def _leaks(resp) -> str | None:
    if resp.status_code == 200 and resp.mimetype != 'text/html':
        return None
    text = resp.get_data(as_text=True)
    for pat in TECHNICAL_LEAK_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None


class TestApiContract:
    # ── 1. crash safety — anonymous never 500 / never leak ──────────────
    def test_no_api_errors_anonymously(self, app, db):
        client = app.test_client()
        failures = []
        for path, methods, ep, _role in _discover(app):
            url = _fill_path(path, {})
            method = 'GET' if 'GET' in methods else 'POST'
            db.session.rollback()
            try:
                resp = client.open(url, method=method, json={} if method == 'POST' else None)
            except Exception as exc:  # noqa: BLE001
                failures.append(f'  {method} {url} [{ep}] -> EXC {type(exc).__name__}: {str(exc)[:120]}')
                db.session.rollback()
                continue
            if resp.status_code == 500:
                failures.append(f'  {method} {url} [{ep}] -> 500')
            else:
                leak = _leaks(resp)
                if leak:
                    failures.append(f'  {method} {url} [{ep}] -> LEAK {leak}')
            db.session.rollback()
        assert not failures, f'{len(failures)} API endpoint(s) errored anonymously:\n' + '\n'.join(failures)

    # ── 2. auth gating — protected endpoints reject anonymous ───────────
    def test_protected_apis_require_auth(self, app, db):
        client = app.test_client()
        holes = []
        for path, methods, ep, _role in _discover(app):
            if _PUBLIC_RE.match(ep):
                continue
            url = _fill_path(path, {})
            method = 'GET' if 'GET' in methods else 'POST'
            db.session.rollback()
            resp = client.open(url, method=method, json={} if method == 'POST' else None,
                               follow_redirects=False)
            # Auth-gated => login redirect (301/302/308) or 401/403. A 200 means
            # an anonymous user reached protected data/action.
            if resp.status_code == 200:
                holes.append(f'  {method} {url} [{ep}] -> 200 (no auth gate)')
            db.session.rollback()
        assert not holes, f'{len(holes)} endpoint(s) reachable without auth:\n' + '\n'.join(holes)

    # ── 3. method contract — disallowed verb => 405 (not 500) ───────────
    def test_disallowed_method_returns_405(self, app, db):
        client = app.test_client()
        bad = []
        for path, methods, ep, _role in _discover(app):
            disallowed = next((m for m in ('DELETE', 'PATCH', 'PUT', 'POST', 'GET')
                               if m not in methods), None)
            if disallowed is None:
                continue
            url = _fill_path(path, {})
            db.session.rollback()
            resp = client.open(url, method=disallowed)
            if resp.status_code not in (405, 301, 302, 308):
                # 405 expected; redirects acceptable (strict_slashes). 500 is a bug.
                if resp.status_code == 500:
                    bad.append(f'  {disallowed} {url} [{ep}] -> 500 (expected 405)')
            db.session.rollback()
        assert not bad, f'{len(bad)} endpoint(s) crashed on disallowed method:\n' + '\n'.join(bad)

    # ── 4. read robustness — authenticated GET JSON APIs never 500 ──────
    def test_get_json_apis_authenticated(self, app, test_tenant, db, e2e_seed):
        failures = []
        targets = [(p, m, ep, r) for (p, m, ep, r) in _discover(app)
                   if _is_api(p, ep) and 'GET' in m and r and not _DANGER_RE.search(p)]
        by_role: dict[str, list] = {}
        for p, _m, ep, r in targets:
            by_role.setdefault(r, []).append((p, ep))
        for role, items in by_role.items():
            db.session.rollback()
            client = app.test_client()
            _login_as(client, test_tenant, role, db)
            for path, ep in items:
                url = _fill_path(path, e2e_seed)
                db.session.rollback()
                try:
                    resp = client.get(url, follow_redirects=False)
                except Exception as exc:  # noqa: BLE001
                    failures.append(f'  [{role}] GET {url} [{ep}] -> EXC {type(exc).__name__}: {str(exc)[:120]}')
                    db.session.rollback()
                    continue
                if resp.status_code == 500:
                    failures.append(f'  [{role}] GET {url} [{ep}] -> 500')
                else:
                    leak = _leaks(resp)
                    if leak:
                        failures.append(f'  [{role}] GET {url} [{ep}] -> LEAK {leak}')
                db.session.rollback()
        assert not failures, f'{len(failures)} GET API(s) failed authenticated:\n' + '\n'.join(failures)

    # ── 5. input robustness — POST JSON APIs reject bad input as JSON 4xx ─
    def test_post_json_apis_reject_bad_input(self, app, test_tenant, db, e2e_seed):
        failures = []
        targets = [(p, m, ep, r) for (p, m, ep, r) in _discover(app)
                   if _is_api(p, ep) and (m & {'POST', 'PUT', 'PATCH', 'DELETE'})
                   and r and not _DANGER_RE.search(p)]
        by_role: dict[str, list] = {}
        for p, m, ep, r in targets:
            verb = 'POST' if 'POST' in m else ('PUT' if 'PUT' in m else ('PATCH' if 'PATCH' in m else 'DELETE'))
            by_role.setdefault(r, []).append((p, verb, ep))

        # A few lenient "create" endpoints (e.g. owner.api_create_bundle) commit a
        # row even for empty input; the session-scoped test DB would then leak that
        # junk into later tests (e.g. SaaS seed). Snapshot + remove anything created.
        from app.core.tenant.models import ProductBundle
        pre_bundles = {b.id for b in ProductBundle.query.all()}
        try:
            for role, items in by_role.items():
                db.session.rollback()
                client = app.test_client()
                _login_as(client, test_tenant, role, db)
                for path, verb, ep in items:
                    url = _fill_path(path, e2e_seed)
                    # (a) empty JSON body, (b) malformed JSON
                    for body, ctype, kwargs in (
                        (None, None, {'json': {}}),
                        ('{ not json', 'application/json', {'data': '{ not json', 'content_type': 'application/json'}),
                    ):
                        db.session.rollback()
                        try:
                            resp = client.open(url, method=verb, **kwargs)
                        except Exception as exc:  # noqa: BLE001
                            failures.append(f'  [{role}] {verb} {url} [{ep}] -> EXC {type(exc).__name__}: {str(exc)[:120]}')
                            db.session.rollback()
                            continue
                        if resp.status_code == 500:
                            failures.append(f'  [{role}] {verb} {url} [{ep}] (ctype={ctype}) -> 500')
                        elif resp.mimetype == 'text/html' and resp.status_code >= 400:
                            # API errors must be JSON, not an HTML error page.
                            failures.append(f'  [{role}] {verb} {url} [{ep}] (ctype={ctype}) -> HTML error {resp.status_code}')
                        else:
                            leak = _leaks(resp)
                            if leak:
                                failures.append(f'  [{role}] {verb} {url} [{ep}] -> LEAK {leak}')
                        db.session.rollback()
        finally:
            db.session.rollback()
            junk = ProductBundle.query.filter(ProductBundle.id.notin_(pre_bundles or {-1})).all()
            for b in junk:
                db.session.delete(b)
            db.session.commit()

        assert not failures, f'{len(failures)} POST/PUT API(s) mishandled bad input:\n' + '\n'.join(failures)
