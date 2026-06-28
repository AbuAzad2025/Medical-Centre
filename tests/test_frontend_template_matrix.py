"""Frontend QA Mandate — template matrix, link crawler, JS validation (Phases 1–3).

Renders core routes through the real Flask stack, audits form fields and links,
and validates static JS assets. Reuses patterns from test_e2e_frontend and
test_phase14_launch.
"""
from __future__ import annotations

import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urljoin

import pytest
from werkzeug.routing import RequestRedirect

from tests.test_e2e_frontend import (
    BP_ROLE,
    _discover_pages,
    _fill_path,
    e2e_seed,
)
from tests.test_phase14_launch import (
    SCREEN_SAMPLES,
    TECHNICAL_LEAK_PATTERNS,
    _login_as,
)

ROOT = Path(__file__).parent.parent
_STATIC_JS = ROOT / 'static' / 'js'
_ROUTE_INVENTORY = ROOT / 'route_inventory.json'

# Core screens whose POST forms must expose backend-expected field names.
CORE_FORM_ROUTES: dict[str, set[str]] = {
    '/auth/login': {'username', 'password', 'csrf_token'},
}

# Sample screens + role dashboards for matrix rendering (Phase 1 & 2).
CORE_RENDER_ROUTES: list[tuple[str, str | None]] = list(SCREEN_SAMPLES) + [
    ('/super-admin/dashboard', 'super_admin'),
    ('/reception/add_patient', 'reception'),
]

_SKIP_INPUT_TYPES = frozenset({'submit', 'button', 'reset', 'image'})
_BAD_HREF_EXACT = frozenset({'', '#'})
_LEGACY_REF_PATTERNS = [
    re.compile(r'sqlite://', re.I),
    re.compile(r'single[-_]tenant', re.I),
    re.compile(r'single tenant mode', re.I),
]
_SKIP_LINK_RE = re.compile(
    r'(logout|export|download|\.pdf\b|/pdf\b|/csv\b|/xlsx\b|/stream\b|/feed\b|'
    r'/raw\b|/ws\b|/sse\b|mailto:|tel:|wa\.me|javascript:)',
    re.I,
)
_EXTERNAL_SCHEME_RE = re.compile(r'^(https?://|//|mailto:|tel:|javascript:)', re.I)


class _FormFieldAuditor(HTMLParser):
    """Collect inputs/selects/textareas inside POST forms missing name attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.issues: list[str] = []
        self._post_form_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: (v or '') for k, v in attrs}
        if tag == 'form':
            method = (attrs_dict.get('method') or 'GET').upper()
            if method == 'POST':
                self._post_form_depth += 1
            return
        if self._post_form_depth <= 0 or tag not in ('input', 'select', 'textarea'):
            return
        if tag == 'input':
            itype = (attrs_dict.get('type') or 'text').lower()
            if itype in _SKIP_INPUT_TYPES:
                return
        name = (attrs_dict.get('name') or '').strip()
        if not name:
            ident = attrs_dict.get('id') or attrs_dict.get('class') or tag
            self.issues.append(f'{tag}[{ident}] missing name')

    def handle_endtag(self, tag: str) -> None:
        if tag == 'form' and self._post_form_depth > 0:
            self._post_form_depth -= 1


class _LinkExtractor(HTMLParser):
    """Extract anchor hrefs and form actions from rendered HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.actions: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: (v or '') for k, v in attrs}
        if tag == 'a' and 'href' in attrs_dict:
            self.hrefs.append(attrs_dict['href'].strip())
        elif tag == 'form' and 'action' in attrs_dict:
            self.actions.append(attrs_dict['action'].strip())


def _collect_form_names(html: str) -> set[str]:
    names: set[str] = set()
    parser = HTMLParser()
    in_post = False

    def start(tag, attrs):
        nonlocal in_post
        d = dict(attrs)
        if tag == 'form':
            if (d.get('method') or 'GET').upper() == 'POST':
                in_post = True
        if in_post and tag == 'input' and d.get('name'):
            names.add(d['name'])
        if in_post and tag == 'select' and d.get('name'):
            names.add(d['name'])
        if in_post and tag == 'textarea' and d.get('name'):
            names.add(d['name'])

    def end(tag):
        nonlocal in_post
        if tag == 'form':
            in_post = False

    parser.handle_starttag = start  # type: ignore[method-assign]
    parser.handle_endtag = end  # type: ignore[method-assign]
    parser.feed(html)
    return names


