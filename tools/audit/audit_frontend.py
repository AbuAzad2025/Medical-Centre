import re
from pathlib import Path

# The repository root, derived from this file's own location. The previous value
# was an absolute path from the machine the script was written on, which meant the
# audit silently scanned nothing here: every glob came back empty and the script
# reported a clean result it had never actually checked.
BASE = Path(__file__).resolve().parents[2]


# 1. Collect all template form actions and selects
template_issues = []
js_issues = []
fetch_issues = []

route_pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")
# A fetch whose first argument is a bare literal is a hardcoded URL worth checking.
# One built by concatenation is a template expression, not a hardcoded path, so it
# is captured separately rather than reported as a missing route: an earlier
# version treated `fetch('/procurement/receive/' + id)` as a call to
# /procurement/receive/ and reported it as a 404 against a route that exists.
fetch_pattern = re.compile(r"fetch\(\s*(?!['\"][^'\"]*['\"]\s*\+)(['\"])(?P<url>[^'\"]+)\1")
fetch_dynamic_pattern = re.compile(r"fetch\(\s*['\"](?P<prefix>[^'\"]+)['\"]\s*\+")
select_pattern = re.compile(r'<select[^>]*name=[\'"]([^\'"]+)[\'"]')
form_action_pattern = re.compile(r'<form[^>]*action=[\'"]([^\'"]+)[\'"]')
form_method_pattern = re.compile(r'<form[^>]*method=[\'"](GET|POST)[\'"]', re.IGNORECASE)

# Parse route inventory
import json


def _forms_spanning(content):
    """Return the (start, end) offsets of every <form> block in the document."""
    spans = []
    for m in re.finditer(r'<form\b[^>]*>', content, re.IGNORECASE):
        close = content.find('</form>', m.end())
        spans.append((m.start(), close if close > 0 else len(content)))
    return spans


def _inside_form(spans, offset):
    return any(start <= offset <= end for start, end in spans)


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

    # Select dropdowns inside a form.
    #
    # Only selects that belong to a form are considered. A filter dropdown in a
    # toolbar legitimately has no `required` and no `onchange`, and flagging it
    # buries the findings that matter: the earlier version reported 173 of them,
    # almost all of them navigation, which is the number that teaches a reader to
    # ignore the report.
    form_span = _forms_spanning(content)
    for m in select_pattern.finditer(content):
        if not _inside_form(form_span, m.start()):
            continue
        name = m.group(1)
        select_start = m.start()
        end_pos = content.find('</select>', select_start)
        if end_pos > 0:
            select_html = content[select_start:end_pos]
            if 'required' not in select_html.lower() and 'onchange' not in select_html.lower():
                template_issues.append(
                    f'{rel}: form select name="{name}" missing required/onchange'
                )

    # Inline fetch() calls
    for m in fetch_pattern.finditer(content):
        url = m.group('url')
        # A literal holding a Jinja expression is resolved by the template engine,
        # so the text captured here is not the URL the browser will request.
        if '{{' in url or '{%' in url:
            continue
        bare = url.split('?')[0].rstrip('/')
        if bare and any(p.rstrip('/') == bare for p in known_paths):
            continue
        fetch_issues.append(f'{rel}: inline fetch() to "{url}"')

# Scan static JS
for js in BASE.glob('static/js/**/*.js'):
    content = js.read_text(encoding='utf-8', errors='ignore')
    rel = js.relative_to(BASE)

    # fetch() calls
    for m in fetch_pattern.finditer(content):
        url = m.group('url')
        if not url.startswith('/'):
            continue
        # Prefer the route table over a prefix list. The prefix heuristic reported
        # /super-admin/api/security-logs/summary as suspicious because it does not
        # begin with /api/, when the application serves exactly that path.
        bare = url.split('?')[0].rstrip('/')
        if bare and any(p.rstrip('/') == bare for p in known_paths):
            continue
        if not any(
            url.startswith(p) for p in ['/api/', '/static/', '/auth/', '/health', '/__health']
        ):
            fetch_issues.append(f'{rel}: fetch() to "{url}" - not in the route table')

    # fetch() calls whose URL is assembled at runtime. These are not hardcoded
    # paths, so they are listed separately: the prefix is worth a glance but the
    # audit cannot claim the assembled URL is missing.
    for m in fetch_dynamic_pattern.finditer(content):
        js_issues.append(f'{rel}: fetch() prefix "{m.group("prefix")}" is built at runtime')

    # Check for hardcoded URLs
    hardcoded = re.findall(r'[\'"](https?://[^\'"]+)[\'"]', content)
    for url in hardcoded:
        if 'localhost' in url or '127.0.0.1' in url:
            continue
        # w3.org addresses are XML namespaces and DTDs, not resources the browser
        # fetches, so listing them as outbound dependencies is noise.
        if 'w3.org' in url:
            continue
        fetch_issues.append(f'{rel}: hardcoded external URL "{url}"')


# Print results
def report(title, issues):  # noqa: T201
    """Print a section, and say so plainly when a section is empty.

    The previous tail of this file looped over the collected issues with `pass`
    as the body, so it produced no output at all: the scan ran and the result was
    discarded. An audit that cannot print what it found is indistinguishable from
    an audit that found nothing, which is how a broken path went unnoticed.

    Printing is the point of this module, so the calls are deliberate rather than
    debug leftovers.
    """
    if not issues:
        print(f'{title}: none')  # noqa: T201
        return
    print(f'{title}: {len(issues)}')  # noqa: T201
    for issue in issues:
        print(f'  - {issue}')  # noqa: T201


# The select check is a heuristic and will always produce items that are correct
# as written: a tenant slug on the login form is optional by design, a status
# filter inside a form element is still a filter. Mixing those in with a form
# action naming a route that does not exist trains a reader to skip the report,
# so the two are reported separately and only the first one fails the run.
review_items = list(template_issues)
hard_findings = list(js_issues) + list(fetch_issues)
template_issues[:] = [i for i in template_issues if 'missing required/onchange' not in i]

report('findings (route and URL defects)', hard_findings + template_issues)
report('review (heuristic, not a defect)', review_items)
print(f'total findings: {len(hard_findings) + len(template_issues)}')  # noqa: T201
print(f'total review items: {len(review_items)}')  # noqa: T201
raise SystemExit(1 if (hard_findings or template_issues) else 0)
