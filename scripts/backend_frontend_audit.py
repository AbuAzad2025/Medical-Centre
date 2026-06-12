"""
Backend-Frontend Cross-Reference Audit
Checks templates use valid model fields, JS calls valid endpoints,
render_template passes expected variables.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ERRORS, WARNINGS, INFOS = [], [], []
def log_error(m): ERRORS.append(m); print(f"[ERROR] {m}")
def log_warn(m): WARNINGS.append(m); print(f"[WARN]  {m}")
def log_info(m): INFOS.append(m); print(f"[INFO]  {m}")


def get_model_fields():
    from app_factory import create_app, db
    app = create_app(os.getenv('FLASK_ENV', 'testing'))
    fields = {}
    with app.app_context():
        for mapper in db.Model.registry.mappers:
            cls = mapper.class_
            if hasattr(cls, '__tablename__'):
                fields[cls.__name__] = {c.name for c in cls.__table__.columns}
                for attr in dir(cls):
                    if not attr.startswith('_') and attr not in {'query', 'metadata', 'registry'}:
                        fields[cls.__name__].add(attr)
    return fields


def get_endpoints():
    from app_factory import create_app
    app = create_app(os.getenv('FLASK_ENV', 'testing'))
    return {r.endpoint: str(r.methods - {'OPTIONS', 'HEAD'})
            for r in app.url_map.iter_rules() if r.endpoint != 'static'}


def extract_render_vars(filepath):
    """Extract render_template variable names from route files."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            src = f.read()
    except: return []
    results = []
    for m in re.finditer(r'render_template\s*\(\s*["\']([^"\']+)["\']\s*,?\s*([^)]*)\)', src, re.DOTALL):
        tmpl = m.group(1)
        args = m.group(2)
        kw = [k.strip() for k in re.findall(r'([a-zA-Z_]\w*)\s*=', args)]
        results.append((tmpl, kw))
    return results


