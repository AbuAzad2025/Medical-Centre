#!/usr/bin/env python3
"""
SQLAlchemy 1.x → 2.0 Automated Query Refactor Script
Targets the most common legacy patterns in the codebase.
Uses regex with balanced-parenthesis matching for safe transformation.
Preserves comments and indentation; run 'black' afterward if desired.
"""

import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Directories to refactor
SCAN_DIRS = ['services', 'routes', 'app', 'models', 'utils']

# Regex to detect if file already imports select / func from sqlalchemy
_HAS_SELECT_IMPORT = re.compile(r'from\s+sqlalchemy\s+import\s+[^\n]*\bselect\b')
_HAS_FUNC_IMPORT = re.compile(r'from\s+sqlalchemy\s+import\s+[^\n]*\bfunc\b')
_HAS_DB_IMPORT = re.compile(r'\bdb\b')


def _balanced_paren(text: str, start: int) -> int:
    """Return index of the closing paren matching the open paren at start."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _extract_call_arg(text: str, call_start: int) -> tuple[str, int]:
    """Given text starting at 'call_name(', extract the full argument string and end index."""
    open_idx = text.find('(', call_start)
    if open_idx == -1:
        return '', call_start
    close_idx = _balanced_paren(text, open_idx)
    if close_idx == -1:
        return '', call_start
    return text[open_idx + 1 : close_idx], close_idx


def _add_import(content: str, needed: list[str]) -> str:
    """Add missing sqlalchemy imports at the top of the file."""
    if not needed:
        return content
    import_line = f'from sqlalchemy import {", ".join(needed)}\n'
    # Insert after any existing from sqlalchemy import
    m = re.search(r'(from sqlalchemy import [^\n]+\n)', content)
    if m:
        existing = m.group(1).rstrip('\n')
        # Check if all needed are already in existing
        missing = [n for n in needed if n not in existing]
        if not missing:
            return content
        new_import = existing + ', ' + ', '.join(missing)
        content = content[: m.start()] + new_import + '\n' + content[m.end() :]
        return content
    # Insert after docstring or at top
    lines = content.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('"""') or line.startswith("'''"):
            # Find end of docstring
            if line.count('"""') == 1 or line.count("'''") == 1:
                for j in range(i + 1, len(lines)):
                    if '"""' in lines[j] or "'''" in lines[j]:
                        insert_idx = j + 1
                        break
            else:
                insert_idx = i + 1
            break
    lines.insert(insert_idx, import_line.rstrip('\n'))
    return '\n'.join(lines)


