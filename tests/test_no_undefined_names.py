"""Guard against latent NameError landmines (flake8 F821) and import-time errors.

F821 (undefined name) is NOT caught by the project's CI flake8 selection, so
missing imports used only in cold POST/branch paths slip through until a user
hits them at runtime. This test fails the build if any undefined name exists in
the application packages, and verifies every route/service module imports cleanly.
"""
from __future__ import annotations

import importlib
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
_PKGS = ['routes', 'app', 'services', 'models', 'utils']


def test_no_undefined_names_f821():
    """No F821 undefined names anywhere in the application packages."""
    proc = subprocess.run(
        [sys.executable, '-m', 'flake8', '--select=F821', '--max-line-length=200', *_PKGS],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        'Undefined names found (likely missing imports — latent NameError):\n'
        + proc.stdout + proc.stderr
    )


def test_all_route_and_service_modules_import(app):
    """Every module under routes/ services/ imports without error."""
    failures = []
    for pkg_name in ('routes', 'services'):
        pkg = importlib.import_module(pkg_name)
        for mod in pkgutil.walk_packages(pkg.__path__, prefix=pkg_name + '.'):
            try:
                importlib.import_module(mod.name)
            except Exception as exc:  # noqa: BLE001
                failures.append(f'{mod.name}: {type(exc).__name__}: {str(exc)[:160]}')
    assert not failures, 'modules failed to import:\n' + '\n'.join(failures)
