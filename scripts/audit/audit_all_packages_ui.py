"""Read-only UI audit of all 23 package tenants against http://localhost:8010.

Methodology (same as package 1):
  * real browser login as the tenant admin through /auth/login (tenant slug selected)
  * walk the non-parameterised GET pages of every ENABLED module + shared pages
  * for every page: status, final URL, title, visible links/buttons to disabled
    modules, literal '#' hrefs, dead `_()` onclick handlers, console errors
  * 1280px dashboard screenshot per tenant

Outputs (only files under docs/PAGE_AUDIT/):
  docs/PAGE_AUDIT/all_packages_ui_audit.json
  docs/PAGE_AUDIT/all_packages_ui/<tenant_slug>.png
  docs/PAGE_AUDIT/all_packages_ui_run.log
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = os.environ.get('AUDIT_BASE_URL', 'http://localhost:8010')
PASSWORD = 'Audit@2026Pass'
AUDIT_DIR = os.path.join(ROOT, 'docs', 'PAGE_AUDIT')
SHOTS = os.path.join(AUDIT_DIR, 'all_packages_ui')
OUT = os.path.join(AUDIT_DIR, 'all_packages_ui_audit.json')
LOG = os.path.join(AUDIT_DIR, 'all_packages_ui_run.log')
os.makedirs(SHOTS, exist_ok=True)

# Source: scripts/audit/provision_all_packages.py (PACKAGES list) — the profile
# selected when each package tenant was created.
PROFILE_BY_PACKAGE = {
    'private_doctor_clinic': 'private_doctor_clinic',
    'doctor_clinic_reception': 'private_doctor_clinic',
    'doctor_clinic_full': 'private_doctor_clinic',
    'small_clinic': 'small_clinic',
    'clinic_with_lab': 'small_clinic',
    'clinic_with_radiology': 'small_clinic',
    'clinic_with_lab_radiology': 'small_clinic',
    'standalone_lab': 'standalone_lab',
    'lab_with_reception': 'standalone_lab',
    'standalone_radiology': 'standalone_radiology',
    'radiology_with_reception': 'standalone_radiology',
    'standalone_pharmacy': 'standalone_pharmacy',
    'standalone_emergency': 'multi_department_center',
    'walkin_clinic': 'small_clinic',
    'urgent_care': 'multi_department_center',
    'diagnostic_center': 'standalone_lab',
    'community_clinic': 'multi_department_center',
    'nursing_home': 'multi_department_center',
    'multi_department_center': 'multi_department_center',
    'polyclinic': 'multi_department_center',
    'hospital': 'multi_department_center',
    'billing_only': 'custom',
    'custom': 'custom',
}

# First URL segment -> product module (from MODULE_REGISTRY route_prefixes and
# inventory.json).  Used to decide whether a visible control points at a module
# that is NOT enabled for the tenant.
PREFIX_MODULE = {
    'reception': 'reception',
    'doctor': 'doctor',
    'lab': 'lab',
    'dicom': 'radiology',
    'radiology': 'radiology',
    'medication': 'pharmacy',
    'pharmacy': 'pharmacy',
    'emergency': 'emergency',
    'nurse': 'nursing',
    'emar': 'nursing',
    'bed': 'nursing',
    'or': 'nursing',
    'nursing-assessment': 'nursing',
    'inpatient': 'nursing',
    'order-sets': 'nursing',
    'finance': 'billing',
    'accountant': 'billing',
    'payment': 'billing',
    'barcode': 'inventory',
    'booking': 'appointments',
    'manager': 'reporting',
    'report-builder': 'reporting',
    'data-warehouse': 'reporting',
    'population-health': 'reporting',
    'quality': 'reporting',
    'what-if': 'reporting',
    'sso': 'integration',
    'ai-imaging': 'ai_imaging',
    'portal': 'portal',
    'inbox': 'inbox',
    'dashboard': 'dashboard',
    'settings': 'settings',
}
SHARED_MODULES = {'inbox', 'dashboard', 'settings', 'home', 'auth', 'static'}
SKIP_PREFIXES = (
    '/api/',
    '/owner/',
    '/super-admin/',
    '/auth/',
    '/static/',
    '/test/',
    '/health',
    '/favicon',
    '/set-language/',
    '/package-restricted',
)

_log_fh = open(LOG, 'w', encoding='utf-8')  # noqa: SIM115 - reused by log()


def log(msg: str) -> None:
    text = f'{datetime.now():%H:%M:%S} {msg}'
    print(text, flush=True)
    _log_fh.write(text + '\n')
    _log_fh.flush()


def load_json(name: str):
    with open(os.path.join(AUDIT_DIR, name), encoding='utf-8') as fh:
        return json.load(fh)


def build_paths():
    """Representative, non-parameterised GET page path per enabled module."""
    routes = load_json('inventory.json')['routes']
    by_module = defaultdict(list)
    for r in routes:
        path = r['path']
        if not r.get('is_get') or '<' in path or '/api/' in path:
            continue
        if path.startswith(SKIP_PREFIXES):
            continue
        if path.rstrip('/').endswith(('/export', '/pdf', '/download')):
            continue
        module = r.get('module') or ''
        if module in PREFIX_MODULE.values():
            by_module[module].append(path)
        else:
            first = path.strip('/').split('/')[0] if path.strip('/') else ''
            inferred = PREFIX_MODULE.get(first)
            if inferred:
                by_module[inferred].append(path)
    return {
        m: sorted(set(p), key=lambda p: (p.count('/'), len(p), p)) for m, p in by_module.items()
    }


def module_of(href: str, tenant_slug: str):
    """Return (module, has_tenant_prefix) for a visible internal href."""
    path = urlparse(href).path
    if not path.startswith('/'):
        return None, None
    prefixed = False
    if path.startswith(f'/t/{tenant_slug}/') or path == f'/t/{tenant_slug}':
        path = path[len(f'/t/{tenant_slug}') :] or '/'
        prefixed = True
    elif path.startswith('/t/'):
        # link to a different tenant — noteworthy but not a module classification
        return None, False
    if not path.startswith('/'):
        return None, prefixed
    first = path.strip('/').split('/')[0] if path.strip('/') else ''
    if not first:
        return 'home', prefixed
    return PREFIX_MODULE.get(first), prefixed


CONTROL_JS = """() => {
  const out = [];
  for (const e of document.querySelectorAll('a, button, [role="button"]')) {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (e.offsetParent === null && cs.position !== 'fixed') continue;
    const rect = e.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    const txt = (e.innerText || e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 60);
    const aria = (e.getAttribute('aria-label') || '').trim().slice(0, 60);
    const title = (e.getAttribute('title') || '').trim().slice(0, 60);
    out.push({
      tag: e.tagName,
      label: txt || aria || title || '(unlabelled)',
      href: (e.getAttribute('href') || '').slice(0, 160),
      onclick: (e.getAttribute('onclick') || '').slice(0, 120),
      cls: String(e.className || '').slice(0, 70)
    });
  }
  return out;
}"""

ERROR_MARKERS = (
    'Internal Server Error',
    'Traceback (most recent call last)',
    'حدث خطأ غير متوقع',
)


def login(pg, user: str, slug: str):
    """Try the real login form up to 3 times; return (ok, final_url, flash)."""
    last = ''
    for attempt in range(3):
        try:
            pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded', timeout=20000)
            pg.fill('#username', user)
            pg.fill('#password', PASSWORD)
            pg.select_option('#tenant_slug', slug)
            pg.click('button[type=submit]')
            pg.wait_for_timeout(900)
            if '/auth/login' not in pg.url:
                return True, pg.url, ''
            flash = ' | '.join(s.strip() for s in pg.locator('.flash-message').all_inner_texts())
            last = flash[:300] or f'still on login after attempt {attempt + 1}'
        except Exception as exc:  # noqa: BLE001
            last = f'{type(exc).__name__}: {str(exc)[:180]}'
    return False, pg.url, last


def scan_page(pg, path: str, module: str, tenant_slug: str, enabled: set[str]):
    """Navigate one page and return a compact record with issues only."""
    console_errors: list[str] = []
    console_errors.clear()

    def on_console(msg):
        if msg.type == 'error':
            console_errors.append(('console: ' + msg.text)[:300])

    def on_pageerror(exc):
        console_errors.append(('pageerror: ' + str(exc))[:300])

    pg.on('console', on_console)
    pg.on('pageerror', on_pageerror)
    status = None
    nav_error = ''
    try:
        resp = pg.goto(
            f'{BASE}/t/{tenant_slug}{path}', wait_until='domcontentloaded', timeout=15000
        )
        status = resp.status if resp else None
    except Exception as exc:  # noqa: BLE001
        nav_error = f'{type(exc).__name__}: {str(exc)[:160]}'
    final_url = pg.url
    try:
        title = pg.title()
    except Exception:  # noqa: BLE001
        title = ''
    issues: dict[str, list] = defaultdict(list)
    if nav_error:
        issues['navigation_error'].append(nav_error)
    if status not in (200, 302, None):
        issues['bad_status'].append({'status': status, 'path': path})
    try:
        body = pg.locator('body').inner_text()[:2500]
    except Exception:  # noqa: BLE001
        body = ''
    for marker in ERROR_MARKERS:
        if marker in body:
            issues['error_marker'].append(marker)
    try:
        controls = pg.evaluate(CONTROL_JS)
    except Exception as exc:  # noqa: BLE001
        controls = []
        issues['control_scan_error'].append(str(exc)[:160])
    for c in controls:
        label, href, onclick = c['label'], c['href'], c['onclick']
        if href == '#' or href.startswith('javascript:void'):
            issues['placeholder_href'].append({'label': label, 'href': href, 'cls': c['cls']})
        if '_(' in onclick:
            issues['dead_onclick'].append({'label': label, 'onclick': onclick, 'cls': c['cls']})
        if not href:
            continue
        target_module, prefixed = module_of(href, tenant_slug)
        if target_module and target_module not in SHARED_MODULES and target_module not in enabled:
            issues['disabled_module_link'].append(
                {'label': label, 'href': href, 'module': target_module}
            )
        elif target_module and target_module in SHARED_MODULES and not prefixed:
            if target_module != 'auth' and not href.startswith(('/auth/', '/static/')):
                issues['unprefixed_tenant_link'].append(
                    {'label': label, 'href': href, 'module': target_module}
                )
    pg.wait_for_timeout(60)
    if console_errors:
        # de-duplicate repeated identical messages on one page
        issues['console_error'].append(list(dict.fromkeys(console_errors))[:5])
    pg.remove_listener('console', on_console)
    pg.remove_listener('pageerror', on_pageerror)
    record = {
        'path': path,
        'module': module,
        'status': status,
        'final_url': final_url.replace(BASE, ''),
        'title': title,
    }
    if issues:
        record['issues'] = {k: v[:5] for k, v in issues.items()}
        record['issue_count'] = sum(len(v) for v in issues.values())
    return record


def main():
    started = time.time()
    tenants_meta = load_json('package_tenants.json')
    verification = {r['slug']: r for r in load_json('package_verification.json')['rows']}
    paths_by_module = build_paths()
    log(f'base={BASE} tenants={len(tenants_meta)} modules_with_paths={len(paths_by_module)}')

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        pg = browser.new_page(viewport={'width': 1280, 'height': 900})
        for meta in tenants_meta:
            pkg = meta['slug']
            slug = meta['tenant_slug']
            user = 'admin_' + pkg
            verification_row = verification.get(pkg, {})
            enabled = set(verification_row.get('actual', []))
            log(f'--- start {pkg} ({slug})')
            ok, login_url, login_flash = login(pg, user, slug)
            entry = {
                'version_id': meta['version_id'],
                'package_slug': pkg,
                'tenant_slug': slug,
                'product_profile_code': PROFILE_BY_PACKAGE.get(pkg),
                'admin_username': user,
                'enabled_modules': sorted(enabled),
                'login': {'ok': ok, 'url': login_url.replace(BASE, ''), 'detail': login_flash},
                'screenshot': None,
                'pages': [],
            }
            if not ok:
                log(f'{pkg:26} LOGIN FAILED: {login_flash[:120]}')
                results.append(entry)
                continue

            # 1280px dashboard screenshot (viewport, not full-page).
            try:
                pg.goto(f'{BASE}/t/{slug}/', wait_until='domcontentloaded', timeout=15000)
                pg.wait_for_timeout(450)
                shot_rel = f'all_packages_ui/{slug}.png'
                pg.screenshot(path=os.path.join(ROOT, 'docs', 'PAGE_AUDIT', shot_rel))
                entry['screenshot'] = shot_rel
            except Exception as exc:  # noqa: BLE001
                entry['screenshot_error'] = str(exc)[:180]

            todo: list[tuple[str, str]] = []
            for shared in ('/', '/dashboard', '/inbox', '/settings', '/doctor/settings'):
                todo.append((shared, 'shared'))
            if 'appointments' in enabled:
                todo.extend(
                    [
                        ('/booking/dashboard', 'appointments'),
                        ('/booking/create', 'appointments'),
                        ('/booking/register', 'appointments'),
                        ('/booking/', 'appointments'),
                    ]
                )
            for module in sorted(enabled):
                candidates = [
                    p for p in paths_by_module.get(module, []) if p not in {x[0] for x in todo}
                ]
                todo.extend((p, module) for p in candidates[:5])
            seen = set()
            for path, module in todo:
                if path in seen:
                    continue
                seen.add(path)
                entry['pages'].append(scan_page(pg, path, module, slug, enabled))

            counts = Counter()
            for page in entry['pages']:
                for key, vals in page.get('issues', {}).items():
                    counts[key] += len(vals)
            entry['issue_counts'] = dict(counts)
            log(
                f'{pkg:26} pages={len(entry["pages"]):3} '
                f'errors={sum(counts.values()):3} {dict(counts)}'
            )
            results.append(entry)
        browser.close()

    # ---- top-level summary of recurring issues -------------------------------
    issue_tenants = defaultdict(set)
    issue_occurrences = Counter()
    issue_examples = defaultdict(list)
    status_counts = Counter()
    login_failures = []
    for entry in results:
        if not entry['login']['ok']:
            login_failures.append(
                {
                    'package_slug': entry['package_slug'],
                    'detail': entry['login']['detail'],
                }
            )
        for page in entry['pages']:
            status_counts[str(page['status'])] += 1
            for key, vals in page.get('issues', {}).items():
                issue_occurrences[key] += len(vals)
                issue_tenants[key].add(entry['package_slug'])
                if len(issue_examples[key]) < 12:
                    issue_examples[key].append(
                        {
                            'package': entry['package_slug'],
                            'path': page['path'],
                            'detail': vals[0],
                        }
                    )
    descriptions = {
        'disabled_module_link': 'Visible link/button targets a module not enabled for this tenant',
        'placeholder_href': 'Literal href="#" (or javascript:void) on a visible link/button',
        'dead_onclick': 'Dead onclick handler containing literal Jinja `_()`',
        'console_error': 'Browser console error / uncaught page exception',
        'unprefixed_tenant_link': 'Internal link missing the /t/<tenant_slug>/ prefix (breaks tenant context)',
        'bad_status': 'HTTP status other than 200/302 on a non-parameterised page',
        'error_marker': 'Server-error marker rendered in the page body',
        'navigation_error': 'Page navigation raised an exception / timed out',
        'control_scan_error': 'Control DOM scan failed',
    }
    sources = {
        'disabled_module_link': (
            'app/shared/nav_resolver.py:221-234 (admin "إعدادات العيادة" always links to '
            '/doctor/settings); templates/partials/_sidebar_dynamic.html:28-29; '
            'templates/dashboards/command_center.html:12-16 ("زيارة جديدة" quick tile)'
        ),
        'placeholder_href': 'templates/owner/announcements.html:52 (owner page, not reached in tenant walk)',
        'dead_onclick': 'no literal `_()` handler rendered in the walked tenant pages',
        'console_error': (
            'resource load failures for 403/404 pages: app/shared/nav_resolver.py:221-234; '
            'routes/patient_portal.py:159/192/267; app/core/platform_capabilities.py:55-59'
        ),
        'unprefixed_tenant_link': (
            'app/shared/dashboard_registry.py:365,372; app/shared/dashboard_service.py:721 '
            '(url_for instead of a tenant-prefixed URL); templates/dashboards/_quick_actions.html:4; '
            'templates/errors/403.html:30,404.html:30,500.html:30 (absolute "/" back-link)'
        ),
        'bad_status': (
            'app/shared/nav_resolver.py:221-234 (/doctor/settings 403); '
            'routes/patient_portal.py:159,192,267,373,475,498 (patient-only role guard); '
            'app_factory.py:1254 + app/core/platform_capabilities.py:55-59 (/sso/config 404)'
        ),
        'error_marker': 'routes/* error handlers',
        'navigation_error': 'slow/timing-out endpoints (/finance/audit, /medication/pos) on this run',
    }
    recurring = []
    for key in sorted(
        issue_occurrences, key=lambda k: (-len(issue_tenants[k]), -issue_occurrences[k])
    ):
        recurring.append(
            {
                'id': key,
                'description': descriptions.get(key, key),
                'tenants_affected': len(issue_tenants[key]),
                'occurrences': issue_occurrences[key],
                'source_hint': sources.get(key),
                'examples': issue_examples[key],
            }
        )

    report = {
        'generated_at': datetime.now(UTC).isoformat(),
        'base_url': BASE,
        'methodology': {
            'login': '/auth/login with per-tenant admin_<package_slug> / Audit@2026Pass and explicit tenant slug selection',
            'pages': 'non-parameterised GET pages of every enabled module (up to 5 representative pages per module) from docs/PAGE_AUDIT/inventory.json, plus /, /dashboard, /inbox, /settings, /doctor/settings and booking pages when appointments enabled',
            'viewport': {'width': 1280, 'height': 900},
            'screenshots': 'docs/PAGE_AUDIT/all_packages_ui/<tenant_slug>.png',
            'data_sources': [
                'docs/PAGE_AUDIT/package_tenants.json (tenant slugs)',
                'docs/PAGE_AUDIT/package_verification.json (enabled modules)',
                'docs/PAGE_AUDIT/inventory.json (route per module)',
                'scripts/audit/provision_all_packages.py (product_profile_code)',
            ],
            'read_only': True,
        },
        'tenants': results,
        'summary': {
            'tenants_total': len(tenants_meta),
            'logins_ok': sum(1 for r in results if r['login']['ok']),
            'login_failures': login_failures,
            'pages_walked': sum(len(r['pages']) for r in results),
            'status_counts': dict(status_counts),
            'recurring_issues': recurring,
            'duration_seconds': round(time.time() - started, 1),
        },
    }
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    log(f'wrote {OUT} in {report["summary"]["duration_seconds"]}s')
    _log_fh.close()


if __name__ == '__main__':
    main()
