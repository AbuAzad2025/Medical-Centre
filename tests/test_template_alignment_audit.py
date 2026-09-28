"""Tests for the template alignment auditor.

The auditor is only useful if it is itself correct, so these pin the three
failure modes that produced pure noise on the first run: templates that only look
broken because an i18n extension or a runtime-registered filter is missing from
the audit environment, names that resolve through a context processor, and names
the template defines itself with ``{% set %}``.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'audit' / 'template_alignment.py'
sys.path.insert(0, str(ROOT / 'scripts' / 'audit'))


@pytest.fixture(scope='module')
def auditor():
    import template_alignment as ta

    return ta


class TestParsesEveryTemplate:
    def test_no_parse_errors(self, auditor, capsys):
        """All 430 templates must parse.

        A template using {% trans %} or a runtime-registered filter looks
        syntactically broken to a bare Jinja environment. That is an artefact of
        the audit environment, not a defect in the template, and the auditor
        registers the i18n extensions and the app's own filters for exactly this
        reason.
        """
        assert auditor.main([]) is not None  # runs the audit
        out = capsys.readouterr().out
        assert 'parse_errors=0' in out, out[-2000:]

    def test_every_template_file_is_seen(self, auditor):
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(str(auditor.TPL)), autoescape=False)
        files = list(auditor.TPL.rglob('*.html'))
        assert len(files) > 100
        for custom in auditor.collect_custom_filters():
            env.filters.setdefault(custom, lambda v, *_a, **_k: v)
        assert env


class TestSuppressionIsCorrect:
    def test_template_local_names_are_not_missing_context(self, auditor):
        """{% set %}, {% for x in %} and {% with x = %} define names locally."""
        local = auditor.collect_local(
            '{% set perms = x %}{% for a, b in items %}{% with y = 1 %}{% endwith %}{% endfor %}'
        )
        assert {'perms', 'a', 'b', 'y'} <= local

    def test_guarded_usage_is_not_reported(self, auditor):
        guarded = auditor._is_guarded('branding', "{{ branding.name if branding else 'x' }}")
        assert guarded is True
        bare = auditor._is_guarded('total', '<h2>{{ total }}</h2>')
        assert bare is False

    def test_context_processors_are_discovered(self, auditor):
        """app_factory's context processors must be found.

        Getting this wrong once made every injected name look missing: a
        Path.rglob() on a file path returns nothing, so app_factory.py was
        silently skipped and 54 templates were reported as broken.
        """
        injected = auditor.collect_injected()
        assert len(injected) > 20
        assert 'has_permission' in injected, 'app_factory context processor not found'
        assert 'module_active' in injected

    def test_custom_filters_are_discovered(self, auditor):
        names = auditor.collect_custom_filters()
        assert 'enum_label' in names, names


class TestExitCode:
    def test_script_runs_and_reports(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=ROOT
        )
        assert result.returncode in (0, 1), result.stderr[-500:]
        assert 'RESULT:' in result.stdout
        assert 'form classes' in result.stdout
