"""Template alignment audit: does every template read only names that exist?

Checks, with real parsers rather than heuristics:

* ``MISSING_CONTEXT`` -- a template reads a top-level name that its view never
  passes, that no context processor injects, and that is not a macro or an
  import.
* ``MISSING_FIELD``  -- a template reads ``form.x`` where ``x`` is not a field
  on the form class the view actually passes.
* ``PARSE_ERROR``    -- a template Jinja cannot parse at all.

The suppression list is the whole point. A first pass that matched templates to
form classes by field-name overlap produced pure noise, and one that treated
every undeclared name as missing flagged 99 templates using ``page_header`` --
a macro imported from ``partials/_page_header.html``. So before reporting a
name as missing, the audit proves it is not resolvable by any of the legitimate
routes: a view argument, a context processor, a macro, an import, a Jinja
global, or a template-level ``set``.

Exit code is non-zero when a real finding exists, so this can gate CI.
"""

from __future__ import annotations

import argparse
import ast
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TPL = ROOT / 'templates'

from jinja2 import Environment, FileSystemLoader, meta  # noqa: E402

#: Jinja and Flask names that are always available.
GLOBALS = {
    'url_for',
    'get_flashed_messages',
    'request',
    'session',
    'config',
    'g',
    'current_user',
    'csrf_token',
    '_',
    'gettext',
    'ngettext',
    'range',
    'dict',
    'lipsum',
    'cycler',
    'joiner',
    'namespace',
    'self',
    'super',
    'loop',
    'true',
    'false',
    'none',
    'True',
    'False',
    'None',
    'attr',
    'visit',
    'enum_values',
    'data',
    'ts',
}

#: Test names Jinja also exposes as bare identifiers; they are not context.
JINJA_TESTS = {
    'defined',
    'undefined',
    'none',
    'number',
    'string',
    'mapping',
    'sequence',
    'iterable',
    'callable',
    'odd',
    'even',
    'divisibleby',
    'lower',
    'upper',
    'boolean',
    'false',
    'true',
    'integer',
    'float',
    'in',
    'eq',
    'ne',
    'lt',
    'le',
    'gt',
    'ge',
}

FORM_BASES = {'FlaskForm', 'Form', 'ModelForm', 'SecureForm'}
FIELD_CALL = re.compile(r'Field$|Field\(')
DICT_KEY = re.compile(r"['\"](\w+)['\"]\s*:")

#: Context variables a view may legitimately not pass, because every template
#: that reads them guards the access explicitly. Each entry names the guard, so
#: removing the guard forces a decision here rather than silently changing
#: behaviour. This is an allowlist, not a suppression list: nothing may be added
#: without saying why the template is safe without it.
ALLOWLIST: dict[str, str] = {
    'pagination': (
        'Read as `{% if pagination is defined and pagination %}`. `is defined` is '
        'exactly the guard StrictUndefined provides, so the template is correct '
        'when the page is rendered without pagination.'
    ),
    'report': (
        'Read as `{% if report %}` and then only inside that branch, so the '
        'absent case renders nothing rather than failing.'
    ),
    'user_role': ('Read as `{% if user_role in [...] %}`; the comparison is the guard.'),
}


def _walk_py(subdirs: tuple[str, ...] = ()):
    """Yield .py files under each entry, which may be a directory or a file.

    ``Path.rglob`` returns nothing when given a file, so single files have to be
    handled explicitly -- getting this wrong silently skipped app_factory.py and
    therefore reported every context-processor name as missing.
    """
    for sub in subdirs:
        base = ROOT / sub
        if base.is_file():
            yield base
            continue
        if not base.exists():
            continue
        for f in base.rglob('*.py'):
            if any(seg in f.parts for seg in ('.venv', 'node_modules', '__pycache__')):
                continue
            yield f


def _parse(path: pathlib.Path):
    try:
        return ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
    except (SyntaxError, OSError):
        return None


