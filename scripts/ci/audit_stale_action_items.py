#!/usr/bin/env python3
"""
Audit the incident-log action-items table for stale entries.

Parses docs/INCIDENT_LOG_ORPHANED_TENANT_ROWS.md section 5 (Action Items)
and flags any row where:

  1. The Status column is not a terminal value (Done / Closed / Resolved)
     AND the Target date is older than STALE_DAYS (default 30).

Exits with code 1 if stale items are found, 0 otherwise.  Designed to
run as a weekly CI step so the team stays on top of lingering action items.

Usage:
    python scripts/ci/audit_stale_action_items.py                  # default 30 days
    python scripts/ci/audit_stale_action_items.py --stale-days 60  # custom threshold
    python scripts/ci/audit_stale_action_items.py --incident-log docs/INCIDENT_LOG_ORPHANED_TENANT_ROWS.md
"""
from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from datetime import date, datetime, timedelta, timezone

# Path relative to project root
DEFAULT_LOG_PATH = "docs/INCIDENT_LOG_ORPHANED_TENANT_ROWS.md"
STALE_DAYS = 30

TERMINAL_STATUSES = frozenset({"done", "closed", "resolved", "completed", "fixed"})

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


@dataclasses.dataclass
class ActionItem:
    num: str
    incident_id: str
    issue: str
    description: str
    status: str
    target: str
    line_number: int

    @property
    def is_terminal(self) -> bool:
        """Whether the status indicates the item is fully resolved."""
        return self.status.strip().lower() in TERMINAL_STATUSES

    @property
    def parsed_target(self) -> date | None:
        """Try to extract a date from the Target column."""
        raw = self.target.strip().strip("—").strip()
        if not raw or raw == "—":
            return None

        # Try ISO format: 2026-07-15
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            pass

        # Try "YYYY-MM-DD" variants
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

        # Try "Mon DD, YYYY" or "Month DD, YYYY"
        m = re.match(
            r"(\w+)\s+(\d{1,2}),?\s*(\d{4})", raw, re.IGNORECASE
        )
        if m:
            month_name = m.group(1).lower()
            month_num = MONTH_NAMES.get(month_name)
            if month_num:
                return date(int(m.group(3)), month_num, int(m.group(2)))

        # Try "DD Mon YYYY" (e.g., "15 Jul 2026")
        m = re.match(
            r"(\d{1,2})\s+(\w+)\s+(\d{4})", raw, re.IGNORECASE
        )
        if m:
            month_name = m.group(2).lower()
            month_num = MONTH_NAMES.get(month_name)
            if month_num:
                return date(int(m.group(3)), month_num, int(m.group(1)))

        return None

    def is_stale(self, stale_days: int = STALE_DAYS) -> bool:
        """True if the item is not terminal and its target date is overdue."""
        if self.is_terminal:
            return False
        target = self.parsed_target
        if target is None:
            # No target set — flag as stale if status isn't clearly done
            status = self.status.strip().lower()
            if status in ("", "—", "-", "tbd", "todo", "open", "pending"):
                return True
            return False
        return (date.today() - target).days > stale_days


def parse_action_items(markdown: str) -> list[ActionItem]:
    """Extract action items from the Action Items table in the incident log."""
    items: list[ActionItem] = []
    lines = markdown.splitlines()

    # Find the Action Items table header
    in_section = False
    in_table = False
    headers = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Detect section 5 header
        if re.match(r"^##\s+5\.", stripped):
            in_section = True
            continue

        if not in_section:
            continue

        # Stop at the next section header
        if re.match(r"^##\s+\d+\.", stripped) and "Action Items" not in stripped:
            break

        # Detect table header row (| # | Incident ID | ...)
        if stripped.startswith("|") and "Incident ID" in stripped:
            in_table = True
            headers = [h.strip() for h in stripped.strip("|").split("|")]
            continue

        # Skip separator row (| --- | --- | ...)
        if in_table and stripped.startswith("|") and "---" in stripped:
            continue

        # Parse data rows
        if in_table and stripped.startswith("|") and stripped.count("|") >= 4:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 6:
                # Skip placeholder rows where all fields are em-dashes
                if all(c in ("", "—", "-") for c in cells):
                    continue
                items.append(ActionItem(
                    num=cells[0],
                    incident_id=cells[1],
                    issue=cells[2],
                    description=cells[3],
                    status=cells[4],
                    target=cells[5],
                    line_number=i,
                ))

    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--incident-log", default=DEFAULT_LOG_PATH,
        help=f"Path to the incident log markdown file (default: {DEFAULT_LOG_PATH})",
    )
    parser.add_argument(
        "--stale-days", type=int, default=STALE_DAYS,
        help=f"Days after which an unresolved item is considered stale (default: {STALE_DAYS})",
    )
    args = parser.parse_args()

    try:
        with open(args.incident_log, encoding="utf-8") as f:
            markdown = f.read()
    except FileNotFoundError:
        print(f"❌ Incident log not found: {args.incident_log}")
        return 1

    items = parse_action_items(markdown)
    if not items:
        print(f"ℹ️  No action items found in {args.incident_log}")
        return 0

    print(f"📋 Found {len(items)} action item(s)\n")

    stale: list[ActionItem] = []
    resolved: list[ActionItem] = []

    for item in items:
        if item.is_terminal:
            resolved.append(item)
            continue
        if item.is_stale(args.stale_days):
            stale.append(item)
            continue
        target_str = str(item.parsed_target) if item.parsed_target else "no target"
        print(f"  ✅ #{item.num} ({item.incident_id}): {item.description[:80]} — "
              f"OK (target: {target_str})")

    if resolved:
        print(f"\n  ✅ {len(resolved)} already resolved: ", end="")
        print(", ".join(f"#{r.num}" for r in resolved))

    if not stale:
        print("\n✅ No stale action items found.")
        return 0

    print(f"\n❌ {len(stale)} STALE action item(s) older than {args.stale_days} days:\n")
    for item in stale:
        print(f"  ┌─ Line {item.line_number}")
        print(f"  ├─ #:          {item.num}")
        print(f"  ├─ Incident:   {item.incident_id}")
        print(f"  ├─ Issue:      {item.issue}")
        print(f"  ├─ Description: {item.description}")
        print(f"  ├─ Status:     {item.status}")
        print(f"  ├─ Target:     {item.target}")
        target = item.parsed_target
        if target:
            days_overdue = (date.today() - target).days
            print(f"  └─ Overdue by: {days_overdue} day(s)")
        else:
            print(f"  └─ No target date set")
        print()

    print(f"ℹ️  Total: {len(items)} items — {len(resolved)} resolved, "
          f"{len(stale)} stale.\n")
    print(f"💡 Update statuses or target dates in {args.incident_log} "
          f"to clear stale items.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
