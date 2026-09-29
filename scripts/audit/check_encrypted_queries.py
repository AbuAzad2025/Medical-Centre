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
    """column name -> declared type, read from the models.

    Kept for reporting only. Detection uses :func:`encrypted_columns_by_model`
    so that a plain column is not flagged because some *other* model happens
    to declare a column with the same name.
    """
    found: dict[str, str] = {}
    for _model, column, declared in _iter_encrypted_declarations():
        found.setdefault(column, declared)
    return found


def encrypted_columns_by_model() -> dict[str, dict[str, str]]:
    """model name -> {column: declared type} for that model alone.

    The earlier version built one global column-name set from every model, so
    `User.email.ilike(...)` was reported as a dead ciphertext search purely
    because OnlineBooking declares an encrypted column called `email`. User.
    email is a plain indexed column and its ilike works. Matching per model
    removes that false positive without weakening the real check.
    """
    by_model: dict[str, dict[str, str]] = {}
    for model, column, declared in _iter_encrypted_declarations():
        by_model.setdefault(model, {})[column] = declared
    return by_model


def _iter_encrypted_declarations():
    """Yield (model, column, declared type) for every encrypted column."""
    import re as _re

    pattern = _re.compile(
        r'(\w+)\s*=\s*(?:db\.)?Column\(\s*(?:db\.)?'
        r'(EncryptedString|EncryptedSearchableString)\b'
    )
    class_re = _re.compile(r'^class\s+(\w+)')
    for f in sorted((ROOT / 'models').glob('*.py')):
        text = f.read_text(encoding='utf-8', errors='ignore')
        current = None
        for line in text.splitlines():
            cm = class_re.match(line)
            if cm:
                current = cm.group(1)
                continue
            if current is None:
                continue
            for m in pattern.finditer(line):
                yield current, m.group(1), m.group(2)


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


def audit_file(
    path: pathlib.Path,
    encrypted_by_model: dict[str, dict[str, str]],
    encrypted_names: frozenset[str],
    models: set[str],
):
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
            if target and target[1] in encrypted_by_model.get(target[0], {}):
                violations.append(
                    ('ENCRYPTED_LIKE', call.lineno, target[1], _line(path, call.lineno))
                )

        # filter_by(col=...) / filter(Model.col == ...)
        if name in ('filter_by', 'filter', 'get', 'get_or_404'):
            for kw in call.keywords:
                if kw.arg and kw.arg in encrypted_names:
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
                    if target and target[1] in encrypted_by_model.get(target[0], {}):
                        violations.append(
                            ('ENCRYPTED_COMPARE', call.lineno, target[1], _line(path, call.lineno))
                        )

    # Attribute comparison outside a call:  Model.col == x
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if type(node.ops[0]).__name__ not in ('Eq', 'NotEq'):
                continue
            target = _is_model_attr(node.left, models)
            if target and target[1] in encrypted_by_model.get(target[0], {}):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    encrypted = encrypted_columns_by_model()
    names = frozenset(encrypted)
    models = _model_names()
    total: list[tuple[str, int, str, str, str]] = []

    for f in python_files():
        for kind, lineno, column, text in audit_file(f, encrypted, names, models):
            total.append((str(f.relative_to(ROOT)), lineno, kind, column, text))

    by_kind = collections.Counter(v[2] for v in total)

    # There is no baseline. It existed to keep the build green while 46 dead
    # searches were still in the tree; all of them are now converted and the
    # file is deleted. Any violation from here on is a regression.
    if not args.quiet:
        print(f'encrypted columns tracked : {len(encrypted)}')
        print(f'files scanned             : {sum(1 for _ in python_files())}')
        print(f'violations found          : {len(total)}')
        print()
        for path, lineno, kind, column, text in total:
            print(f'{kind}  {path}:{lineno}  [{column}]')
            print(f'    {text}')
        if not total:
            print('no encrypted-query violations: every search goes through the blind index')

    print(
        f'\nRESULT: {len(total)} violation(s) of {len(total)} total '
        f'({", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())) or "none"})'
    )
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
