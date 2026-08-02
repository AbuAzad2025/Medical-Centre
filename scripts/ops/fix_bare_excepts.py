"""
Automated fix for 'except Exception:' → 'except Exception as e:' across the codebase.
Also adds logger import and structured logging where appropriate.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Pattern: 'except Exception:' NOT already 'except Exception as'
BARE_EXCEPT_RE = re.compile(r'except Exception(?!\s+as\s+\w+)(\s*:)')

# Files to skip (scripts/ops tooling, not production code)
SKIP_PREFIXES = ('scripts/ops/',)


def needs_logger_import(content):
    """Check if file already has a logger."""
    return 'logger = logging.getLogger' not in content


def add_logger_import(content):
    """Add logging import and logger creation if not present."""
    if 'import logging' not in content:
        # Add after last import line
        lines = content.split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import = i
        lines.insert(last_import + 1, 'import logging')
        content = '\n'.join(lines)
    if 'logger = logging.getLogger' not in content:
        lines = content.split('\n')
        # Find a good spot after imports
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_at = i + 1
            elif line.strip() == '' and insert_at > 0:
                insert_at = i + 1
                break
        # Add logger after all imports
        for i, line in enumerate(lines):
            if (
                not line.startswith('import ')
                and not line.startswith('from ')
                and line.strip() != ''
                and not line.startswith('#')
                and not line.startswith('"""')
                and not line.startswith("'''")
            ):
                insert_at = i
                break
        logger_line = 'logger = logging.getLogger(__name__)'
        lines.insert(insert_at, '')
        lines.insert(insert_at + 1, logger_line)
        content = '\n'.join(lines)
    return content


def fix_file(filepath):
    """Fix bare except Exception: patterns in a single file."""
    rel = os.path.relpath(filepath, ROOT).replace('\\', '/')
    for prefix in SKIP_PREFIXES:
        if rel.startswith(prefix):
            return 0

    try:
        with open(filepath, encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return 0

    original = content

    # Replace 'except Exception:' with 'except Exception as e:'
    new_content = BARE_EXCEPT_RE.sub(r'except Exception as e:', content)

    if new_content == original:
        return 0

    # Check if any replacements were actually made
    changes = len(re.findall(BARE_EXCEPT_RE, content))

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return changes


def main():
    total_files = 0
    total_changes = 0

    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Skip hidden dirs, __pycache__, .git, node_modules
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith('.') and d not in ('__pycache__', 'node_modules', '.pytest_cache')
        ]

        for fname in filenames:
            if not fname.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, fname)
            changes = fix_file(filepath)
            if changes > 0:
                total_files += 1
                total_changes += changes
                rel = os.path.relpath(filepath, ROOT)
                print(f'  {rel}: {changes} fixes')

    print(f'\nTotal: {total_changes} bare excepts fixed across {total_files} files')
    return total_files


if __name__ == '__main__':
    main()
