"""Frontend-Backend Template Matcher

Cross-references frontend JS page modules with backend read-templates to ensure:
1. Every backend read-template has a corresponding frontend page module
2. Every frontend page module has a corresponding backend read-template
3. API calls in frontend match the routes declared in backend templates
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC_JS = ROOT / 'static' / 'js'
PAGES_DIR = STATIC_JS / 'pages'
SCENARIOS_DIR = ROOT / 'docs' / 'scenarios' / 'generated'
INVENTORY_PATH = ROOT / 'route_inventory.json'
READ_INVENTORY_PATH = ROOT / 'docs' / 'scenarios' / 'generated' / 'read-route-inventory.json'
BACKEND_TEMPLATES_DIR = ROOT / 'tools' / 'scenario_gen'


@dataclass
class FrontendPage:
    """A frontend page module."""

    path: Path
    blueprint: str
    name: str
    fetches: list[dict] = field(default_factory=list)
    api_calls: list[str] = field(default_factory=list)


@dataclass(unsafe_hash=True)
class BackendTemplate:
    """A backend read-template."""

    key: str
    family: str
    axes: tuple[str, ...]
    steps: list[dict] = field(default_factory=list)
    api_paths: list[dict] = field(default_factory=list)


@dataclass
class MatchResult:
    """Result of matching frontend to backend."""

    frontend_page: FrontendPage
    backend_templates: list[BackendTemplate] = field(default_factory=list)
    matched: bool = False
    missing_backend_apis: list[str] = field(default_factory=list)
    missing_frontend_coverage: list[str] = field(default_factory=list)


def load_api_routes() -> dict:
    """Load API_ROUTES mapping from base.html template."""
    base_html = ROOT / 'templates' / 'base.html'
    if not base_html.exists():
        return {}

    content = base_html.read_text(encoding='utf-8-sig')

    # Find the API_ROUTES object
    match = re.search(r'API_ROUTES\s*=\s*\{', content)
    if not match:
        return {}

    start = match.start()
    brace_count = 0
    for i, c in enumerate(content[start:]):
        if c == '{':
            brace_count += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0:
                end = start + i + 1
                api_routes_text = content[start:end]
                break

    # Parse the Jinja2 template to extract key-value pairs
    # The format is: key: {{ url_for('endpoint')|tojson }},
    routes = {}
    # Pattern: key: {{ url_for('endpoint')|tojson }},
    pattern = r'(\w+):\s*\{\{\s*url_for\([\'"]([^\'"]+)[\'"].*?\)\s*\|\s*tojson\s*\}\}'
    for match in re.finditer(pattern, api_routes_text):
        key = match.group(1)
        endpoint = match.group(2)
        routes[key] = endpoint

    return routes


def load_route_endpoint_map() -> dict:
    """Load mapping from (method, path) to endpoint name."""
    if not INVENTORY_PATH.exists():
        return {}

    with INVENTORY_PATH.open(encoding='utf-8') as f:
        inv = json.load(f)
    endpoint_map = {}
    for route in inv['routes']:
        path = normalize_api_path(route['path'])
        for method in route['methods']:
            if method in ('GET', 'HEAD', 'OPTIONS'):
                continue  # Skip read-only methods for write templates
            key = (method, path)
            endpoint_map[key] = route['endpoint']
    return endpoint_map


def resolve_api_routes(api_calls: list[str], api_routes: dict) -> list[str]:
    """Resolve API_ROUTES keys to actual endpoint names."""
    resolved = []
    for call in api_calls:
        # Check if it's an API_ROUTES key
        if call in api_routes:
            resolved.append(api_routes[call])
        else:
            # Check if it's a template literal with API_ROUTES
            # e.g., `fetch(\`\${window.API_ROUTES.api_department_services}?id=1\`)`
            for key, endpoint in api_routes.items():
                if key in call:
                    resolved.append(endpoint)
            if call not in resolved:
                resolved.append(call)
    return list(set(resolved))


def extract_frontend_pages() -> list[FrontendPage]:
    """Extract all frontend page modules and their API calls."""
    pages = []

    for page_file in PAGES_DIR.rglob('*.js'):
        if page_file.name.startswith('_') or page_file.name.startswith('.'):
            continue
        if 'test' in page_file.name.lower():
            continue

        rel_path = page_file.relative_to(PAGES_DIR)
        blueprint = rel_path.parts[0] if len(rel_path.parts) > 1 else 'root'
        name = page_file.stem

        content = page_file.read_text(encoding='utf-8-sig')

        # Extract fetch/axios/ajax calls and API_ROUTES references
        api_calls = []

        # Match fetch/axios/ajax calls with template literals
        fetch_patterns = [
            r'fetch\s*\(\s*["\']([^"\']+)["\']',  # fetch('/api/...')
            r'fetch\s*\(\s*(`[^`]*`)',  # fetch(`...`)
            r'axios\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
            r'axios\s*\(\s*\{[^}]*url\s*:\s*["\']([^"\']+)["\']',
        ]

        for pattern in fetch_patterns:
            for match in re.finditer(pattern, content):
                if len(match.groups()) >= 2:
                    url = match.group(2)
                elif len(match.groups()) == 1:
                    url = match.group(1)
                else:
                    continue
                # Normalize URL
                url = url.split('?')[0].split('#')[0]
                if url.startswith('/'):
                    api_calls.append(url)

        # Match window.API_ROUTES.key patterns
        api_routes_patterns = [
            r'window\.API_ROUTES\.(\w+)',
            r'window\.API_ROUTES\s*&&\s*window\.API_ROUTES\.(\w+)',
            r'window\.API_ROUTES\[["\'](\w+)["\']\]',
        ]

        for pattern in api_routes_patterns:
            for match in re.finditer(pattern, content):
                key = match.group(1)
                api_calls.append(key)

        # Also look for template literals with API_ROUTES
        # e.g., `\${window.API_ROUTES.api_department_services}?id=1`
        template_literal_pattern = r'`\$\{window\.API_ROUTES\.(\w+)\}'
        for match in re.finditer(template_literal_pattern, content):
            api_calls.append(match.group(1))

        # Match template variable patterns like __M2__, __M3__, etc.
        # These are template variables injected by the backend
        template_var_pattern = r'__M\d+__'
        for match in re.finditer(template_var_pattern, content):
            api_calls.append(match.group(0))

        # Also look for API constants
        const_patterns = [
            r'const\s+\w+_API\s*=\s*["\']([^"\']+)["\']',
            r'const\s+\w+_URL\s*=\s*["\']([^"\']+)["\']',
            r'const\s+\w+_ENDPOINT\s*=\s*["\']([^"\']+)["\']',
        ]

        for pattern in const_patterns:
            for match in re.finditer(pattern, content):
                url = match.group(1)
                if url.startswith('/'):
                    api_calls.append(url)

        # Resolve API_ROUTES keys to actual endpoints
        resolved_calls = resolve_api_routes(api_calls, load_api_routes())

        page = FrontendPage(
            path=page_file,
            blueprint=blueprint,
            name=name,
            fetches=[],
            api_calls=list(set(resolved_calls)),
        )
        pages.append(page)

    return pages


def _extract_template_blocks(content: str):
    """Extract template key and steps content, handling nested parentheses."""
    for match in re.finditer(r'Template\(', content):
        # Find the key (handles both single and double quotes)
        key_start = content.find("key='", match.start())
        if key_start < 0:
            key_start = content.find('key="', match.start())
        if key_start < 0:
            continue
        quote_char = content[key_start + 4]  # ' or "
        key_end = content.find(quote_char, key_start + 5)
        key = content[key_start + 5 : key_end]

        # Find steps=
        steps_start = content.find('steps=', match.end())
        if steps_start < 0:
            continue
        # Find matching parenthesis for steps=(
        paren_start = content.find('(', steps_start + 5)  # after 'steps='
        if paren_start < 0:
            continue
        # Find matching closing paren
        paren_depth = 0
        for offset, char in enumerate(content[paren_start:]):
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
                if paren_depth == 0:
                    yield (key, content[paren_start + 1 : paren_start + offset])
                    break


def load_backend_templates() -> list[BackendTemplate]:
    """Load backend read-templates from scenario generation."""
    templates = []
    endpoint_map = load_route_endpoint_map()

    # Load from read_templates.py
    read_templates_path = BACKEND_TEMPLATES_DIR / 'read_templates.py'
    if read_templates_path.exists():
        content = read_templates_path.read_text(encoding='utf-8')

        for key, steps_content in _extract_template_blocks(content):
            # Extract family and axes
            family_match = re.search(r'family=["\']([^"\']+)["\']', steps_content[:200])
            axes_match = re.search(r'axes=\((.*?)\)', steps_content[:200])

            family = family_match.group(1) if family_match else 'unknown'
            axes = ()
            if axes_match:
                axes = tuple(
                    a.strip().strip('\'"') for a in axes_match.group(1).split(',') if a.strip()
                )

            # Extract API paths from steps (with methods)
            api_paths = []
            # Pattern: _s(ROLE, 'METHOD /path', 'description')
            step_matches = re.findall(r"_s\([^,]+,\s*['\"]([A-Z]+\s+[^'\"]+)['\"]", steps_content)
            for path_with_method in step_matches:
                parts = path_with_method.split(' ', 1)
                if len(parts) == 2:
                    method, path = parts
                    norm_path = normalize_api_path(path)
                    endpoint = endpoint_map.get((method, norm_path))
                    api_paths.append(
                        {
                            'method': method,
                            'path': path,
                            'norm_path': norm_path,
                            'endpoint': endpoint,
                        }
                    )

            template = BackendTemplate(key=key, family=family, axes=axes, api_paths=api_paths)
            templates.append(template)

    return templates


def load_route_inventory() -> dict:
    """Load route inventory."""
    if INVENTORY_PATH.exists():
        return json.loads(INVENTORY_PATH.read_text(encoding='utf-8'))
    return {}


def load_read_inventory() -> dict:
    """Load read route inventory."""
    if READ_INVENTORY_PATH.exists():
        return json.loads(READ_INVENTORY_PATH.read_text(encoding='utf-8'))
    return {}


def normalize_api_path(path: str) -> str:
    """Normalize API path for comparison."""
    # Remove query params, fragments
    path = path.split('?', maxsplit=1)[0].split('#', maxsplit=1)[0]
    # Normalize converters
    return re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', path)


def match_frontend_to_backend(
    pages: list[FrontendPage], templates: list[BackendTemplate]
) -> list[MatchResult]:
    """Match frontend pages to backend templates."""
    results = []

    # Build API path index for backend templates
    template_by_blueprint = {}
    for template in templates:
        bp = template.family.lower()
        if bp not in template_by_blueprint:
            template_by_blueprint[bp] = []
        template_by_blueprint[bp].append(template)

    # Also index by endpoint
    endpoint_to_templates = {}
    for template in templates:
        for api in template.api_paths:
            endpoint = api.get('endpoint')
            if endpoint:
                if endpoint not in endpoint_to_templates:
                    endpoint_to_templates[endpoint] = []
                endpoint_to_templates[endpoint].append(template)

    for page in pages:
        matched_template_keys = set()
        missing_backend_apis = []
        matched_backend_apis = set()

        # Match by blueprint
        bp_templates = template_by_blueprint.get(page.blueprint, [])
        for template in bp_templates:
            matched_template_keys.add(template.key)

        # Match by API calls (frontend api_calls are now endpoint names)
        for api_call in page.api_calls:
            matched = False

            # Check direct endpoint match
            if api_call in endpoint_to_templates:
                for template in endpoint_to_templates[api_call]:
                    matched_template_keys.add(template.key)
                matched = True

            # Check normalized path match (for API paths that weren't resolved to endpoints)
            if not matched:
                norm = normalize_api_path(api_call)
                if norm in endpoint_to_templates:
                    for template in endpoint_to_templates[norm]:
                        matched_template_keys.add(template.key)
                    matched = True

            # Check pattern match (with converters) on backend template paths
            if not matched:
                for template in templates:
                    for api in template.api_paths:
                        t_endpoint = api.get('endpoint')
                        if t_endpoint and _paths_match(normalize_api_path(api_call), t_endpoint):
                            matched_template_keys.add(template.key)
                            matched = True
                            break

            if not matched:
                missing_backend_apis.append(api_call)
            else:
                matched_backend_apis.add(api_call)

        # Convert template keys back to template objects
        key_to_template = {t.key: t for t in templates}
        matched_templates = [key_to_template[k] for k in matched_template_keys]

        result = MatchResult(
            frontend_page=page,
            backend_templates=matched_templates,
            matched=len(matched_templates) > 0,
            missing_backend_apis=missing_backend_apis,
            missing_frontend_coverage=[],
        )
        results.append(result)

    return results


def _paths_match(path1: str, path2: str) -> bool:
    """Check if two paths match (ignoring converter differences)."""
    # Simple pattern matching - in production use proper routing
    parts1 = path1.strip('/').split('/')
    parts2 = path2.strip('/').split('/')

    if len(parts1) != len(parts2):
        return False

    for p1, p2 in zip(parts1, parts2, strict=True):
        # Both are parameters
        if p1.startswith('{') and p2.startswith('{'):
            continue
        # One is parameter, one is not
        if (p1.startswith('{') and not p2.startswith('{')) or (
            not p1.startswith('{') and p2.startswith('{')
        ):
            continue  # Allow parameter vs literal match
        if p1 != p2:
            return False
    return True


def find_orphaned_backend_templates(
    results: list[MatchResult], templates: list[BackendTemplate]
) -> list[BackendTemplate]:
    """Find backend templates with no matching frontend page."""
    matched_template_keys = set()
    for result in results:
        for template in result.backend_templates:
            matched_template_keys.add(template.key)

    return [t for t in templates if t.key not in matched_template_keys]


def find_missing_frontend_coverage(
    templates: list[BackendTemplate], pages: list[FrontendPage]
) -> dict[str, list[str]]:
    """Find backend template APIs not covered by any frontend page."""
    all_frontend_apis = set()
    for page in pages:
        for api in page.api_calls:
            all_frontend_apis.add(normalize_api_path(api))

    missing = {}
    for template in templates:
        template_missing = []
        for api in template.api_paths:
            endpoint = api.get('endpoint')
            norm = normalize_api_path(endpoint) if endpoint else ''
            if norm and norm not in all_frontend_apis:
                template_missing.append(endpoint)
        if template_missing:
            missing[template.key] = template_missing

    return missing


def generate_report(
    pages: list[FrontendPage], templates: list[BackendTemplate], results: list[MatchResult]
) -> str:
    """Generate markdown report."""
    lines = [
        '# Frontend-Backend Template Matching Report',
        '',
        f'Generated: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")}',
        f'Frontend pages analyzed: {len(pages)}',
        f'Backend templates analyzed: {len(templates)}',
        '',
    ]

    # Calculate derived data
    orphaned = find_orphaned_backend_templates(results, templates)
    missing = find_missing_frontend_coverage(templates, pages)

    # Summary
    matched_pages = sum(1 for r in results if r.matched)
    total_pages = len(results)
    lines += [
        '## Summary',
        '',
        f'- Frontend pages with backend match: {matched_pages}/{total_pages} ({100 * matched_pages / total_pages:.1f}%)',
        f'- Orphaned backend templates: {len(orphaned)}',
        '',
    ]

    # Per-page detail
    lines += ['## Page-by-Page Matching', '']

    for result in sorted(
        results, key=lambda r: (not r.matched, r.frontend_page.blueprint, r.frontend_page.name)
    ):
        page = result.frontend_page
        status = '✅' if result.matched else '❌'
        lines += [
            f'### {status} {page.blueprint}/{page.name}',
            f'- File: `{page.path}`',
            f'- API calls found: {len(page.api_calls)}',
        ]

        if result.backend_templates:
            lines.append(
                f'- Matched backend templates: {", ".join(t.key for t in result.backend_templates)}'
            )

        if result.missing_backend_apis:
            lines.append(
                f'- **Missing backend coverage for:** {", ".join(result.missing_backend_apis)}'
            )

        lines.append('')

    # Orphaned templates
    if orphaned:
        lines += ['## Orphaned Backend Templates (No Frontend Coverage)', '']
        for template in orphaned:
            api_strs = [
                api.get('endpoint', '') for api in template.api_paths if api.get('endpoint')
            ]
            lines.append(
                f'- `{template.key}` ({template.family}) - APIs: {", ".join(api_strs) or "none"}'
            )
        lines.append('')

    # Missing frontend coverage
    if missing:
        lines += ['## Backend Template APIs Not Covered by Frontend', '']
        for template_key, apis in missing.items():
            lines.append(f'- **{template_key}**: {", ".join(apis)}')
        lines.append('')

    # Cross-reference table
    lines += ['## API Cross-Reference Matrix', '']
    lines.append('| Frontend Page | Blueprint | API Calls | Matched Templates | Missing |')
    lines.append('|---------------|-----------|-----------|-------------------|---------|')

    for result in sorted(results, key=lambda r: (r.frontend_page.blueprint, r.frontend_page.name)):
        page = result.frontend_page
        apis = ', '.join(result.frontend_page.api_calls[:3]) + (
            '...' if len(result.frontend_page.api_calls) > 3 else ''
        )
        templates_str = ', '.join(t.key for t in result.backend_templates[:2]) + (
            '...' if len(result.backend_templates) > 2 else ''
        )
        missing_str = ', '.join(result.missing_backend_apis[:2]) + (
            '...' if len(result.missing_backend_apis) > 2 else ''
        )
        lines.append(
            f'| {page.blueprint}/{page.name} | {page.blueprint} | {apis} | {templates_str} | {missing_str} |'
        )

    return '\n'.join(lines)


def main():
    print('Extracting frontend pages...')
    pages = extract_frontend_pages()
    print(f'  Found {len(pages)} frontend pages')

    print('Loading backend templates...')
    templates = load_backend_templates()
    print(f'  Found {len(templates)} backend templates')

    print('Matching...')
    results = match_frontend_to_backend(pages, templates)

    report = generate_report(pages, templates, results)

    output_path = ROOT / 'docs' / 'reports' / 'frontend-backend-matching.md'
    os.makedirs(output_path.parent, exist_ok=True)
    output_path.write_text(report, encoding='utf-8', newline='\n')
    print(f'Report written to {output_path}')

    # Print summary
    matched = sum(1 for r in results if r.matched)
    orphaned = find_orphaned_backend_templates(results, templates)
    missing = find_missing_frontend_coverage(templates, pages)

    print('\nSummary:')
    print(f'  Frontend pages: {len(pages)}')
    print(f'  Matched: {matched}/{len(pages)} ({100 * matched / len(pages):.1f}%)')
    print(f'  Orphaned backend templates: {len(orphaned)}')
    print(f'  Templates with missing frontend coverage: {len(missing)}')

    return 0 if matched == len(pages) and len(orphaned) == 0 and len(missing) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
