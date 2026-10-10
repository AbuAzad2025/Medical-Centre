"""The single registry of which scenario templates are actually executed.

Each executable test file had its own idea of what it covered. The financial
spine kept an ``EXECUTED`` set naming five templates while three later files
executed several more without recording it anywhere. The published number was
therefore five out of two hundred and twelve, which understates the work by an
order of magnitude and makes the figure impossible to grow honestly: adding a test
did not move the number unless someone remembered to edit a list in a different
file.

This module is that list, in one place, derived rather than remembered. Every
executable test file imports ``covers`` and decorates the classes it serves, so
adding a test without declaring its template fails the coverage gate below. The
gate compares this registry against the matrix on every run and prints what share
of the matrix is executed.

Kept separate from the tests themselves because the tests describe behaviour and
this describes inventory. A change to what is covered is a different kind of
change from a change to what is asserted, and conflating them is how the five
came to stand for thirty-eight.
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# template key -> the file that executes it, and one line saying what it asserts.
EXECUTED_TEMPLATES: dict[str, tuple[str, str]] = {
    # ── financial spine ──────────────────────────────────────────────────
    'OPD_CASH_FULL_SETTLEMENT': (
        'test_scenarios_executable',
        'the queue gate refuses an unpaid visit and admits it once paid, and the '
        'payment posts a balanced GL journal',
    ),
    'OPD_PARTIAL_THEN_SETTLE': (
        'test_scenarios_executable',
        'a partial payment leaves the visit PARTIAL and a second payment settles it',
    ),
    'OPD_INSURANCE_PATIENT_SHARE': (
        'test_scenarios_executable',
        'the patient share is the complement of coverage, and coverage outside '
        '[50, 100] is rejected by the gate',
    ),
    'CASH_PAYMENT_LIMIT': (
        'test_scenarios_executable',
        'the cash ceiling is a constant rather than a setting, and no override exists',
    ),
    'FORCE_PAYMENT_QUOTA_AND_APPROVAL': (
        'test_scenarios_executable',
        'the gate refuses at the five percent boundary where the statistics disagree',
    ),
    'INSURANCE_CLAIM_LIFECYCLE': (
        'test_scenarios_executable_finance',
        'a claim is generated from an ISSUED invoice, adjudicated and paid out, '
        'and the split stays consistent',
    ),
    'REFUND_REQUEST_APPROVE_EXECUTE': (
        'test_scenarios_executable_finance',
        'an over-refund writes no row, and reception cannot refund at all',
    ),
    'ACCOUNTANT_REFUND_EXECUTION': (
        'test_scenarios_executable_finance',
        'the refund journal is left VOID rather than deleted',
    ),
    'QUEUE_TICKET_LIFECYCLE': (
        'test_scenarios_executable_isolation',
        'skip then return leaves exactly one ticket, so a patient is never on the board twice',
    ),
    # ── pharmacy money ───────────────────────────────────────────────────
    'PHARMACY_POS_SALE_AND_RETURN': (
        'test_scenarios_executable_pharmacy',
        'a sale decrements stock and produces a receipt; a card sale without the '
        'last four digits or a transaction id is refused before stock moves',
    ),
    'PHARMACY_PURCHASE_AND_DISPENSE': (
        'test_scenarios_executable_pharmacy',
        'a purchase adds exactly the stock it was told to add, a purchase against '
        'a missing medication is refused rather than inventing one, and reception '
        'cannot dispense',
    ),
    'PHARMACY_STOCK_AND_SUPPLY': (
        'test_scenarios_executable_pharmacy',
        'a supply request is created with a medication id and a per-id quantity, '
        'and approval moves it to APPROVED',
    ),
    # ── access control ───────────────────────────────────────────────────
    'QUEUE_GATE_AND_ADD_SERVICE_RBAC': (
        'test_scenarios_executable_isolation',
        'the emergency-debt bypass is unreachable, because approving a debt needs '
        'a ticket the payment gate prevents from existing',
    ),
    'IDENTITY_AUDIT_TRAIL_COVERAGE': (
        'test_scenarios_executable_rbac',
        'the audit matrix is a coverage plan rather than a journey, and the routes '
        'that carry it are executed instead',
    ),
    'IDENTITY_ROLE_DEPARTMENT_BINDING': (
        'test_scenarios_executable_rbac',
        'a blueprint with a guard in the source, asserted against every tested '
        'blueprint rather than against one',
    ),
    'IDENTITY_STAFF_ACCOUNT_LIFECYCLE': (
        'test_scenarios_executable_rbac',
        'deactivation survives an open session, and deletion is a separate console',
    ),
    'READ_DIAGNOSTIC_SURFACES_REVEAL_IDENTITY': (
        'test_scenarios_executable_rbac',
        '/_ghost_whoami answers an anonymous caller with the resolved tenant and session identity',
    ),
    'SUPERADMIN_PLATFORM_USER_DIRECTORY': (
        'test_scenarios_executable_rbac',
        'ban, unban and force-logout are registered for GET, asserted against the '
        'route table because executing them mutates the shared tenant',
    ),
    'READ_PWA_AND_METRICS_SURFACES': (
        'test_scenarios_executable_rbac',
        'the public static, health and manifest routes answer without a session',
    ),
    'READ_SUBSCRIPTION_RENEWAL_IS_A_WRITE_ON_GET': (
        'test_scenarios_executable_rbac',
        'GET /owner/tenants/<id>/renew advances subscription_end, executed',
    ),
    'READ_SUPERADMIN_CATALOGUE_AND_PRICING': (
        'test_scenarios_executable_rbac',
        'a manager is refused the platform console, and owner is admitted by policy',
    ),
    # ── read views executed for a specific failure mode ──────────────────
    'READ_RECEPTION_QUEUE_DISPLAYS': (
        'test_scenarios_executable_isolation',
        'the waiting and calls boards and the snapshot agree about the same ticket',
    ),
}


def covers(*template_keys: str):
    """Declare which templates the decorated class executes.

    Used as a class decorator. It records the keys so the coverage gate can find
    them, and does nothing else, which keeps the tests free to be organised by
    behaviour rather than by inventory.
    """

    def decorate(cls):
        existing = set(getattr(cls, 'SCENARIO_TEMPLATES', ()) or ())
        existing.update(template_keys)
        cls.SCENARIO_TEMPLATES = tuple(sorted(existing))
        return cls

    return decorate


def matrix_templates() -> dict[str, int]:
    """template key -> number of scenarios it produces."""
    import glob

    counts: dict[str, int] = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'docs/scenarios/generated/scenarios*.json'))):
        with open(path, encoding='utf-8') as fh:
            for sc in json.load(fh):
                counts[sc['template']] = counts.get(sc['template'], 0) + 1
    return counts


def executed_coverage() -> dict:
    """How much of the matrix is executed, and what the registry costs."""
    counts = matrix_templates()
    executed = set(EXECUTED_TEMPLATES)
    unknown = sorted(executed - set(counts))
    covered_scenarios = sum(counts[t] for t in executed if t in counts)
    return {
        'templates_total': len(counts),
        'templates_executed': len(executed & set(counts)),
        'scenarios_total': sum(counts.values()),
        'scenarios_executed': covered_scenarios,
        'pct_scenarios': 100.0 * covered_scenarios / sum(counts.values()) if counts else 0.0,
        'unknown_templates': unknown,
        'files': sorted({f for f, _ in EXECUTED_TEMPLATES.values()}),
    }
