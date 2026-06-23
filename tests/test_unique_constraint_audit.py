"""Tests for P0C-002: unique constraint audit file is valid."""

import json
from pathlib import Path


class TestUniqueConstraintAudit:
    """Unique constraint audit must exist and be valid JSON."""

    def test_audit_file_exists(self):
        audit_path = Path(__file__).parent.parent / "unique_constraint_audit.json"
        assert audit_path.exists(), "unique_constraint_audit.json is missing"

    def test_audit_is_valid_json(self):
        audit_path = Path(__file__).parent.parent / "unique_constraint_audit.json"
        data = json.loads(audit_path.read_text(encoding="utf-8"))
        assert "constraints" in data
        assert "summary" in data
        assert "duplicate_audit_queries" in data
        for constraint in data["constraints"]:
            assert constraint["table"]
            assert constraint["columns"]
            assert constraint["classification"] in {
                "global", "tenant-scoped", "branch/fiscal", "soft-delete", "unknown", "decision"
            }