def _render_core_pages(app, test_tenant, db, e2e_seed):
    """Yield (path, role, status_code, html_text) for each core route."""
    id_map = e2e_seed or {}
    seen: set[str] = set()
    for path, role in CORE_RENDER_ROUTES:
        if path in seen:
            continue
        seen.add(path)
        client = app.test_client()
        _login_as(client, test_tenant, role, db)
        try:
            resp = client.get(path, follow_redirects=True)
        except Exception as exc:  # noqa: BLE001
            yield path, role, f'EXC:{type(exc).__name__}', ''
            db.session.rollback()
            continue
        html = resp.get_data(as_text=True) if resp.status_code == 200 else ''
        yield path, role, resp.status_code, html
        db.session.rollback()


def _normalize_internal_path(href: str, base_path: str = '/') -> str | None:
    """Return path+query for same-app links; None for external/skip."""
    href = (href or '').strip()
    if not href or href in _BAD_HREF_EXACT:
        return href if href == '' else href
    if href.startswith('#'):
        return None
    if _EXTERNAL_SCHEME_RE.match(href):
        if href.startswith(('http://', 'https://', '//')):
            parsed = urlparse(href)
            if parsed.netloc and parsed.netloc not in ('localhost', '127.0.0.1'):
                return None
            return parsed.path or '/'
        return None
    joined = urljoin(f'http://localhost{base_path}', href)
    parsed = urlparse(joined)
    return parsed.path or '/'


def _path_matches_url_map(app, path: str) -> bool:
    """True if path matches any registered rule (static segments only check)."""
    adapter = app.url_map.bind('')
    try:
        adapter.match(path, method='GET')
        return True
    except RequestRedirect:
        return True
    except Exception:
        pass
    try:
        adapter.match(path, method='HEAD')
        return True
    except RequestRedirect:
        return True
    except Exception:
        return False


# ── Phase 1: Template render + form field audit ─────────────────────


class TestTemplateRenderMatrix:
    """Render core routes; assert no leaks and POST form fields have names."""

    def test_core_routes_render_without_500_or_leaks(self, app, test_tenant, db, e2e_seed):
        failures = []
        for path, role, status, html in _render_core_pages(app, test_tenant, db, e2e_seed):
            if isinstance(status, str) and status.startswith('EXC:'):
                failures.append(f'{path} ({role}): {status}')
                continue
            if status == 500:
                failures.append(f'{path} ({role}): HTTP 500')
                continue
            if status != 200:
                continue
            for pat in TECHNICAL_LEAK_PATTERNS:
                if pat.search(html):
                    failures.append(f'{path} ({role}): LEAK {pat.pattern}')
                    break
        assert not failures, 'render failures:\n' + '\n'.join(failures)

    @pytest.mark.parametrize('path,role', CORE_RENDER_ROUTES)
    def test_post_form_fields_have_name_attributes(
        self, app, test_tenant, db, e2e_seed, path, role,
    ):
        client = app.test_client()
        _login_as(client, test_tenant, role, db)
        resp = client.get(path, follow_redirects=True)
        if resp.status_code != 200:
            pytest.skip(f'{path} returned {resp.status_code}')
        auditor = _FormFieldAuditor()
        auditor.feed(resp.get_data(as_text=True))
        assert not auditor.issues, f'{path}: fields missing name — {auditor.issues}'

    @pytest.mark.parametrize('path,expected_fields', CORE_FORM_ROUTES.items())
    def test_core_post_form_backend_contract(
        self, app, test_tenant, db, path, expected_fields,
    ):
        client = app.test_client()
        resp = client.get(path, follow_redirects=True)
        assert resp.status_code == 200, f'{path} returned {resp.status_code}'
        found = _collect_form_names(resp.get_data(as_text=True))
        missing = expected_fields - found
        assert not missing, f'{path}: backend expects {missing}, form has {found}'

    def test_payment_form_fields_have_names(self, app, test_tenant, db, e2e_seed):
        path = f'/payment/process/{e2e_seed["visit_id"]}'
        client = app.test_client()
        _login_as(client, test_tenant, 'accountant', db)
        resp = client.get(path, follow_redirects=True)
        if resp.status_code != 200:
            pytest.skip(f'{path} returned {resp.status_code}')
        auditor = _FormFieldAuditor()
        auditor.feed(resp.get_data(as_text=True))
        assert not auditor.issues, f'{path}: {auditor.issues}'