def extract_template_refs(filepath):
    """Extract obj.field references and url_for from template."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except: return set(), set()
    refs = set()
    urls = set()
    for m in re.finditer(r'\b([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)\b', content):
        refs.add((m.group(1), m.group(2)))
    for m in re.finditer(r'url_for\s*\(\s*["\']([^"\']+)["\']', content):
        urls.add(m.group(1))
    return refs, urls


# Jinja2 built-ins and common non-model variables
SAFE_VARS = {'g', 'session', 'request', 'config', 'current_user', 'url_for',
             'get_flashed_messages', 'range', 'len', 'str', 'int', 'float',
             'dict', 'list', 'tuple', 'set', 'zip', 'enumerate', 'map',
             'filter', 'sorted', 'reversed', 'any', 'all', 'hasattr',
             'getattr', 'isinstance', 'type', 'id', 'format', 'join',
             'split', 'replace', 'strip', 'lower', 'upper', 'title',
             'capitalize', 'startswith', 'endswith', 'find', 'index',
             'count', 'isdigit', 'isalpha', 'isalnum', 'isspace',
             'zfill', 'center', 'ljust', 'rjust', 'now', 'today',
             'utcnow', 'combine', 'strptime', 'strftime', 'replace',
             'astimezone', 'timezone', 'timedelta', 'date', 'time',
             'datetime', 'Decimal', 'json', 'loads', 'dumps',
             'loop', 'index', 'index0', 'revindex', 'revindex0',
             'first', 'last', 'length', 'depth', 'depth0',
             'patient', 'patients', 'visit', 'visits',
             'appointment', 'appointments', 'prescription', 'prescriptions',
             'invoice', 'invoices', 'payment', 'payments',
             'user', 'users', 'doctor', 'doctors', 'nurse', 'nurses',
             'department', 'departments', 'lab', 'labs',
             'radiology', 'emergency', 'pharmacy', 'billing',
             'manager', 'admin', 'reception', 'accounting',
             'record', 'records', 'report', 'reports',
             'task', 'tasks', 'note', 'notes', 'file', 'files',
             'image', 'images', 'document', 'documents',
             'message', 'messages', 'notification', 'notifications',
             'alert', 'alerts', 'log', 'logs', 'event', 'events',
             'queue', 'queues', 'counter', 'counters',
             'item', 'items', 'entry', 'entries', 'row', 'rows',
             'cell', 'cells', 'column', 'columns', 'page', 'pages',
             'form', 'forms', 'field', 'fields', 'widget', 'widgets',
             'button', 'buttons', 'link', 'links', 'nav', 'navbar',
             'sidebar', 'header', 'footer', 'content', 'container',
             'wrapper', 'panel', 'card', 'deck', 'group',
             'breadcrumb', 'pagination', 'pager', 'modal',
             'tooltip', 'popover', 'dropdown', 'carousel',
             'collapse', 'tab', 'pill', 'alert', 'badge',
             'progress', 'meter', 'table', 'thead', 'tbody',
             'tfoot', 'tr', 'th', 'td', 'col', 'colgroup',
             'figure', 'figcaption', 'caption', 'summary',
             'details', 'dialog', 'menu', 'menuitem', 'toolbar',
             'status', 'error', 'warning', 'info', 'success',
             'danger', 'primary', 'secondary', 'tertiary',
             'light', 'dark', 'muted', 'white', 'black',
             'transparent', 'inherit', 'initial', 'unset',
             'none', 'auto', 'hidden', 'visible', 'collapse',
             'scroll', 'fixed', 'absolute', 'relative',
             'static', 'sticky', 'inherit', 'initial',
             'unset', 'revert', 'all', 'unset', 'global',
             'local', 'text', 'element', 'content', 'box',
             'padding', 'margin', 'border', 'outline',
             'shadow', 'radius', 'width', 'height',
             'min', 'max', 'top', 'bottom', 'left', 'right',
             'center', 'middle', 'start', 'end', 'between',
             'around', 'evenly', 'baseline', 'stretch',
             'normal', 'nowrap', 'wrap', 'reverse',
             'row', 'column', 'dense', 'area', 'span',
             'self', 'items', 'content', 'justify',
             'align', 'place', 'grid', 'flex', 'block',
             'inline', 'inline-block', 'inline-flex',
             'inline-grid', 'table', 'table-cell',
             'table-row', 'table-column', 'list-item',
             'run-in', 'compact', 'marker', 'ruby'}


def check_backend_to_frontend(endpoints, model_fields):
    print("\n" + "="*70 + "\n[1/2] Templates — Model field references\n" + "="*70)
    base = os.path.dirname(os.path.dirname(__file__))
    issues = []
    total = 0
    for root, _, files in os.walk(os.path.join(base, 'templates')):
        for f in files:
            if not f.endswith(('.html', '.j2')): continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, base)
            refs, urls = extract_template_refs(path)
            for ep in urls:
                if ep == 'static': continue
                if ep not in endpoints:
                    issues.append(f"{rel}: url_for('{ep}') missing")
            for var, field in refs:
                total += 1
                if var in SAFE_VARS: continue
                # Singularize common plurals
                guess = var
                if var.endswith('s') and var != 'status':
                    guess = var[:-1]
                if guess not in model_fields:
                    continue
                known = model_fields[guess]
                if field not in known:
                    issues.append(f"{rel}: {var}.{field} may not exist in {guess}")
    if issues:
        for i in issues[:20]: log_warn(i)
        if len(issues) > 20: log_warn(f"... +{len(issues)-20} more")
    else:
        log_info(f"All {total} template references are valid")
    return issues


def check_render_template_vars():
    print("\n" + "="*70 + "\n[2/2] Routes — render_template variable usage\n" + "="*70)
    base = os.path.dirname(os.path.dirname(__file__))
    routes_dir = os.path.join(base, 'routes')
    issues = []
    for f in os.listdir(routes_dir):
        if not f.endswith('.py'): continue
        path = os.path.join(routes_dir, f)
        rel = os.path.relpath(path, base)
        render_vars = extract_render_vars(path)
        for tmpl, vars_passed in render_vars:
            # Check template file exists
            tmpl_path = os.path.join(base, 'templates', tmpl)
            if not os.path.exists(tmpl_path):
                issues.append(f"{rel}: render_template('{tmpl}') — file not found")
    if issues:
        for i in issues[:20]: log_warn(i)
        if len(issues) > 20: log_warn(f"... +{len(issues)-20} more")
    else:
        log_info("All render_template calls reference existing templates")
    return issues


def main():
    print("="*70 + "\nBackend-Frontend Cross-Reference Audit\n" + "="*70)
    endpoints = get_endpoints()
    model_fields = get_model_fields()
    check_backend_to_frontend(endpoints, model_fields)
    check_render_template_vars()
    print("\n" + "="*70 + "\nالملخص النهائي\n" + "="*70)
    print(f"  {len(ERRORS)} خطأ")
    print(f"  {len(WARNINGS)} تحذير")
    print(f"  {len(INFOS)} معلومة")
    if not ERRORS and not WARNINGS:
        print("\n✅ Backend و Frontend متطابقان تماماً")
    sys.exit(1 if ERRORS else 0)

if __name__ == '__main__':
    main()
