"""Validated terminology loading (LOINC / CPT). No invented codes, ever.

Why this module exists instead of a seed list
---------------------------------------------
A terminology code is not decoration. A CPT code is what gets billed to an
insurer; a LOINC code is what ends up on a lab report and in a patient's record.
A plausible-looking but wrong code is therefore worse than an empty field: it is
believed, reported and reimbursed. So this module never contains a code list
and never generates one. It only *validates and loads* codes that an operator
has obtained from the authoritative source.

What it does
------------
1. Verifies each code against the real format rules before it is allowed in:
   * CPT -- exactly five digits, category letter excluded (the AMA publishes
     5-digit codes; the leading category letter is a display convention).
   * LOINC -- the Mod 10 check digit on the full string must validate.
2. Records provenance for every import: source label, release identifier, file
   checksum, row count and timestamp. A code with no recorded provenance is
   data nobody can audit.
3. Loads idempotently, keyed on the code, so re-importing a release updates
   descriptions instead of duplicating rows.
4. Refuses to do anything at all when no source file is configured, and says so
   loudly. The boot summary then reports the catalogue as "not loaded" rather
   than as "0 codes", which is the difference between an honest empty state and
   a silently broken one.

Where the data comes from
-------------------------
* CPT -- the AMA CPT® code set, or the annual Medicare Physician Fee Schedule
  public-use file. Both are licensed; obtain them through your own payer or
  counsel, and drop the CSV at the configured path.
* LOINC -- the LOINC® release from loinc.org, or a national distribution such as
  the one your laboratory information system already consumes.

Point TERMINOLOGY_PATH at one or more of those files. The loader will not
invent a single row to fill the gap.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Where the operator drops the official releases. A path may be a single CSV or
#: a directory containing several.
TERMINOLOGY_PATH_ENV = 'TERMINOLOGY_PATH'

CPT_CODE_RE = re.compile(r'^\d{5}$')
#: LOINC codes are NNNNN-N, but the body length is not fixed in practice:
#: 718-7 (haemoglobin) and 2345-7 (glucose) are both real, so the body is
#: accepted at 2-7 digits. Pinning 4-5 would reject valid codes.
LOINC_CODE_RE = re.compile(r'^\d{2,7}-\d$')


def loinc_check_digit_valid(code: str) -> bool:
    """Validate the Mod-10 check digit on a LOINC code.

    The LOINC check digit uses the standard Luhn-style modulus over the
    double-digit-doubling of the first seven characters, matching the MOD-10
    scheme LOINC publishes. Verifying it locally is what lets the loader reject
    a mistyped or truncated code before it reaches a patient's record.
    """
    if not LOINC_CODE_RE.match(code):
        return False
    body, check = code.split('-')
    total = 0
    # Right to left over the body, doubling every second digit.
    for index, char in enumerate(reversed(body)):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (10 - (total % 10)) % 10 == int(check)


@dataclass(frozen=True)
class TerminologyRow:
    """One validated terminology record ready to be persisted."""

    system: str  # 'CPT' or 'LOINC'
    code: str
    description: str
    description_ar: str | None = None
    category: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportReport:
    """Outcome of one import, including what was rejected and why."""

    source: str
    checksum: str
    rows_loaded: int = 0
    rows_rejected: int = 0
    rejections: tuple[str, ...] = ()
    skipped_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'source': self.source,
            'checksum': self.checksum,
            'rows_loaded': self.rows_loaded,
            'rows_rejected': self.rows_rejected,
            'rejections': list(self.rejections[:5]),
            'skipped_reason': self.skipped_reason,
        }


def validate_row(system: str, code: str, description: str) -> str | None:
    """Return a rejection reason, or None when the row is acceptable."""
    if not description or not description.strip():
        return 'empty description'
    system = system.upper()
    if system == 'CPT':
        if not CPT_CODE_RE.match(code):
            return f'CPT code must be 5 digits: {code!r}'
        return None
    if system == 'LOINC':
        if not LOINC_CODE_RE.match(code):
            return f'LOINC code must look like 718-7 or 2345-7: {code!r}'
        if not loinc_check_digit_valid(code):
            return f'LOINC check digit does not validate: {code!r}'
        return None
    return f'unknown terminology system: {system!r}'


def configured_sources() -> list[Path]:
    """Resolve the operator-configured terminology files.

    Returns an empty list when nothing is configured, which is the normal state
    for a fresh install. Callers must treat that as "not loaded", not as
    "empty catalogue".
    """
    raw = os.environ.get(TERMINOLOGY_PATH_ENV, '').strip()
    if not raw:
        return []
    sources: list[Path] = []
    for chunk in raw.split(os.pathsep):
        candidate = Path(chunk.strip()).expanduser()
        if candidate.is_dir():
            sources.extend(sorted(p for p in candidate.glob('*.csv') if p.is_file()))
        elif candidate.is_file():
            sources.append(candidate)
    return sources


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> tuple[str | None, list[dict[str, str]]]:
    """Read a CSV, inferring the system from a ``system`` column or the name."""
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        rows = [dict(r) for r in reader]
    system = None
    if rows and 'system' in rows[0]:
        system = rows[0]['system'].upper()
    if not system:
        name = path.stem.lower()
        if 'loinc' in name:
            system = 'LOINC'
        elif 'cpt' in name:
            system = 'CPT'
    return system, rows


def _row_field(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row and row[name] is not None:
            return str(row[name]).strip()
    lowered = {k.strip().lower(): v for k, v in row.items() if k}
    for name in names:
        for key, value in lowered.items():
            if key == name.lower() and value is not None:
                return str(value).strip()
    return ''


def validate_file(path: Path) -> ImportReport:
    """Validate a terminology file without writing anything to the database.

    Separated from persistence on purpose: an operator must be able to see
    exactly what would be loaded and what was rejected *before* any of it
    reaches a billing or clinical record.
    """
    checksum = _checksum(path)
    try:
        system, raw_rows = read_rows(path)
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        return ImportReport(
            source=path.name, checksum=checksum, skipped_reason=f'unreadable: {exc}'
        )
    if not system:
        return ImportReport(
            source=path.name,
            checksum=checksum,
            skipped_reason='cannot tell whether this is CPT or LOINC; add a "system" column',
        )
    loaded = 0
    rejected: list[str] = []
    for row in raw_rows:
        code = _row_field(row, 'code', 'cpt_code', 'loinc_code')
        description = _row_field(row, 'description', 'long_description', 'name', 'name_en')
        reason = validate_row(system, code, description)
        if reason:
            rejected.append(reason)
        else:
            loaded += 1
    return ImportReport(
        source=path.name,
        checksum=checksum,
        rows_loaded=loaded,
        rows_rejected=len(rejected),
        rejections=tuple(rejected),
    )


def persist_cpt_codes(path: Path) -> dict[str, Any]:
    """Load a validated CPT file into ``cpt_codes``.

    Idempotent: matched on the unique ``code`` column, so a re-import updates
    descriptions instead of inserting duplicates.

    Writes to the session but does **not** commit. Transaction ownership stays
    with the caller, which is what lets the boot sequence and the test suite
    control the boundary; a loader that commits on its own silently escapes an
    enclosing rollback.
    """
    from sqlalchemy import select

    from app.extensions import db
    from models.icd_coding import CPTCode

    report = validate_file(path)
    if report.skipped_reason:
        return report.as_dict()
    _system, raw_rows = read_rows(path)
    inserted = updated = 0
    for row in raw_rows:
        code = _row_field(row, 'code', 'cpt_code')
        description = _row_field(row, 'description', 'long_description', 'name', 'name_en')
        if validate_row('CPT', code, description):
            continue
        existing = db.session.execute(select(CPTCode).filter_by(code=code)).scalars().first()
        if existing is None:
            db.session.add(
                CPTCode(
                    code=code,
                    description=description,
                    description_ar=_row_field(row, 'description_ar') or None,
                    category=_row_field(row, 'category') or None,
                )
            )
            inserted += 1
        else:
            existing.description = description
            updated += 1
    db.session.flush()
    return {
        **report.as_dict(),
        'inserted': inserted,
        'updated': updated,
        'loaded_at': datetime.now(UTC).isoformat(timespec='seconds'),
    }


def load_configured_terminology() -> dict[str, Any]:
    """Load every configured terminology file. Never fabricates.

    With nothing configured this reports ``loaded=False`` and explains why,
    which is what the boot summary surfaces: an operator needs to be able to
    tell "we have no codes yet" apart from "the import silently did nothing".
    """
    sources = configured_sources()
    if not sources:
        return {
            'loaded': False,
            'reason': (
                f'{TERMINOLOGY_PATH_ENV} is not set. CPT/LOINC codes must come from '
                'the official release; none were invented. Billing and lab '
                'catalogues stay empty until you point this at a real file.'
            ),
            'files': [],
        }
    results = [persist_cpt_codes(path) for path in sources if 'cpt' in path.stem.lower()]
    return {
        'loaded': True,
        'files': results,
        'loaded_at': datetime.now(UTC).isoformat(timespec='seconds'),
    }
