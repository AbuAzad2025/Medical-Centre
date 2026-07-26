"""
Bare Exception Audit Script
Scans the codebase for dangerous bare `except:` and `except: pass` blocks
and reports them for immediate remediation with structured logging.
"""
import os
import sys
import re
from pathlib import Path
from typing import List, Dict

# Force UTF-8 stdout on Windows to avoid UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCAN_DIRS = [
    'models', 'routes', 'services', 'app', 'utils', 'app_factory.py', 'config.py',
]

# Patterns that flag dangerous exception handling
DANGEROUS_PATTERNS = [
    (r'^\s*except\s*:\s*$', 'bare except:'),
    (r'^\s*except\s*Exception\s*:\s*$', 'bare except Exception:'),
    (r'except\s*:\s*pass', 'except: pass'),
    (r'except\s*Exception\s*:\s*pass', 'except Exception: pass'),
]

# Allowed patterns (re-raise, explicit handling, logging)
ALLOWED_PATTERNS = [
    r'except\s+\w+\s+as\s+\w+\s*:\s*(?!\s*pass\s*$)',  # named exception with real handling
    r'raise\s+',  # re-raise
    r'logger\.',  # logging present
    r'logging\.',  # logging present
    r'_alert_admin',  # admin alert present
]


def _is_allowed_line(line: str) -> bool:
    for pat in ALLOWED_PATTERNS:
        if re.search(pat, line):
            return True
    return False


def scan_file(filepath: Path) -> List[Dict]:
    findings = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return findings

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        for pattern, label in DANGEROUS_PATTERNS:
            if re.search(pattern, stripped):
                if not _is_allowed_line(stripped):
                    findings.append({
                        'file': str(filepath),
                        'line': lineno,
                        'code': stripped,
                        'pattern': label,
                    })
                break
    return findings


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    all_findings: List[Dict] = []

    for subdir in SCAN_DIRS:
        target = root / subdir if not subdir.endswith('.py') else root / subdir
        if target.is_file():
            findings = scan_file(target)
            all_findings.extend(findings)
        elif target.is_dir():
            for pyfile in target.rglob('*.py'):
                if pyfile.name.startswith('test_'):
                    continue
                findings = scan_file(pyfile)
                all_findings.extend(findings)

    by_file: Dict[str, List[Dict]] = {}
    for f in all_findings:
        by_file.setdefault(f['file'], []).append(f)

    print("=" * 70)
    print("Bare Exception Audit Report")
    print("=" * 70)
    print(f"Total dangerous exception blocks found: {len(all_findings)}")
    print(f"Files affected: {len(by_file)}")
    print()

    if not all_findings:
        print("[OK] No bare exception blocks detected.")
        return 0

    for filepath, findings in sorted(by_file.items()):
        rel = os.path.relpath(filepath, root)
        print(f"\n[FILE] {rel}  ({len(findings)} occurrence(s))")
        for f in findings:
            print(f"   L{f['line']:4d}  [{f['pattern']}]  {f['code'][:80]}")

    print("\n" + "=" * 70)
    print("REMEDIATION TEMPLATE")
    print("=" * 70)
    print("""
Replace:
    except:
        pass

With:
    except Exception as exc:
        logger.error("Operation failed: %s", exc, exc_info=True)
        _alert_admin('CRITICAL', 'Operation failed', error=str(exc))
        raise  # or return appropriate error response
""")
    return 1


if __name__ == '__main__':
    sys.exit(main())