def refactor_file(filepath: Path) -> tuple[int, str]:
    """Refactor a single file. Returns (number of replacements, new content)."""
    try:
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f'  [SKIP] {filepath}: {e}')
        return 0, ''

    original = content
    replacements = 0
    needs_select = False
    needs_func = False

    # We operate line-by-line for safety, but some queries span multiple lines.
    # Strategy: collapse logical lines (backslash continuation) and apply regex.
    # For simplicity, we only handle single-line patterns here.

    # Pattern helpers
    def replacer(pattern: re.Pattern, repl_func):
        nonlocal content, replacements, needs_select
        for m in pattern.finditer(content):
            try:
                new_text = repl_func(m)
                if new_text is not None:
                    content = content[: m.start()] + new_text + content[m.end() :]
                    replacements += 1
                    needs_select = True
            except Exception:
                pass  # Skip unsafe matches

    # ----- Model.query.filter_by(...).all() -----
    # We use a conservative regex that captures the whole line-like expression
    # This is imperfect for multi-line; we will iterate with a while loop.

    # To avoid catastrophic regex, we do manual scanning per line
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        original_line = line
        # Skip lines that are obviously strings or comments
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            new_lines.append(line)
            continue

        # Pattern 1: Model.query.filter_by(...).all()
        # We look for .filter_by( ... ).all()
        while True:
            m = re.search(r'(\b\w+\.query\.filter_by\()', line)
            if not m:
                break
            model_prefix = m.group(1).replace('.query.filter_by(', '')
            arg, close_idx = _extract_call_arg(
                line, m.start() + len(model_prefix) + len('.query.filter_by')
            )
            if close_idx == -1:
                break
            # Look for .all() or .first() or .count() after close_idx
            suffix_match = re.match(r'\s*\.(all|first|count|one)\(\)', line[close_idx + 1 :])
            if not suffix_match:
                break
            suffix = suffix_match.group(1)
            end_idx = close_idx + 1 + suffix_match.end()
            if suffix == 'count':
                needs_func = True
                new_expr = f'db.session.execute(select(func.count()).select_from({model_prefix}).filter_by({arg})).scalar()'
            elif suffix == 'one':
                new_expr = (
                    f'db.session.execute(select({model_prefix}).filter_by({arg})).scalar_one()'
                )
            else:
                new_expr = f'db.session.execute(select({model_prefix}).filter_by({arg})).scalars().{suffix}()'
            line = line[: m.start()] + new_expr + line[end_idx:]
            replacements += 1
            needs_select = True

        # Pattern 2: Model.query.filter(...).all()
        while True:
            m = re.search(r'(\b\w+\.query\.filter\()', line)
            if not m:
                break
            model_prefix = m.group(1).replace('.query.filter(', '')
            arg, close_idx = _extract_call_arg(
                line, m.start() + len(model_prefix) + len('.query.filter')
            )
            if close_idx == -1:
                break
            suffix_match = re.match(r'\s*\.(all|first|count|one)\(\)', line[close_idx + 1 :])
            if not suffix_match:
                break
            suffix = suffix_match.group(1)
            end_idx = close_idx + 1 + suffix_match.end()
            if suffix == 'count':
                needs_func = True
                new_expr = f'db.session.execute(select(func.count()).select_from({model_prefix}).where({arg})).scalar()'
            elif suffix == 'one':
                new_expr = f'db.session.execute(select({model_prefix}).where({arg})).scalar_one()'
            else:
                new_expr = (
                    f'db.session.execute(select({model_prefix}).where({arg})).scalars().{suffix}()'
                )
            line = line[: m.start()] + new_expr + line[end_idx:]
            replacements += 1
            needs_select = True

        # Pattern 3: Model.query.order_by(...).all()
        while True:
            m = re.search(r'(\b\w+\.query\.order_by\()', line)
            if not m:
                break
            model_prefix = m.group(1).replace('.query.order_by(', '')
            arg, close_idx = _extract_call_arg(
                line, m.start() + len(model_prefix) + len('.query.order_by')
            )
            if close_idx == -1:
                break
            suffix_match = re.match(r'\s*\.(all|first|count|one)\(\)', line[close_idx + 1 :])
            if not suffix_match:
                break
            suffix = suffix_match.group(1)
            end_idx = close_idx + 1 + suffix_match.end()
            if suffix == 'count':
                needs_func = True
                new_expr = f'db.session.execute(select(func.count()).select_from({model_prefix}).order_by({arg})).scalar()'
            elif suffix == 'one':
                new_expr = (
                    f'db.session.execute(select({model_prefix}).order_by({arg})).scalar_one()'
                )
            else:
                new_expr = f'db.session.execute(select({model_prefix}).order_by({arg})).scalars().{suffix}()'
            line = line[: m.start()] + new_expr + line[end_idx:]
            replacements += 1
            needs_select = True

        # Pattern 4: Model.query.limit(...).all()
        while True:
            m = re.search(r'(\b\w+\.query\.limit\()', line)
            if not m:
                break
            model_prefix = m.group(1).replace('.query.limit(', '')
            arg, close_idx = _extract_call_arg(
                line, m.start() + len(model_prefix) + len('.query.limit')
            )
            if close_idx == -1:
                break
            suffix_match = re.match(r'\s*\.(all|first|count|one)\(\)', line[close_idx + 1 :])
            if not suffix_match:
                break
            suffix = suffix_match.group(1)
            end_idx = close_idx + 1 + suffix_match.end()
            if suffix == 'count':
                needs_func = True
                new_expr = f'db.session.execute(select(func.count()).select_from({model_prefix}).limit({arg})).scalar()'
            elif suffix == 'one':
                new_expr = f'db.session.execute(select({model_prefix}).limit({arg})).scalar_one()'
            else:
                new_expr = (
                    f'db.session.execute(select({model_prefix}).limit({arg})).scalars().{suffix}()'
                )
            line = line[: m.start()] + new_expr + line[end_idx:]
            replacements += 1
            needs_select = True

        # Pattern 5: Model.query.all() / .first() / .count() / .one()
        while True:
            m = re.search(r'(\b\w+\.query)\s*\.(all|first|count|one)\(\)', line)
            if not m:
                break
            model_prefix = m.group(1).replace('.query', '')
            suffix = m.group(2)
            if suffix == 'count':
                needs_func = True
                new_expr = (
                    f'db.session.execute(select(func.count()).select_from({model_prefix})).scalar()'
                )
            elif suffix == 'one':
                new_expr = f'db.session.execute(select({model_prefix})).scalar_one()'
            else:
                new_expr = f'db.session.execute(select({model_prefix})).scalars().{suffix}()'
            line = line[: m.start()] + new_expr + line[m.end() :]
            replacements += 1
            needs_select = True

        # Pattern 6: Model.query.get(id)
        while True:
            m = re.search(r'(\b\w+\.query\.get\()', line)
            if not m:
                break
            model_prefix = m.group(1).replace('.query.get(', '')
            arg, close_idx = _extract_call_arg(
                line, m.start() + len(model_prefix) + len('.query.get')
            )
            if close_idx == -1:
                break
            end_idx = close_idx + 1
            new_expr = f'db.session.get({model_prefix}, {arg})'
            line = line[: m.start()] + new_expr + line[end_idx:]
            replacements += 1
            needs_select = False  # get() doesn't need select import

        # Pattern 7: db.session.query(Model).filter(...).all()
        while True:
            m = re.search(r'(\bdb\.session\.query\()', line)
            if not m:
                break
            model_arg, close_idx = _extract_call_arg(line, m.start() + len('db.session.query'))
            if close_idx == -1:
                break
            rest = line[close_idx + 1 :]
            # Look for .filter(...) or .filter_by(...) then .all/first/count/one
            chain_match = re.match(
                r'\s*\.(filter|filter_by)\((.*)\)\s*\.(all|first|count|one)\(\)', rest
            )
            if chain_match:
                chain_type = chain_match.group(1)
                chain_arg = chain_match.group(2)
                suffix = chain_match.group(3)
                end_idx = close_idx + 1 + chain_match.end()
                if chain_type == 'filter':
                    if suffix == 'count':
                        needs_func = True
                        new_expr = f'db.session.execute(select(func.count()).select_from({model_arg}).where({chain_arg})).scalar()'
                    elif suffix == 'one':
                        new_expr = f'db.session.execute(select({model_arg}).where({chain_arg})).scalar_one()'
                    else:
                        new_expr = f'db.session.execute(select({model_arg}).where({chain_arg})).scalars().{suffix}()'
                elif suffix == 'count':
                    needs_func = True
                    new_expr = f'db.session.execute(select(func.count()).select_from({model_arg}).filter_by({chain_arg})).scalar()'
                elif suffix == 'one':
                    new_expr = f'db.session.execute(select({model_arg}).filter_by({chain_arg})).scalar_one()'
                else:
                    new_expr = f'db.session.execute(select({model_arg}).filter_by({chain_arg})).scalars().{suffix}()'
                line = line[: m.start()] + new_expr + line[end_idx:]
                replacements += 1
                needs_select = True
                break  # Only one per line for safety
            # Look for .all() / .first() directly after query(Model)
            suffix_match = re.match(r'\s*\.(all|first|count|one)\(\)', rest)
            if suffix_match:
                suffix = suffix_match.group(1)
                end_idx = close_idx + 1 + suffix_match.end()
                if suffix == 'count':
                    needs_func = True
                    new_expr = f'db.session.execute(select(func.count()).select_from({model_arg})).scalar()'
                elif suffix == 'one':
                    new_expr = f'db.session.execute(select({model_arg})).scalar_one()'
                else:
                    new_expr = f'db.session.execute(select({model_arg})).scalars().{suffix}()'
                line = line[: m.start()] + new_expr + line[end_idx:]
                replacements += 1
                needs_select = True
                break
            break  # No match

        if line != original_line:
            needs_select = True  # Mark anyway if any change happened
        new_lines.append(line)

    content = '\n'.join(new_lines)

    # Add imports if needed
    if needs_select or needs_func:
        imports_needed = []
        if needs_select and not _HAS_SELECT_IMPORT.search(content):
            imports_needed.append('select')
        if needs_func and not _HAS_FUNC_IMPORT.search(content):
            imports_needed.append('func')
        content = _add_import(content, imports_needed)

    return replacements, content


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    total_replacements = 0
    files_modified = 0

    for subdir in SCAN_DIRS:
        target = root / subdir
        if not target.exists():
            continue
        for pyfile in target.rglob('*.py'):
            if pyfile.name.startswith('test_'):
                continue
            if pyfile.name == 'audit_sqlalchemy_1x_queries.py':
                continue
            count, new_content = refactor_file(pyfile)
            if count > 0:
                total_replacements += count
                files_modified += 1
                with open(pyfile, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                rel = os.path.relpath(pyfile, root)
                print(f'[MODIFIED] {rel}  ({count} replacement(s))')

    print(f'\n{"=" * 60}')
    print('SQLAlchemy 2.0 Auto-Refactor Complete')
    print(f'{"=" * 60}')
    print(f'Files modified: {files_modified}')
    print(f'Total replacements: {total_replacements}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
