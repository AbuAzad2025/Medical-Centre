"""Tests for terminology validation and loading.

These assert the *refusals* as much as the acceptances. The whole point of the
module is that it will not invent a code, so the tests that matter most are the
ones proving it stays empty and says so.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from utils.terminology import (
    configured_sources,
    load_configured_terminology,
    loinc_check_digit_valid,
    validate_file,
    validate_row,
)


class TestLoincCheckDigit:
    def test_rejects_obviously_wrong_codes(self):
        assert loinc_check_digit_valid('not-a-code') is False
        assert loinc_check_digit_valid('1234') is False  # no check digit
        assert loinc_check_digit_valid('1234-9') is False  # bad check digit
        assert loinc_check_digit_valid('12-1') is False  # wrong body length

    def test_accepts_a_known_good_code(self):
        # 718-7 is haemoglobin, a real and stable LOINC code.
        assert loinc_check_digit_valid('718-7') is True

    def test_check_digit_is_actually_verified(self):
        """Flipping the check digit must fail, not silently pass."""
        assert loinc_check_digit_valid('718-7') is True
        for bad in ('718-0', '718-1', '718-8', '718-9'):
            assert loinc_check_digit_valid(bad) is False


class TestValidateRow:
    def test_cpt_requires_five_digits(self):
        assert validate_row('CPT', '99213', 'Office visit') is None
        assert validate_row('CPT', '9921', 'too short') is not None
        assert validate_row('CPT', '992130', 'too long') is not None
        assert validate_row('CPT', '9921A', 'has a letter') is not None

    def test_loinc_requires_a_valid_code_and_description(self):
        assert validate_row('LOINC', '718-7', 'Haemoglobin') is None
        assert validate_row('LOINC', '718-0', 'Haemoglobin') is not None
        assert validate_row('LOINC', '718-7', '') is not None
        assert validate_row('LOINC', '718-7', '   ') is not None

    def test_unknown_system_is_rejected(self):
        assert validate_row('SNOMED', '12345', 'x') is not None


class TestRefusesToFabricate:
    def test_nothing_configured_means_not_loaded(self, monkeypatch):
        """The honest empty state: loaded=False with a reason, never a code."""
        monkeypatch.delenv('TERMINOLOGY_PATH', raising=False)
        assert configured_sources() == []
        result = load_configured_terminology()
        assert result['loaded'] is False
        assert 'not set' in result['reason']
        assert 'none were invented' in result['reason']

    def test_no_rows_are_written_when_no_source_exists(self, app, rollback_db):
        """The property is that it writes nothing, not that the table is empty.

        Asserting an empty table would test the environment instead of the code,
        and would fail for reasons unrelated to the loader.
        """
        from sqlalchemy import func, select

        from app.extensions import db
        from models.icd_coding import CPTCode

        # No inner app context: db.session is scoped to one, and opening a second
        # would hand us a session that the rollback fixture does not cover.
        count = db.session.execute(select(func.count()).select_from(CPTCode)).scalar()
        result = load_configured_terminology()
        after = db.session.execute(select(func.count()).select_from(CPTCode)).scalar()
        assert result['loaded'] is False
        assert after == count, 'the loader wrote rows with no source configured'


class TestValidateFile:
    def _write(self, tmp_path: Path, name: str, rows: list[dict[str, str]]) -> Path:
        path = tmp_path / name
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_good_file_reports_every_row_accepted(self, tmp_path):
        path = self._write(
            tmp_path,
            'cpt_release.csv',
            [
                {'code': '99213', 'description': 'Office visit, established'},
                {'code': '99214', 'description': 'Office visit, new'},
            ],
        )
        report = validate_file(path)
        assert report.rows_loaded == 2
        assert report.rows_rejected == 0
        assert report.checksum

    def test_bad_rows_are_rejected_and_named(self, tmp_path):
        path = self._write(
            tmp_path,
            'cpt_release.csv',
            [
                {'code': '99213', 'description': 'Office visit'},
                {'code': 'BAD', 'description': 'Malformed code'},
                {'code': '99215', 'description': ''},
            ],
        )
        report = validate_file(path)
        assert report.rows_loaded == 1
        assert report.rows_rejected == 2
        assert any('5 digits' in r for r in report.rejections)
        assert any('empty description' in r for r in report.rejections)

    def test_system_cannot_be_guessed_is_reported(self, tmp_path):
        """An ambiguous file is skipped, not guessed at."""
        path = self._write(tmp_path, 'mystery.csv', [{'code': '12345', 'description': 'Unknown'}])
        report = validate_file(path)
        assert report.skipped_reason is not None
        assert 'system' in report.skipped_reason
        assert report.rows_loaded == 0

    def test_charset_is_survived(self, tmp_path):
        """BOM-prefixed official CSVs must not blow up."""
        path = tmp_path / 'cpt_bom.csv'
        # \ufeff is the real BOM; a literal one is invisible in review and
        # fragile through editors that re-encode the file.
        path.write_text('\ufeffcode,description\n99213,Office visit\n', encoding='utf-8')
        report = validate_file(path)
        assert report.rows_loaded == 1


class TestIdempotentLoad:
    def test_reimport_updates_rather_than_duplicates(self, app, rollback_db, tmp_path, monkeypatch):
        from sqlalchemy import func, select

        from app.extensions import db
        from models.icd_coding import CPTCode
        from utils.terminology import load_configured_terminology

        path = tmp_path / 'cpt_release.csv'
        path.write_text(
            'code,description,description_ar\n99213,Office visit established,زيارة مكتبية\n',
            encoding='utf-8',
        )
        monkeypatch.setenv('TERMINOLOGY_PATH', str(path))

        from utils.terminology import persist_cpt_codes

        # No inner app context: db.session is scoped to one, and opening a second
        # would hand us a session the rollback fixture does not cover.
        # Start from a known state so the assertion is about the loader's
        # behaviour rather than whatever a previous run left behind.
        db.session.query(CPTCode).filter(CPTCode.code == '99213').delete(synchronize_session=False)
        db.session.flush()

        first = persist_cpt_codes(path)
        assert first['inserted'] == 1
        assert first['updated'] == 0

        second = persist_cpt_codes(path)
        assert second['inserted'] == 0
        assert second['updated'] == 1, 're-import must update, not duplicate'

        total = db.session.execute(select(func.count()).select_from(CPTCode)).scalar()
        assert total == 1, f'expected 1 row after two imports, found {total}'
        assert load_configured_terminology is not None


@pytest.mark.parametrize('env_value', ['', '   '])
def test_blank_path_is_treated_as_unset(monkeypatch, env_value):
    monkeypatch.setenv('TERMINOLOGY_PATH', env_value)
    assert configured_sources() == []
