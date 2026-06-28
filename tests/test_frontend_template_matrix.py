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
    ('/reception/patients', 'reception'),
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
        name = (attrs_dict.get('name') or '').strip()
        if tag == 'input':
            itype = (attrs_dict.get('type') or 'text').lower()
            if itype in _SKIP_INPUT_TYPES:
                return
            if 'disabled' in attrs_dict and not name:
                return
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
        self.hrefs: list[tuple[str, dict[str, str]]] = []
        self.actions: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: (v or '') for k, v in attrs}
        if tag == 'a' and 'href' in attrs_dict:
            self.hrefs.append((attrs_dict['href'].strip(), attrs_dict))
        elif tag == 'form' and 'action' in attrs_dict:
            self.actions.append(attrs_dict['action'].strip())


def _is_allowed_placeholder_href(href: str, attrs: dict[str, str]) -> bool:
    """Bootstrap toggles / JS-driven anchors may use href='#'."""
    if href != '#':
        return False
    return any(attrs.get(k) for k in (
        'data-bs-toggle', 'data-toggle', 'data-bs-target', 'data-target',
        'onclick', 'role',
    ))


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
    from app.core.tenant.models import Tenant

    id_map = e2e_seed or {}
    tenant_id = test_tenant.id
    seen: set[str] = set()
    for path, role in CORE_RENDER_ROUTES:
        if path in seen:
            continue
        seen.add(path)
        tenant = db.session.get(Tenant, tenant_id)
        client = app.test_client()
        _login_as(client, tenant, role, db)
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
    """True if path matches any registered rule for GET/HEAD/POST."""
    adapter = app.url_map.bind('')
    for method in ('GET', 'HEAD', 'POST'):
        try:
            adapter.match(path, method=method)
            return True
        except RequestRedirect:
            return True
        except Exception:
            continue
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


# ── Phase 2: Dead links & static asset crawler ──────────────────────


def _bad_href_reason(href: str) -> str | None:
    href = (href or '').strip()
    if href in _BAD_HREF_EXACT:
        return f'empty or placeholder href={href!r}'
    if href.lower().startswith('javascript:'):
        return 'javascript: href'
    return None


def _resolve_link(app, href: str, base_path: str) -> tuple[bool, str]:
    """Return (ok, reason) for an internal link — url_map first, then HTTP."""
    reason = _bad_href_reason(href)
    if reason:
        return False, reason
    path = _normalize_internal_path(href, base_path)
    if path is None:
        return True, 'external'
    if _SKIP_LINK_RE.search(path):
        return True, 'skipped'
    if _path_matches_url_map(app, path):
        return True, 'url_map'
    return False, 'unregistered path'


class TestLinkCrawler:
    """Extract hrefs/actions from rendered pages; validate routes and inventory."""

    def test_no_bad_hrefs_on_core_pages(self, app, test_tenant, db, e2e_seed):
        offenders = []
        for path, role, status, html in _render_core_pages(app, test_tenant, db, e2e_seed):
            if status != 200:
                continue
            extractor = _LinkExtractor()
            extractor.feed(html)
            for href, attrs in extractor.hrefs:
                if _is_allowed_placeholder_href(href, attrs):
                    continue
                bad = _bad_href_reason(href)
                if bad:
                    offenders.append(f'{path}: <a href={href!r}> — {bad}')
        assert not offenders, '\n'.join(offenders)

    def test_internal_links_resolve_on_core_pages(self, app, test_tenant, db, e2e_seed):
        failures = []
        checked: set[str] = set()
        for path, role, status, html in _render_core_pages(app, test_tenant, db, e2e_seed):
            if status != 200:
                continue
            extractor = _LinkExtractor()
            extractor.feed(html)
            for href, attrs in extractor.hrefs:
                if _is_allowed_placeholder_href(href, attrs):
                    continue
                norm = _normalize_internal_path(href, path)
                if norm is None or norm in checked or _SKIP_LINK_RE.search(href):
                    continue
                checked.add(norm)
                ok, reason = _resolve_link(app, href, path)
                if not ok:
                    failures.append(f'{path} -> {href!r}: {reason}')
            for href in extractor.actions:
                norm = _normalize_internal_path(href, path)
                if norm is None or norm in checked or _SKIP_LINK_RE.search(href):
                    continue
                checked.add(norm)
                ok, reason = _resolve_link(app, href, path)
                if not ok:
                    failures.append(f'{path} action -> {href!r}: {reason}')
        assert not failures, '\n'.join(failures[:40])

    def test_no_legacy_sqlite_or_single_tenant_refs(self, app, test_tenant, db, e2e_seed):
        leaks = []
        for path, role, status, html in _render_core_pages(app, test_tenant, db, e2e_seed):
            if status != 200:
                continue
            for pat in _LEGACY_REF_PATTERNS:
                if pat.search(html):
                    leaks.append(f'{path}: legacy ref {pat.pattern}')
        assert not leaks, '\n'.join(leaks)

    def test_route_inventory_endpoints_registered(self, app):
        inventory = json.loads(_ROUTE_INVENTORY.read_text(encoding='utf-8'))
        known = set(app.url_map._rules_by_endpoint.keys())
        missing = [
            f'{r["endpoint"]} ({r["path"]})'
            for r in inventory['routes']
            if r['endpoint'] not in known
        ]
        assert not missing, (
            f'{len(missing)} route_inventory endpoints not in url_map:\n'
            + '\n'.join(missing[:30])
        )

    def test_route_inventory_paths_match_url_map(self, app):
        inventory = json.loads(_ROUTE_INVENTORY.read_text(encoding='utf-8'))
        registered_paths = {str(rule.rule) for rule in app.url_map.iter_rules()}
        missing_paths = [
            r['path'] for r in inventory['routes']
            if r['path'] not in registered_paths
        ]
        assert not missing_paths, (
            f'{len(missing_paths)} inventory paths absent from url_map:\n'
            + '\n'.join(missing_paths[:30])
        )

    def test_discovered_get_routes_in_inventory(self, app):
        """Spot-check that page-bearing blueprints appear in route_inventory."""
        inventory = json.loads(_ROUTE_INVENTORY.read_text(encoding='utf-8'))
        inv_paths = {r['path'] for r in inventory['routes']}
        sample_rules = _discover_pages(app)[:50]
        missing = [p for p, _ in sample_rules if p not in inv_paths]
        assert not missing, f'discovered routes missing from inventory: {missing[:20]}'


