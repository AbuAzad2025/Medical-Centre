#!/usr/bin/env python3
"""
CJK Guard - Check for Chinese/Japanese/Korean characters in code and templates.
This prevents accidental commit of non-ASCII characters that should be in translation files.
"""
import re
import sys
from pathlib import Path

# CJK Unicode ranges
CJK_PATTERN = re.compile(
    r'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff'
    r'\uf900-\ufaff\uff65-\uff9f]'
)

# Files to skip (allowlist)
SKIP_PATTERNS = [
    r'.*\.po$',           # Translation files
    r'.*\.mo$',           # Compiled translation files
    r'.*/migrations/.*',  # Migration files
    r'.*/tests/.*',       # Test files (may contain test data)
    r'.*/node_modules/.*',
    r'.*/.venv/.*',
    r'.*/__pycache__/.*',
    r'.*\.png$',
    r'.*\.jpg$',
    r'.*\.jpeg$',
    r'.*\.gif$',
    r'.*\.ico$',
    r'.*\.woff$',
    r'.*\.woff2$',
    r'.*\.ttf$',
    r'.*\.eot$',
]

def should_skip(filepath: Path) -> bool:
    """Check if file should be skipped"""
    rel_path = str(filepath)
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, rel_path):
            return True
    return False

def check_file(filepath: Path) -> list:
    """Check a file for CJK characters, return list of (line_num, line) tuples"""
    violations = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        for i, line in enumerate(content.splitlines(), 1):
            if CJK_PATTERN.search(line):
                violations.append((i, line.strip()))
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}")
    return violations

def main():
    root = Path(__file__).resolve().parents[2]
    
    # Collect all files to check
    files_to_check = []
    for ext in ['*.py', '*.html', '*.js', '*.ts', '*.css', '*.scss', '*.json', '*.yml', '*.yaml', '*.md', '*.txt']:
        files_to_check.extend(root.rglob(ext))
    
    total_violations = 0
    files_with_violations = 0
    
    for filepath in files_to_check:
        if should_skip(filepath):
            continue
        
        violations = check_file(filepath)
        if violations:
            files_with_violations += 1
            total_violations += len(violations)
            rel_path = filepath.relative_to(Path.cwd())
            print(f"\n{rel_path}:")
            for line_num, line in violations[:5]:  # Show first 5 violations per file
                print(f"  Line {line_num}: {line[:100]}")
            if len(violations) > 5:
                print(f"  ... and {len(violations) - 5} more violations")
    
    if total_violations > 0:
        print(f"\n❌ FAILED: Found {total_violations} CJK character violations in {files_with_violations} files")
        print("Please move CJK text to translation files (.po) or add files to skip list.")
        return 1
    else:
        print("✅ PASSED: No CJK characters found in source code")
        return 0

if __name__ == "__main__":
    sys.exit(main())