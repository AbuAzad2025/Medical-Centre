"""Generate unique_constraint_audit.json by introspecting the live DB schema.

P0C-002: enumerate every unique constraint / unique index, classify it, and emit
a machine-readable audit that downstream de-duplication tooling can consume.
"""
from __future__ import annotations

import json
from pathlib import Path

from app_factory import create_app
from app.extensions import db
from sqlalchemy import text

ROOT = Path(__file__).parent.parent


def classify(table: str, columns: list[str]) -> str:
    cols = {c.lower() for c in columns}
    if "tenant_id" in cols:
        return "tenant-scoped"
    if "branch_id" in cols or "fiscal_year" in cols:
        return "branch/fiscal"
    if "deleted_at" in cols:
        return "soft-delete"
    if table in {"approval_decision", "clinical_decision"} or "decision" in table:
        return "decision"
    # Single-column uniqueness on a natural key (username, code, key, email, ...)
    if len(columns) == 1:
        return "global"
    return "unknown"


def _parse_cols(value) -> list[str]:
    """psycopg may return a PostgreSQL array literal ('{a,b}') as a string."""
    if isinstance(value, (list, tuple)):
        return [str(c) for c in value]
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("{") and s.endswith("}"):
            s = s[1:-1]
        if not s:
            return []
        return [c.strip() for c in s.split(",") if c.strip()]
    return []


def main() -> None:
    app = create_app("testing")
    with app.app_context():
        rows = db.session.execute(text("""
            SELECT
                tc.table_name,
                tc.constraint_name,
                array_agg(kcu.column_name ORDER BY kcu.ordinal_position) AS columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'UNIQUE'
              AND tc.table_schema = 'public'
            GROUP BY tc.table_name, tc.constraint_name
            ORDER BY tc.table_name, tc.constraint_name
        """)).fetchall()

        # Also capture unique indexes not backed by a named constraint.
        idx_rows = db.session.execute(text("""
            SELECT
                t.relname AS table_name,
                i.relname AS index_name,
                array_agg(a.attname ORDER BY a.attnum) AS columns
            FROM pg_index ix
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            WHERE ix.indisunique
              AND NOT ix.indisprimary
              AND NOT EXISTS (
                  SELECT 1 FROM information_schema.table_constraints tc
                  WHERE tc.constraint_name = i.relname
                    AND tc.constraint_type = 'UNIQUE'
              )
            GROUP BY t.relname, i.relname
            ORDER BY t.relname, i.relname
        """)).fetchall()

        seen = set()
        constraints = []
        for table, _name, raw_cols in list(rows) + [(r[0], r[1], r[2]) for r in idx_rows]:
            columns = _parse_cols(raw_cols)
            key = (table, tuple(columns))
            if key in seen:
                continue
            seen.add(key)
            constraints.append({
                "table": table,
                "columns": list(columns),
                "classification": classify(table, list(columns)),
            })

        by_class: dict[str, int] = {}
        for c in constraints:
            by_class[c["classification"]] = by_class.get(c["classification"], 0) + 1

        audit = {
            "constraints": constraints,
            "summary": {
                "total": len(constraints),
                "by_classification": by_class,
            },
            "duplicate_audit_queries": [
                {
                    "table": c["table"],
                    "columns": c["columns"],
                    "sql": (
                        f"SELECT {', '.join(c['columns'])}, COUNT(*) AS n "
                        f"FROM {c['table']} GROUP BY {', '.join(c['columns'])} "
                        f"HAVING COUNT(*) > 1"
                    ),
                }
                for c in constraints
                if c["classification"] in {"global", "tenant-scoped"}
            ],
        }

    out = ROOT / "unique_constraint_audit.json"
    out.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out} with {len(constraints)} unique constraints")


if __name__ == "__main__":
    main()
