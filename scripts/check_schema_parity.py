#!/usr/bin/env python3
"""Ensure every ORM __tablename__ has a matching Alembic create_table (static check)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect_migration_tables() -> set[str]:
    tables: set[str] = set()
    for p in (ROOT / "migrations/versions").glob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        tables.update(re.findall(r"create_table\(\s*['\"]([^'\"]+)['\"]", text))
    return tables


def collect_orm_tables() -> set[str]:
    tables: set[str] = set()
    for base in (ROOT / "models", ROOT / "app"):
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            tables.update(re.findall(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", text))
    return tables


def main() -> int:
    orm = collect_orm_tables()
    mig = collect_migration_tables()
    missing = sorted(orm - mig)
    if missing:
        print("ORM tables without migration create_table:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        return 1
    extra = sorted(mig - orm)
    if extra:
        print(f"Note: {len(extra)} migration-only tables (no ORM model)", file=sys.stderr)
    print(f"Schema parity OK: {len(orm)} ORM tables match migrations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
