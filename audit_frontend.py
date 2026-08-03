import re
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(r'D:\Data\MED-2-7-2025\medical_system')

print('=' * 80)
print('COMPREHENSIVE FRONTEND AUDIT: Dropdowns, Forms, Fetch/GET/POST')
print('=' * 80)

# 1. Collect all template form actions and selects
template_issues = []
js_issues = []
fetch_issues = []

route_pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")
fetch_pattern = re.compile(r'fetch\([\'"]([^\'"]+)[\'"]')
select_pattern = re.compile(r'<select[^>]*name=[\'"]([^\'"]+)[\'"]')
form_action_pattern = re.compile(r'<form[^>]*action=[\'"]([^\'"]+)[\'"]')
form_method_pattern = re.compile(r'<form[^>]*method=[\'"](GET|POST)[\'"]', re.IGNORECASE)

# Parse route inventory
import json

route_inv = BASE / 'route_inventory.json'
if route_inv.exists():
    with open(route_inv, encoding='utf-8') as f:
        inv_data = json.load(f)
    known_endpoints = {r['endpoint'] for r in inv_data.get('routes', [])}
    known_paths = {r['path'] for r in inv_data.get('routes', [])}
else:
    known_endpoints = set()
    known_paths = set()

# Scan templates
for tmpl in BASE.glob('templates/**/*.html'):
    content = tmpl.read_text(encoding='utf-8', errors='ignore')
    rel = tmpl.relative_to(BASE)

    # Form actions
    for m in form_action_pattern.finditer(content):
        action = m.group(1)
        # Find method
        start = max(0, m.start() - 200)
        form_tag = content[start : m.end()]
        method_match = form_method_pattern.search(form_tag)
        method = method_match.group(1).upper() if method_match else 'GET'

        # Check if it's a url_for
        url_for_match = route_pattern.search(action)
        if url_for_match:
            endpoint = url_for_match.group(1)
            if endpoint not in known_endpoints and not endpoint.startswith('static'):
                template_issues.append(
                    f'{rel}: form {method} action uses unknown endpoint "{endpoint}"'
                )
        elif action.startswith('/') and action not in known_paths and not action.startswith('/t/'):
            template_issues.append(f'{rel}: form {method} action uses unknown path "{action}"')

    # Select dropdowns
    for m in select_pattern.finditer(content):
        name = m.group(1)
        # Check for empty options or missing required
        select_start = m.start()
        # Find the full select tag
        end_pos = content.find('</select>', select_start)
        if end_pos > 0:
            select_html = content[select_start:end_pos]
            if 'required' not in select_html.lower() and 'onchange' not in select_html.lower():
                template_issues.append(f'{rel}: select name="{name}" missing required/onchange')

    # Inline fetch() calls
    for m in fetch_pattern.finditer(content):
        url = m.group(1)
        fetch_issues.append(f'{rel}: inline fetch() to "{url}"')

# Scan static JS
for js in BASE.glob('static/js/**/*.js'):
    content = js.read_text(encoding='utf-8', errors='ignore')
    rel = js.relative_to(BASE)

    # fetch() calls
    for m in fetch_pattern.finditer(content):
        url = m.group(1)
        if url.startswith('/'):
            # Check if it's a known API route or dashboard
            if not any(
                url.startswith(p) for p in ['/api/', '/static/', '/auth/', '/health', '/__health']
            ):
                fetch_issues.append(f'{rel}: fetch() to "{url}" - verify route exists')

    # Check for hardcoded URLs
    hardcoded = re.findall(r'[\'"](https?://[^\'"]+)[\'"]', content)
    for url in hardcoded:
        if 'localhost' not in url and '127.0.0.1' not in url:
            fetch_issues.append(f'{rel}: hardcoded external URL "{url}"')

# Print results
print(f'\n{"=" * 80}')
print('TEMPLATE ISSUES')
print(f'{"=" * 80}')
if template_issues:
    for i, issue in enumerate(template_issues, 1):
        print(f'  {i}. {issue}')
else:
    print('  None')

print(f'\n{"=" * 80}')
print('FETCH/JS ISSUES')
print(f'{"=" * 80}')
if fetch_issues:
    for i, issue in enumerate(fetch_issues, 1):
        print(f'  {i}. {issue}')
else:
    print('  None')

# Summary
print(f'\n{"=" * 80}')
print('SUMMARY')
print(f'{"=" * 80}')
print(f'  Template issues: {len(template_issues)}')
print(f'  Fetch/JS issues: {len(fetch_issues)}')
print(f'  Known endpoints: {len(known_endpoints)}')
print(f'  Known paths: {len(known_paths)}')