def collect_forms() -> tuple[dict[str, set[str]], dict[str, str]]:
    """Real WTForms field names per form class, from the class bodies."""
    fields: dict[str, set[str]] = {}
    bases: dict[str, str] = {}
    for f in _walk_py(('app', 'models', 'forms', 'routes', 'services', 'utils')):
        tree = _parse(f)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bnames = {b.id for b in node.bases if isinstance(b, ast.Name)} | {
                b.attr for b in node.bases if isinstance(b, ast.Attribute)
            }
            if not (bnames & FORM_BASES or any('Form' in b for b in bnames)):
                continue
            names: set[str] = set()
            for stmt in ast.walk(node):
                if not isinstance(stmt, ast.Assign):
                    continue
                for t in stmt.targets:
                    if not isinstance(t, ast.Name):
                        continue
                    if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
                        if FIELD_CALL.search(stmt.value.func.id):
                            names.add(t.id)
                    elif isinstance(stmt.value, ast.Name) and stmt.value.id in names:
                        names.add(t.id)
            fields[node.name] = names
            bases[node.name] = ','.join(sorted(bnames))
    return fields, bases


def collect_injected() -> set[str]:
    """Names available to every template: context processors and Jinja globals."""
    injected: set[str] = set()
    for f in _walk_py(('app', 'app_factory.py', 'utils')):
        tree = _parse(f)
        if tree is None:
            continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                (getattr(d, 'attr', None) or getattr(d, 'id', None)) == 'context_processor'
                for d in n.decorator_list
            ):
                injected |= set(DICT_KEY.findall(ast.unparse(n)))
    # Jinja globals, in every registration form the app uses.
    for f in _walk_py(('app', 'app_factory.py', 'utils')):
        text = f.read_text(encoding='utf-8', errors='ignore')
        injected |= set(re.findall(r"jinja_env\.globals\[['\"]([\w.]+)['\"]\]", text))
        injected |= set(re.findall(r'add_template_global\(\s*([\w.]+)', text))
        injected |= set(re.findall(r"@app\.template_global\(\s*['\"]([\w.]+)['\"]", text))
        injected |= set(re.findall(r"@app\.template_global\(\s*name\s*=\s*['\"]?(\w+)", text))
        # app.jinja_env.globals.update({...}) and .update(name=...)
        for block in re.findall(r'globals\.update\(\s*\{(.+?)\}\s*\)', text, re.S):
            injected |= set(DICT_KEY.findall(block))
    return injected


def collect_macros_and_imports() -> set[str]:
    """Names a template can legitimately acquire via macro or import.

    Both import forms matter and both were previously missed:

        {% import 'macros/forms.html' as forms %}   -- alias is `forms`
        {% from 'partials/x.html' import page_header %}

    The first form was not matched because the imported path is a quoted
    string, not an identifier, so 7 templates using a forms macro module were
    reported as reading an undeclared context variable.
    """
    names: set[str] = set()
    for f in TPL.rglob('*.html'):
        text = f.read_text(encoding='utf-8', errors='ignore')
        names |= set(re.findall(r'\{%-?\s*macro\s+(\w+)', text))
        names |= set(re.findall(r'\{%-?\s*import\s+[^%]*?\bas\s+(\w+)', text))
        names |= set(re.findall(r'\{%-?\s*import\s+(\w+)', text))
        for group in re.findall(r'\{%-?\s*from\s+[^%]*?\s+import\s+(.+?)\s*-?%\}', text, re.S):
            for part in group.replace('(', ' ').replace(')', ' ').split(','):
                token = part.strip().split(' as ')[-1].strip()
                if token.isidentifier():
                    names.add(token)
    return names


def collect_renders() -> tuple[dict[str, set[str]], dict[str, dict[str, str]]]:
    """Template -> names the views pass, and template -> var: form class."""
    provided: dict[str, set[str]] = collections.defaultdict(set)
    forms: dict[str, dict[str, str]] = collections.defaultdict(dict)
    form_names = set(collect_forms()[0])
    for f in _walk_py(('routes', 'app', 'app_factory.py')):
        tree = _parse(f)
        if tree is None:
            continue
        for func in [
            n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]:
            local: dict[str, str] = {}
            for node in ast.walk(func):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    fn = node.value.func
                    fname = fn.id if isinstance(fn, ast.Name) else getattr(fn, 'attr', '')
                    if fname in form_names:
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                local[t.id] = fname
            for node in ast.walk(func):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                    continue
                if (
                    node.func.id not in {'render_template', 'render_template_string'}
                    or not node.args
                ):
                    continue
                first = node.args[0]
                if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                    continue
                tname = first.value
                for kw in node.keywords:
                    if kw.arg is None:
                        provided[tname].add('**dynamic**')
                        continue
                    provided[tname].add(kw.arg)
                    if kw.arg in local:
                        forms[tname][kw.arg] = local[kw.arg]
                    elif isinstance(kw.value, ast.Call) and isinstance(kw.value.func, ast.Name):
                        if kw.value.func.id in form_names:
                            forms[tname][kw.arg] = kw.value.func.id
    return provided, forms


