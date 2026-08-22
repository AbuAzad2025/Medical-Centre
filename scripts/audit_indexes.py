"""
Index audit — find FK columns missing indexes + unused indexes.

Run:  python scripts/audit_indexes.py
Outputs a report and optionally generates CREATE INDEX statements.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app_factory import create_app
from app.extensions import db

# FK columns WITHOUT an index are candidates. Composite-leading-column
# indexes already cover the FK, so we check for any index whose FIRST
# column matches the FK column.
MISSING_FK_SQL = """
SELECT c.conrelid::regclass AS table_name,
       a.attname AS column_name,
       c.conname AS fk_name,
       EXISTS (
         SELECT 1 FROM pg_index i
         WHERE i.indrelid = c.conrelid
           AND i.indkey[0] = a.attnum
       ) AS has_leading_index
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid
  AND a.attnum = c.conkey[1]
  AND a.attnum > 0
WHERE c.contype = 'f'
ORDER BY c.conrelid::regclass::text, a.attname;
"""

UNUSED_INDEX_SQL = """
SELECT s.schemaname, s.relname AS table_name, s.indexrelname AS index_name,
       s.idx_scan AS scans, pg_size_pretty(pg_relation_size(s.indexrelid)) AS size,
       pg_relation_size(s.indexrelid) AS size_bytes
FROM pg_stat_user_indexes s
JOIN pg_index i ON s.indexrelid = i.indexrelid
WHERE s.idx_scan < 50          -- rarely scanned
  AND NOT i.indisunique        -- never drop unique (correctness)
  AND NOT i.indisprimary       -- never drop PK
  AND s.indexrelname NOT LIKE '%pkey%'
ORDER BY pg_relation_size(s.indexrelid) DESC;
"""

app = create_app('testing')
with app.app_context():
    print('=' * 70)
    print('FOREIGN KEY COLUMNS MISSING INDEXES')
    print('=' * 70)
    rows = db.session.execute(db.text(MISSING_FK_SQL)).fetchall()
    missing = [r for r in rows if not r[3]]
    if not missing:
        print('NO ISSUES IDENTIFIED — all FK columns have leading indexes.')
    else:
        for r in missing:
            table, column, fk_name = r[0], r[1], r[2]
            idx_name = (
                f'ix_{table}_{column}'
                if '.' not in str(table)
                else f'ix_{str(table).split(".")[-1]}_{column}'
            )
            print(f'  {table}.{column}  (fk: {fk_name})')
    print(f'\nTotal missing: {len(missing)} / {len(rows)} FK columns')

    print()
    print('=' * 70)
    print('GENERATED CREATE INDEX STATEMENTS (for missing)')
    print('=' * 70)
    for r in missing:
        table = str(r[0]).split('.')[-1]
        column = r[1]
        idx = f'idx_audit_fk_{table}_{column}'
        print(f'CREATE INDEX IF NOT EXISTS {idx} ON {table}({column});')

    print()
    print('=' * 70)
    print('RARELY-USED INDEXES (scans < 50) — review before dropping')
    print('=' * 70)
    try:
        unused = db.session.execute(db.text(UNUSED_INDEX_SQL)).fetchall()
        if not unused:
            print('No rarely-used indexes found.')
        for r in unused[:30]:
            print(f'  {r[1]}.{r[2]}  scans={r[3]}  size={r[4]}')
    except Exception as e:
        print(f'(stats unavailable: {e})')
