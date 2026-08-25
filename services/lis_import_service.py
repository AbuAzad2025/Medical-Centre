"""LIS Import Service (P1) — CSV/ASTM flat-file lab result ingestion.

Pipeline:
  1. parse_csv()          → normalized rows + structural errors
  2. map_rows()           → match instrument_code to LabTestCatalog.code
                             per-tenant; unmatched go to the exceptions queue
  3. import_results()     → writes LabResult rows ONLY for confirmed matches,
                             flagging out-of-range values as CRITICAL.

Design guarantees (each maps to a test):
  - Malformed lines are skipped and reported, never crash the batch.
  - Re-importing the same request+code+value is a no-op (dedup).
  - Nothing auto-inserts without a catalog match (human-in-the-loop).
"""

import csv
import io
import logging
from datetime import UTC, datetime

from flask import g
from sqlalchemy import func, select

from app.extensions import db
from utils.db_safety import safe_commit

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {'test_code', 'value'}
SUPPORTED_DELIMITERS = [',', ';', '\t', '|']


class LISImportError(Exception):
    pass


def _sniff_delimiter(sample_line: str) -> str:
    for d in SUPPORTED_DELIMITERS:
        if d in sample_line:
            return d
    return ','


def parse_csv(content: bytes) -> dict:
    """Parse raw CSV bytes → {'rows': [...], 'errors': [...]}.

    Accepts an optional UTF-8 BOM. Requires header row containing at least
    test_code and value; patient/request identifiers are optional but at
    least one of (request_id) should be present for routing.
    """
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise LISImportError('encoding') from None

    if not text.strip():
        raise LISImportError('empty_file')

    first_line = text.splitlines()[0]
    delim = _sniff_delimiter(first_line)

    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if not reader.fieldnames:
        raise LISImportError('missing_header')

    normalized = {}
    for f in reader.fieldnames:
        key = (f or '').strip().lower().replace(' ', '_')
        normalized[f] = key
    reader.fieldnames = [normalized.get(f, f) for f in reader.fieldnames]

    lower_fields = {f.lower().replace(' ', '_') for f in reader.fieldnames}
    missing = REQUIRED_COLUMNS - lower_fields
    if missing:
        raise LISImportError(f'missing_columns:{",".join(sorted(missing))}')

    rows, errors = [], []
    for i, row in enumerate(reader, start=2):
        code = (row.get('test_code') or '').strip()
        value = (row.get('value') or '').strip()
        if not code or not value:
            errors.append({'line': i, 'error': 'missing_required_field'})
            continue
        rows.append(
            {
                'line': i,
                'request_id': _to_int(row.get('request_id')),
                'patient_national_id': (row.get('national_id') or '').strip(),
                'test_code': code,
                'value': value,
                'unit': (row.get('unit') or '').strip() or None,
                'performed_at': (row.get('performed_at') or '').strip() or None,
            }
        )
    return {'rows': rows, 'errors': errors}


def _to_int(v):
    try:
        return int(str(v).strip()) if v not in (None, '') else None
    except (TypeError, ValueError):
        return None


def map_rows(rows: list[dict]) -> dict:
    """Attach catalog matches; unmatched land in `unmatched` queue."""
    from models.lab_test_catalog import LabTestCatalog

    codes = {r['test_code'] for r in rows}
    catalog = (
        db.session.execute(select(LabTestCatalog).where(LabTestCatalog.code.in_(codes)))
        .scalars()
        .all()
    )
    by_code = {c.code: c for c in catalog}

    matched, unmatched = [], []
    for r in rows:
        cat = by_code.get(r['test_code'])
        if cat:
            r['catalog'] = {
                'id': cat.id,
                'name_ar': cat.name_ar,
                'unit': cat.unit,
                'reference_range': cat.default_reference_range,
                'critical_low': cat.critical_low,
                'critical_high': cat.critical_high,
            }
            matched.append(r)
        else:
            r['reason'] = 'unknown_test_code'
            unmatched.append(r)
    return {'matched': matched, 'unmatched': unmatched}


def _is_critical(value: str, cat: dict | None) -> bool:
    """Numeric compare against critical_low/high when both are numeric."""
    if not cat:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    try:
        lo = float(cat['critical_low']) if cat.get('critical_low') else None
    except (TypeError, ValueError):
        lo = None
    try:
        hi = float(cat['critical_high']) if cat.get('critical_high') else None
    except (TypeError, ValueError):
        hi = None
    if lo is not None and v <= lo:
        return True
    return bool(hi is not None and v >= hi)


def import_results(rows: list[dict], performed_by: int) -> dict:
    """Write confirmed LabResult rows. Dedup on (request_id, test_code, value).

    Rows lacking request_id are rejected into `skipped` — P1 routes results
    to existing requests only; free-standing results need human triage.
    """
    from models.lab_request import LabResult

    imported, skipped, duplicates = [], [], []

    for r in rows:
        rid = _to_int(r.get('request_id'))
        if not rid:
            r['reason'] = 'missing_request_id'
            skipped.append(r)
            continue

        exists = (
            db.session.execute(
                select(func.count())
                .select_from(LabResult)
                .where(
                    LabResult.request_id == rid,
                    LabResult.test_code == r['test_code'],
                    LabResult.value == r['value'],
                )
            ).scalar()
            or 0
        )
        if exists:
            duplicates.append(r)
            continue

        cat = r.get('catalog') or {}
        lr = LabResult(
            tenant_id=getattr(g, 'tenant_id', None),
            request_id=rid,
            patient_id=_resolve_patient_id(rid),
            performed_by=performed_by,
            test_code=r['test_code'],
            test_name=(cat.get('name_ar') or r['test_code'])[:120],
            value=str(r['value'])[:120],
            unit=(r.get('unit') or cat.get('unit') or '')[:40],
            reference_range=(cat.get('reference_range') or '')[:120],
            status='READY',
            is_critical=_is_critical(r['value'], cat),
        )
        db.session.add(lr)
        imported.append(r)

    safe_commit(db.session, error_message='LIS import failed', reraise=True)
    return {
        'imported_count': len(imported),
        'duplicates_count': len(duplicates),
        'skipped': skipped,
        'imported_ids': [id(x) for x in imported],
        'imported_at': datetime.now(UTC).isoformat(),
    }


def _resolve_patient_id(request_id: int):
    from models.lab_request import LabRequest

    return db.session.execute(
        select(LabRequest.patient_id).where(LabRequest.id == request_id)
    ).scalar()


def watch_directory_once(directory: str, performed_by: int = 0) -> list[dict]:
    """Process any *.csv files dropped into `directory`; archive after import."""
    from pathlib import Path

    reports = []
    for path in Path(directory).glob('*.csv'):
        report = {'file': path.name}
        try:
            parsed = parse_csv(path.read_bytes())
            mapping = map_rows(parsed['rows'])
            result = import_results(mapping['matched'], performed_by)
            report.update(
                success=True,
                parsed=parsed,
                unmatched=mapping['unmatched'],
                **{'imported_count': result['imported_count']},
            )
            path.rename(path.with_suffix('.csv.done'))
        except Exception as e:
            logger.warning('LIS watcher failed on %s: %s', path.name, e)
            report.update(success=False, error=str(e))
        reports.append(report)
    return reports
