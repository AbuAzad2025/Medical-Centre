import json
import re
from pathlib import Path

BASE = Path(r'D:\Data\MED-2-7-2025\medical_system')

# More targeted audit: actual functional issues

route_inv = BASE / 'route_inventory.json'
with open(route_inv, encoding='utf-8') as f:
    inv_data = json.load(f)
known_endpoints = {r['endpoint'] for r in inv_data.get('routes', [])}
known_paths = {r['path'] for r in inv_data.get('routes', [])}

issues = []

# Check forms for:
# 1. POST forms missing CSRF
# 2. Form actions with unknown endpoints
# 3. GET forms that should be POST
# 4. Selects in POST forms without name attribute

for tmpl in BASE.glob('templates/**/*.html'):
    content = tmpl.read_text(encoding='utf-8', errors='ignore')
    rel = tmpl.relative_to(BASE)

    # Find all forms
    form_pattern = re.compile(r'<form[^>]*>.*?</form>', re.DOTALL | re.IGNORECASE)
    for form_match in form_pattern.finditer(content):
        form_html = form_match.group(0)

        # Get method
        method_match = re.search(r'method=[\'"](GET|POST)[\'"]', form_html, re.IGNORECASE)
        method = method_match.group(1).upper() if method_match else 'GET'

        # Get action
        action_match = re.search(r'action=[\'"]([^\'"]+)[\'"]', form_html)
        action = action_match.group(1) if action_match else ''

        # Check CSRF for POST
        if method == 'POST':
            has_csrf = (
                'csrf_token' in form_html.lower()
                or 'forms.csrf()' in form_html
                or 'csrf()' in form_html
            )
            if not has_csrf:
                issues.append(f'{rel}: POST form missing CSRF (action={action})')

        # Check action endpoint
        if action:
            url_for_match = re.search(r'url_for\([\'"]([^\'"]+)[\'"]\)', action)
            if url_for_match:
                endpoint = url_for_match.group(1)
                if endpoint not in known_endpoints and not endpoint.startswith('static'):
                    issues.append(
                        f'{rel}: form action uses unknown endpoint "{endpoint}" (method={method})'
                    )
            elif (
                action.startswith('/')
                and action not in known_paths
                and not action.startswith(('/t/', '/static/'))
            ):
                issues.append(f'{rel}: form action uses unknown path "{action}" (method={method})')

        # Check selects in POST forms for name attribute
        if method == 'POST':
            select_matches = re.finditer(r'<select[^>]*>', form_html)
            for sel_match in select_matches:
                sel_tag = sel_match.group(0)
                if 'name=' not in sel_tag:
                    issues.append(f'{rel}: POST form has select without name attribute')

# Check JS fetch calls for valid routes
js_issues = []
for js in BASE.glob('static/js/**/*.js'):
    content = js.read_text(encoding='utf-8', errors='ignore')
    rel = js.relative_to(BASE)

    # fetch() calls
    fetch_pattern = re.compile(r'fetch\([\'"]([^\'"]+)[\'"]')
    for m in fetch_pattern.finditer(content):
        url = m.group(1)
        if url.startswith('/') and not url.startswith(
            ('/api/', '/static/', '/auth/', '/health', '/__health', '/t/')
        ):
            # Check if path exists in route inventory
            # Extract path (remove query string)
            path = url.split('?')[0]
            if path not in known_paths:
                js_issues.append(f'{rel}: fetch() to unknown path "{url}"')

for _i, _issue in enumerate(issues, 1):
    pass

for _i, _issue in enumerate(js_issues, 1):
    pass