def collect_custom_filters() -> set[str]:
    """Filter/test names the app registers at runtime.

    Jinja resolves ``{{ x|enum_label }}`` while parsing, not while rendering, so
    a filter the app registers on ``jinja_env.filters`` makes every template
    using it look syntactically broken to a bare environment. Discovering the
    names statically lets the audit stub them instead of reporting 64 phantom
    parse errors.
    """
    names: set[str] = set()
    decorator = re.compile(r"@(?:app|self\.\w+)\.template_(?:filter|global)\(\s*['\"]?([\w.]+)")
    assign = re.compile(r"jinja_env\.filters\[['\"]([\w.]+)['\"]\]\s*=")
    for f in _walk_py(('app', 'app_factory.py', 'utils', 'routes')):
        text = f.read_text(encoding='utf-8', errors='ignore')
        names |= set(decorator.findall(text))
        names |= set(assign.findall(text))
    return names


GUARD_PATTERNS = (
    r'\{%-?\s*if\s+{n}\b',
    r'\{%-?\s*if\s+not\s+__N__\b',
    r'\{%-?\s*elif\s+__N__\b',
    r'\{%-?\s*if\s+[^%]*\b__N__\b',
    r'\b__N__\s+if\b',
    r'\bif\s+__N__\b',
    r'\{%-?\s*set\s+__N__\b',
    # `| default(...)` is an explicit declaration that the name is optional, and
    # it is the form StrictUndefined requires. Treating it as a guard is what
    # lets a template say "this may be absent" instead of relying on the view.
    r'\|\s*default\(',
    r'\|default\(',
)


def _is_guarded(name: str, source: str) -> bool:
    """True when every use of *name* is conditional.

    A template that writes ``{{ branding.name if branding else 'x' }}`` is
    deliberately defensive, and flagging it would be noise. A template that uses
    the name bare is a real dependency the view has to satisfy.

    The name is substituted as a token rather than through str.format, because
    the patterns themselves contain Jinja braces and format() would choke on
    them as field names.
    """
    token = re.escape(name)
    guards = [re.compile(p.replace('__N__', token)) for p in GUARD_PATTERNS]
    uses = list(re.finditer(r'(?<![\w.])' + token + r'\b', source))
    if not uses:
        return True
    for m in uses:
        line_start = source.rfind('\n', 0, m.start()) + 1
        line_end = source.find('\n', m.start())
        line = source[line_start : line_end if line_end > 0 else len(source)]
        if not any(g.search(line) for g in guards):
            return False
    return True


SET_RE = re.compile(r'\{%-?\s*set\s+([\w, ]+?)\s*(?:=|not in| in )')
FOR_TARGET_RE = re.compile(r'\{%-?\s*for\s+([\w, ]+?)\s+in\b')
WITH_RE = re.compile(r'\{%-?\s*with\s+([\w, ]+?)\s*=')


def collect_local(source: str) -> set[str]:
    """Names the template defines itself, so they are not "missing context".

    ``{% set x = ... %}``, ``{% for a, b in ... %}`` and ``{% with y = ... %}``
    all introduce names that ``find_undeclared_variables`` still reports when
    the definition sits in a narrower scope. Treating those as missing context
    is how ``perms`` and ``status_map`` in the roles and nursing templates came
    to be flagged when both are plainly defined in the template.
    """
    local: set[str] = set()
    for pattern in (SET_RE, FOR_TARGET_RE, WITH_RE):
        for match in pattern.finditer(source):
            for part in match.group(1).split(','):
                name = part.strip()
                if name and name.isidentifier():
                    local.add(name)
    return local


