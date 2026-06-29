#!/usr/bin/env python3
"""Optional debt lint — full F821 scan (not enforced in CI)."""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [
        sys.executable, "-m", "flake8",
        "app", "routes", "services", "models", "utils",
        "--select=F821", "--count", "--statistics",
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
