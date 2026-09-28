"""Fail the build on any query that string-matches an encrypted column.

Why this gate exists
--------------------
``FieldEncryptionService.encrypt`` uses a random 12-byte nonce, so the same
plaintext produces different ciphertext on every write. Any SQL that compares
such a column to a literal -- ``ilike('%sara%')``, ``filter_by(phone=...)``,
``Model.email == x`` -- can therefore never match. Those queries do not fail
loudly; they return nothing, and the caller reads that as "no such record".
That is how patient search, duplicate detection, identity linking and booking
lookup all became dead code while the application still returned HTTP 200.

The fix is never a string comparison on the column. It is one of:

  * ``Patient.search(term)`` -- exact blind index plus the trigram index
  * ``Patient.find_by_national_id`` / ``find_by_phone`` -- blind index
  * ``db.session.query(Column.col.is_(None))`` -- NULL passes through the type

``is_(None)`` is deliberately allowed: an unset column is stored as SQL NULL and
the TypeDecorator returns it untouched, so that comparison is correct.

How it decides
--------------
Encrypted columns are read from the model declarations, not from a list kept
here, so adding an ``EncryptedString`` column automatically brings it under
protection. Only *SQL-level* comparison is flagged. Comparing an attribute on
an already-loaded instance (``p.first_name == 'Sara'``) is a plain Python
comparison on a decrypted value and is perfectly valid.
"""

from __future__ import annotations

import argparse
import ast
import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_DIRS = {
    '.venv',
    'node_modules',
    '__pycache__',
    'migrations',
    '.mypy_cache',
    '.ruff_cache',
    '.pytest_cache',
    'tests',
}

#: Comparisons that are safe on an encrypted column.
ALLOWED_CALLS = {'is_', 'isnot', 'isnot_', 'notin_', 'notlike', 'notilike'}

#: Column names that are plaintext despite living on a model that has encrypted
#: columns. Empty by design: the model declarations are the source of truth.


def python_files(subdirs: tuple[str, ...] = ('app', 'routes', 'services', 'utils', 'models')):
    for sub in subdirs:
        base = ROOT / sub
        if not base.exists():
            continue
        for f in sorted(base.rglob('*.py')):
            if any(seg in f.parts for seg in SKIP_DIRS):
                continue
            yield f


def collect_encrypted_columns() -> dict[str, str]:
    """column name -> the type it was declared with, read from the models."""
    found: dict[str, str] = {}
    pattern = (
        r'(\w+)\s*=\s*(?:db\.)?Column\(\s*(?:db\.)?'
        r'(EncryptedString|EncryptedSearchableString)\b'
    )
    for f in (ROOT / 'models').glob('*.py'):
        text = f.read_text(encoding='utf-8', errors='ignore')
        import re

        for m in re.finditer(pattern, text):
            found[m.group(1)] = m.group(2)
    return found


def _is_model_attr(node: ast.AST, model_names: set[str]) -> tuple[str, str] | None:
    """Return (model, column) when *node* looks like ``Model.column``."""
    if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
        return None
    if node.value.id not in model_names:
        return None
    return node.value.id, node.attr


def _model_names() -> set[str]:
    names: set[str] = set()
    for f in (ROOT / 'models').glob('*.py'):
        try:
            tree = ast.parse(f.read_text(encoding='utf-8', errors='ignore'))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names.add(node.name)
    return names


def _iter_calls(node: ast.AST):
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            yield child


