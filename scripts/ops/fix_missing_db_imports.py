"""Fix missing `db` imports in files touched by the SQLAlchemy 2.0 migration."""
import re
import sys


def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    content = "".join(lines)
    # If 'db' is already imported in any form, skip
    if re.search(r"\bimport\s+db\b", content) or re.search(
        r"\bfrom\s+.*\bimport\s+.*\bdb\b", content
    ):
        return

    # Check for SQLAlchemy 2.0 patterns introduced by migration
    if (
        "db.session.get(" in content
        or "db.session.execute(" in content
        or "db.session.query(" in content
    ):
        # Find insertion point: after last import line
        import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                import_idx = i + 1

        # Determine which import to use based on path
        if "routes" in filepath:
            import_line = "from app.extensions import db\n"
        else:
            import_line = "from app_factory import db\n"

        lines.insert(import_idx, import_line)
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"Fixed {filepath}")


if __name__ == "__main__":
    files = sys.argv[1:]
    for f in files:
        fix_file(f)