# ── Phase 3: JavaScript validation ──────────────────────────────────

_JS_FETCH_PATTERNS = [
    re.compile(r'\bfetch\s*\('),
    re.compile(r'window\.fetch'),
    re.compile(r'\.then\s*\('),
]


def _iter_js_modules():
    for path in sorted(_STATIC_JS.glob('*.js')):
        yield path
    pages = _STATIC_JS / 'pages'
    if pages.is_dir():
        for path in sorted(pages.rglob('*.js')):
            yield path


def _node_syntax_check(path: Path) -> str | None:
    try:
        proc = subprocess.run(
            ['node', '--check', str(path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f'{type(exc).__name__}'
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or 'syntax error')[:200]
    return None


class TestJavaScriptValidation:
    """Structural audit of static/js modules and global error handling."""

    def test_js_modules_parse_without_syntax_errors(self):
        errors = []
        node_missing = False
        for js_path in _iter_js_modules():
            rel = js_path.relative_to(ROOT).as_posix()
            text = js_path.read_text(encoding='utf-8', errors='ignore')
            if '<script' in text or '<!DOCTYPE' in text:
                continue
            err = _node_syntax_check(js_path)
            if err == 'FileNotFoundError':
                node_missing = True
                break
            if err:
                errors.append(f'{rel}: {err}')
        if node_missing:
            for js_path in _iter_js_modules():
                text = js_path.read_text(encoding='utf-8', errors='ignore')
                if text.count('{') != text.count('}'):
                    errors.append(f'{js_path.relative_to(ROOT)}: brace mismatch')
                if text.count('(') != text.count(')'):
                    errors.append(f'{js_path.relative_to(ROOT)}: paren mismatch')
        assert not errors, 'JS syntax issues:\n' + '\n'.join(errors[:20])

    def test_js_modules_use_fetch_or_dom_patterns(self):
        """Spot-check top-level static/js modules reference fetch or DOM APIs."""
        static_only = {'enums.js', 'digits-ar.js', 'flash.js', 'csrf.js'}
        missing = []
        for js_path in sorted(_STATIC_JS.glob('*.js')):
            if js_path.name in static_only:
                continue
            text = js_path.read_text(encoding='utf-8', errors='ignore')
            if not any(p.search(text) for p in _JS_FETCH_PATTERNS):
                if not re.search(r'document\.|addEventListener|window\.', text):
                    missing.append(js_path.relative_to(ROOT).as_posix())
        assert not missing, f'JS modules with no fetch/DOM patterns: {missing[:15]}'

    def test_base_html_includes_global_error_handler_script(self):
        base = (ROOT / 'templates' / 'base.html').read_text(encoding='utf-8')
        assert 'global-errors.js' in base
        assert 'api-feedback.js' in base
        assert base.index('api-feedback.js') < base.index('global-errors.js')
        assert base.index('global-errors.js') < base.index('base.js')

    def test_global_errors_defines_handlers_and_fetch_wrapper(self):
        src = (_STATIC_JS / 'global-errors.js').read_text(encoding='utf-8')
        assert 'onerror' in src
        assert 'onunhandledrejection' in src
        assert '__wrapFetchEntitlement' in src
        assert '402' in src and '403' in src
        assert 'entitlement-lock' in src
        assert 'notify' in src

    def test_base_js_applies_entitlement_fetch_wrapper(self):
        src = (_STATIC_JS / 'base.js').read_text(encoding='utf-8')
        assert '__wrapFetchEntitlement' in src
        assert 'X-CSRFToken' in src

    def test_entitlement_lock_partial_exists(self):
        partial = ROOT / 'templates' / 'partials' / '_entitlement_lock.html'
        assert partial.is_file()
        text = partial.read_text(encoding='utf-8')
        assert 'entitlement-lock-screen' in text
        assert 'capability_key' in text or 'capability' in text