def audit_file(path: pathlib.Path, encrypted: dict[str, str], models: set[str]):
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
    except (SyntaxError, OSError) as exc:
        return [('PARSE_ERROR', 0, f'{type(exc).__name__}: {exc}', '')]

    violations: list[tuple[str, int, str, str]] = []

    for call in _iter_calls(tree):
        func = call.func
        name = getattr(func, 'attr', None) or getattr(func, 'id', None)

        # Model.column.ilike(...) / .like(...)
        if name in ('ilike', 'like', 'notilike', 'notlike'):
            if name in ALLOWED_CALLS:
                continue
            target = (
                _is_model_attr(func.value, models)
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)
                else _is_model_attr(func, models)
            )
            if target and target[1] in encrypted:
                violations.append(
                    ('ENCRYPTED_LIKE', call.lineno, target[1], _line(path, call.lineno))
                )

        # filter_by(col=...) / filter(Model.col == ...)
        if name in ('filter_by', 'filter', 'get', 'get_or_404'):
            for kw in call.keywords:
                if kw.arg and kw.arg in encrypted:
                    if isinstance(kw.value, ast.Call) and (
                        getattr(kw.value.func, 'attr', '') in ALLOWED_CALLS
                    ):
                        continue
                    violations.append(
                        ('ENCRYPTED_FILTER', call.lineno, kw.arg, _line(path, call.lineno))
                    )
            for arg in call.args:
                # filter(Model.col == value)
                if isinstance(arg, ast.Compare) and len(arg.ops) == 1:
                    op = type(arg.ops[0]).__name__
                    if op not in ('Eq', 'NotEq'):
                        continue
                    target = _is_model_attr(arg.left, models)
                    if target and target[1] in encrypted:
                        violations.append(
                            ('ENCRYPTED_COMPARE', call.lineno, target[1], _line(path, call.lineno))
                        )

    # Attribute comparison outside a call:  Model.col == x
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if type(node.ops[0]).__name__ not in ('Eq', 'NotEq'):
                continue
            target = _is_model_attr(node.left, models)
            if target and target[1] in encrypted:
                violations.append(
                    ('ENCRYPTED_COMPARE', node.lineno, target[1], _line(path, node.lineno))
                )
    return violations


def _line(path: pathlib.Path, lineno: int) -> str:
    try:
        return (
            path.read_text(encoding='utf-8', errors='ignore').splitlines()[lineno - 1].strip()[:100]
        )
    except (IndexError, OSError):
        return ''


BASELINE_PATH = pathlib.Path(__file__).with_name('encrypted_query_baseline.json')


def _load_baseline() -> set[str]:
    """Recorded pre-existing violations, keyed by file and source text.

    The gate's job is to stop a *new* dead query being introduced. Failing on the
    46 that already exist would leave the build permanently red, which blocks
    every future change and gets the gate ignored within a week. So the existing
    debt is recorded here, and the build fails only when the count exceeds it or
    a site is not in the baseline. The baseline is expected to shrink: when a
    search is converted to Patient.search, delete its entry, and the next run
    reports the baseline as stale until it matches again.
    """
    if not BASELINE_PATH.exists():
        return set()
    import json

    try:
        return set(json.loads(BASELINE_PATH.read_text(encoding='utf-8')).get('sites', []))
    except (ValueError, OSError):
        return set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    encrypted = collect_encrypted_columns()
    models = _model_names()
    total: list[tuple[str, int, str, str, str]] = []

    for f in python_files():
        for kind, lineno, column, text in audit_file(f, encrypted, models):
            total.append((str(f.relative_to(ROOT)), lineno, kind, column, text))

    by_kind = collections.Counter(v[2] for v in total)

    baseline = _load_baseline()
    # total entries are (path, lineno, kind, column, source_text)
    site = lambda v: f'{v[0]}::{v[2]}::{v[4]}'  # noqa: E731
    baseline_sites = set(baseline)
    new = [v for v in total if site(v) not in baseline_sites]
    stale = sorted(baseline_sites - {site(v) for v in total})

    if not args.quiet:
        print(f'encrypted columns tracked : {len(encrypted)}')
        print(f'files scanned             : {sum(1 for _ in python_files())}')
        print(f'violations found          : {len(total)}')
        print(f'recorded in baseline      : {len(total) - len(new)}')
        print(f'NEW (block the build)     : {len(new)}')
        if stale:
            print(f'baseline is stale         : {len(stale)} entr(y/ies) no longer reproduce')
        print()
        if new:
            for path, lineno, kind, column, text in new:
                print(f'NEW  {kind}  {path}:{lineno}  [{column}]')
                print(f'    {text}')
        elif not args.quiet:
            print('no new encrypted-query violations')

    print(
        f'\nRESULT: {len(new)} new violation(s) of {len(total)} total '
        f'({", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())) or "none"})'
    )
    return 1 if new else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
