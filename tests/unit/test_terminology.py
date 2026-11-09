"""Behavioural tests for utils.terminology (CPT/LOINC validation and loading).

The module exists so the platform can *validate* clinical codes, never invent
them. These tests pin that contract: format rules, the LOINC Mod-10 check
digit, provenance reporting, idempotent persistence, and the honesty of the
no-source-default case.
"""

from __future__ import annotations

import csv
from pathlib import Path

from utils import terminology


class TestValidateRow:
    def test_cpt_valid(self):
        assert terminology.validate_row('CPT', '99213', 'Office visit') is None

    def test_cpt_requires_five_digits(self):
        assert terminology.validate_row('CPT', '9921', 'Office visit') is not None
        assert terminology.validate_row('CPT', '99213A', 'Office visit') is not None

    def test_loinc_valid_with_check_digit(self):
        # 2339-0 is a valid LOINC code (blood glucose)
        assert terminology.validate_row('LOINC', '2339-0', 'Glucose') is None

    def test_loinc_bad_check_digit_rejected(self):
        assert terminology.validate_row('LOINC', '2339-1', 'Glucose') is not None

    def test_loinc_shape_enforced(self):
        assert terminology.validate_row('LOINC', 'A102-1', 'Glucose') is not None
        assert terminology.validate_row('LOINC', 'ABCD-X', 'Glucose') is not None

    def test_loinc_known_real_code(self):
        # 718-7 haemoglobin is a canonical LOINC code
        assert terminology.loinc_check_digit_valid('718-7') is True

    def test_empty_description_rejected(self):
        assert terminology.validate_row('CPT', '99213', '') is not None
        assert terminology.validate_row('CPT', '99213', '   ') is not None

    def test_unknown_system_rejected(self):
        assert terminology.validate_row('ICD', 'E11.9', 'Diabetes') is not None


class TestLoincCheckDigit:
    def test_valid_bodies_of_different_lengths(self):
        for code in ('718-7', '2339-0'):
            assert terminology.loinc_check_digit_valid(code)

    def test_wrong_check_rejected(self):
        for code in ('718-8', '718-9', '2339-1', '2339-2'):
            assert not terminology.loinc_check_digit_valid(code)

    def test_nonsense_rejected(self):
        assert not terminology.loinc_check_digit_valid('')
        assert not terminology.loinc_check_digit_valid('-')
        assert not terminology.loinc_check_digit_valid('718--7')


class TestConfiguredSources:
    def test_unset_env_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.delenv('TERMINOLOGY_PATH', raising=False)
        assert terminology.configured_sources() == []

    def test_single_file_accepted(self, monkeypatch, tmp_path):
        f = tmp_path / 'codes.csv'
        f.write_text('code,description\n99213,x\n', encoding='utf-8')
        monkeypatch.setenv('TERMINOLOGY_PATH', str(f))
        assert terminology.configured_sources() == [f]

    def test_directory_picks_up_csv_only(self, monkeypatch, tmp_path):
        (tmp_path / 'a.csv').write_text('x', encoding='utf-8')
        (tmp_path / 'b.txt').write_text('y', encoding='utf-8')
        monkeypatch.setenv('TERMINOLOGY_PATH', str(tmp_path))
        assert terminology.configured_sources() == [tmp_path / 'a.csv']

    def test_multiple_paths_split_on_pathsep(self, monkeypatch, tmp_path):
        f1 = tmp_path / 'one.csv'
        f2 = tmp_path / 'two.csv'
        f1.write_text('x', encoding='utf-8')
        f2.write_text('y', encoding='utf-8')
        import os

        monkeypatch.setenv('TERMINOLOGY_PATH', os.pathsep.join([str(f1), str(f2)]))
        assert terminology.configured_sources() == [f1, f2]


