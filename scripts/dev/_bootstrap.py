"""Shared path bootstrap for scripts/dev — not imported by production code."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def bootstrap_dev_script() -> Path:
    """Put repo root on sys.path and cwd (local dev scripts only)."""
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(REPO_ROOT)
    return REPO_ROOT