def main(argv: list[str] | None = None) -> int:
    """Run the audit.

    ``argv`` is explicit so calling this from a test does not swallow the test
    runner's own arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    # Flask-Babel's i18n extensions are not installed in a bare Jinja
    # environment, so without this every {% trans %} / {% gettext %} tag parses
    # as an unknown tag and the template is falsely reported as broken.
    extensions = []
    for ext in ('jinja2.ext.i18n', 'jinja2.ext.do', 'jinja2.ext.loopcontrols'):
        try:
            __import__(ext)
            extensions.append(ext)
        except ImportError:  # pragma: no cover - depends on Jinja build
            pass
    env = Environment(
        loader=FileSystemLoader(str(TPL)),
        autoescape=False,
        extensions=extensions,
    )
    # Register the app's own filters and globals as pass-throughs so templates
    # that use them parse. Their behaviour is the app's business, not the
    # audit's; the audit only needs names to resolve.
    custom = collect_custom_filters()
    for name in custom:
        env.filters.setdefault(name, lambda value, *_a, **_k: value)
    templates = sorted(TPL.rglob('*.html'))

    declared: dict[str, set[str]] = {}
    parse_errors: list[tuple[str, str]] = []
    for f in templates:
        rel = str(f.relative_to(TPL)).replace('\\', '/')
        try:
            declared[rel] = meta.find_undeclared_variables(
                env.parse(f.read_text(encoding='utf-8', errors='ignore'), name=rel, filename=str(f))
            )
        except Exception as exc:  # noqa: BLE001
            parse_errors.append((rel, f'{type(exc).__name__}: {exc}'))
            declared[rel] = set()

    injected = collect_injected()
    macros = collect_macros_and_imports()
    provided, provided_forms = collect_renders()
    form_fields, _bases = collect_forms()
    resolvable = GLOBALS | JINJA_TESTS | injected | macros

    missing_context: list[tuple[str, list[str]]] = []
    guarded_context: list[tuple[str, list[str]]] = []
    for tname, needed in sorted(declared.items()):
        given = provided.get(tname)
        if given is None or '**dynamic**' in given:
            continue
        src = TPL / tname
        source = src.read_text(encoding='utf-8', errors='ignore') if src.exists() else ''
        local = collect_local(source)
        absent = sorted(
            n
            for n in needed - given - resolvable - local
            if not n.startswith('_') and not n.isupper() and n not in ALLOWLIST
        )
        if not absent:
            continue
        unguarded = [n for n in absent if not _is_guarded(n, source)]
        guarded = [n for n in absent if n not in unguarded]
        if unguarded:
            missing_context.append((tname, unguarded))
        if guarded and not args.quiet:
            guarded_context.append((tname, guarded))

    missing_field: list[tuple[str, str, str, list[str]]] = []
    attr_re = re.compile(r'\b(\w+)\.([A-Za-z_]\w*)')
    for tname, fmap in sorted(provided_forms.items()):
        src = TPL / tname
        if not src.exists():
            continue
        text = src.read_text(encoding='utf-8', errors='ignore')
        for var, cls in fmap.items():
            known = form_fields.get(cls)
            if not known:
                continue
            used = {m.group(2) for m in attr_re.finditer(text) if m.group(1) == var}
            used -= {
                'items',
                'data',
                'errors',
                'hidden_fields',
                'visible_fields',
                'validate',
                'submit',
                'is_submitted',
                'field_classes',
                'meta',
            }
            unknown = sorted(u for u in used if u not in known)
            if unknown:
                missing_field.append((tname, var, cls, unknown))

    if not args.quiet:
        print(f'templates parsed : {len(declared) - len(parse_errors)}/{len(templates)}')
        print(f'context processors: {len(injected)} injected names')
        print(f'macros/imports    : {len(macros)} names')
        print(f'form classes      : {len(form_fields)}')
        print()
        for rel, err in parse_errors:
            print(f'PARSE_ERROR  {rel}: {err}')
        for tname, absent in guarded_context:
            print(f'guarded (ok)     {tname}: {absent}')
        for tname, absent in missing_context:
            print(f'MISSING_CONTEXT  {tname}: {absent}')
        for tname, var, cls, unknown in missing_field:
            print(f'MISSING_FIELD  {tname}: form.{var} ({cls}) -> {unknown}')

    total = len(parse_errors) + len(missing_context) + len(missing_field)
    print(
        f'\nRESULT: {total} finding(s) '
        f'(parse_errors={len(parse_errors)} missing_context={len(missing_context)} '
        f'missing_field={len(missing_field)})'
    )
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