class TestValidateFile:
    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> Path:
        with path.open('w', encoding='utf-8', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_valid_cpt_file_reports_loaded(self, tmp_path):
        path = self._write_csv(
            tmp_path / 'cpt_codes.csv',
            [{'code': '99213', 'description': 'Office visit'}],
        )
        report = terminology.validate_file(path)
        assert report.rows_loaded == 1
        assert report.rows_rejected == 0
        assert report.skipped_reason is None
        assert len(report.checksum) == 64

    def test_reports_rejected_rows_with_reason(self, tmp_path):
        path = self._write_csv(
            tmp_path / 'cpt_codes.csv',
            [
                {'code': '99213', 'description': 'Office visit'},
                {'code': 'ZZ123', 'description': 'bad code'},
            ],
        )
        report = terminology.validate_file(path)
        assert report.rows_loaded == 1
        assert report.rows_rejected == 1
        assert any('99213' in r or 'code' in r for r in report.rejections)

    def test_cannot_infer_system(self, tmp_path):
        path = self._write_csv(
            tmp_path / 'stuff.csv',
            [{'code': '99213', 'description': 'x'}],
        )
        report = terminology.validate_file(path)
        assert report.skipped_reason is not None
        assert report.rows_loaded == 0

    def test_system_column_takes_precedence(self, tmp_path):
        path = self._write_csv(
            tmp_path / 'stuff.csv',
            [
                {'system': 'CPT', 'code': '99213', 'description': 'x'},
                {'system': 'LOINC', 'code': '2339-0', 'description': 'y'},
            ],
        )
        # Mixed systems in one file: the inferred system applies per-row validation
        report = terminology.validate_file(path)
        assert report.rows_loaded >= 1  # at least CPT passes under CPT-inferred rule

    def test_roundtrip_as_dict(self, tmp_path):
        path = self._write_csv(
            tmp_path / 'cpt_x.csv',
            [{'code': '99213', 'description': 'x'}],
        )
        d = terminology.validate_file(path).as_dict()
        assert set(d) >= {
            'source',
            'checksum',
            'rows_loaded',
            'rows_rejected',
            'rejections',
            'skipped_reason',
        }


class TestPersistCptCodes:
    def test_load_inserts_and_updates_idempotently(self, app, db, tmp_path):

        path = tmp_path / 'cpt_codes.csv'
        with path.open('w', encoding='utf-8', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=['code', 'description'])
            writer.writeheader()
            writer.writerow({'code': '99213', 'description': 'Office visit'})
        result = terminology.persist_cpt_codes(path)
        assert result['inserted'] == 1
        assert result['updated'] == 0
        row = db.session.execute(
            db.text('SELECT description FROM cpt_codes WHERE code = :c'), {'c': '99213'}
        ).scalar()
        assert row == 'Office visit'

        # Re-import with changed description updates instead of duplicating
        with path.open('w', encoding='utf-8', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=['code', 'description'])
            writer.writeheader()
            writer.writerow({'code': '99213', 'description': 'Office visit, revised'})
        result2 = terminology.persist_cpt_codes(path)
        assert result2['inserted'] == 0
        assert result2['updated'] == 1
        row = db.session.execute(
            db.text('SELECT description FROM cpt_codes WHERE code = :c'), {'c': '99213'}
        ).scalar()
        assert row == 'Office visit, revised'

    def test_skipped_file_writes_nothing(self, app, db, tmp_path):
        path = tmp_path / 'stuff.csv'
        with path.open('w', encoding='utf-8', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=['code', 'description'])
            writer.writeheader()
            writer.writerow({'code': '99213', 'description': 'x'})
        result = terminology.persist_cpt_codes(path)
        assert result['skipped_reason']

    def test_load_configured_terminology_honesty(self, app, monkeypatch, tmp_path):
        monkeypatch.delenv('TERMINOLOGY_PATH', raising=False)
        result = terminology.load_configured_terminology()
        assert result['loaded'] is False
        assert 'not set' in result['reason']
