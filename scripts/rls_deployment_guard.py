#!/usr/bin/env python3
"""
Ticket 11: RLS Runtime Verification and Deployment Guard

This script verifies Row-Level Security (RLS) is properly configured before deployment.
Run as part of CI/CD pipeline or pre-deployment check.

Checks:
1. Application database role exists and does NOT have BYPASSRLS
2. All tenant-scoped tables have RLS enabled (relrowsecurity=true)
3. All tenant-scoped tables have RLS enforced (relforcerowsecurity=true)
4. row_security_active() is true for current connection
5. RLS policies exist for all tenant-scoped tables
6. No tenant-scoped table is missing a policy

Exit codes:
0 = All checks passed (safe to deploy)
1 = One or more checks failed
"""
import sys
import os
import json
import logging
from typing import List, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from app.extensions import db

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Tenant-scoped tables (must have RLS policies)
_TENANT_SCOPED_TABLES = [
    'visits', 'patients', 'users', 'departments', 'service_master',
    'invoice_services', 'invoices', 'payments', 'receipts',
    'medical_records', 'lab_requests', 'lab_results',
    'radiology_requests', 'radiology_results', 'prescriptions',
    'medications', 'queue_management', 'audit_trails',
    'notifications', 'appointments', 'medical_files',
    'medical_reports', 'medical_report_templates', 'dynamic_forms',
    'form_submissions', 'form_field_definitions', 'branding_settings',
    'custom_pages', 'menus', 'menu_items', 'navigation_items',
    'website_sections', 'website_content', 'landing_pages',
    'page_sections', 'doctors', 'nurses', 'receptionists',
    'medical_staff', 'staff_schedules', 'shifts', 'shift_assignments',
    'medical_equipment', 'equipment_maintenance', 'inventory_items',
    'inventory_transactions', 'suppliers', 'purchase_orders',
    'purchase_order_items', 'pricing_catalogs', 'pricing_catalog_items',
    'doctor_pricings', 'doctor_pricing_items', 'insurance_companies',
    'insurance_plans', 'insurance_coverages', 'insurance_claims',
    'claim_items', 'billing_codes', 'billing_code_categories',
    'financial_transactions', 'journal_entries', 'ledger_accounts',
    'account_balances', 'budgets', 'budget_items', 'financial_reports',
    'report_templates', 'scheduled_reports', 'report_executions',
    'dashboard_widgets', 'dashboard_layouts', 'user_preferences',
    'system_settings', 'email_templates', 'sms_templates',
    'notification_templates', 'workflow_rules', 'workflow_actions',
    'workflow_executions', 'task_definitions', 'task_instances',
    'task_assignments', 'escalation_rules', 'escalation_actions',
    'sla_definitions', 'sla_violations', 'compliance_checks',
    'compliance_reports', 'risk_assessments', 'risk_mitigations',
    'incidents', 'incident_responses', 'change_requests',
    'change_approvals', 'deployment_logs', 'system_health_checks',
    'performance_metrics', 'error_logs', 'slow_query_logs',
    'security_events', 'access_logs', 'login_attempts',
    'session_logs', 'api_usage_logs', 'webhook_logs',
    'integration_logs', 'sync_logs', 'backup_logs',
    'restore_logs', 'migration_logs', 'seed_logs',
    'bootstrap_logs', 'provisioning_logs', 'tenant_audit_logs',
    'platform_audit_logs', 'resource_usage', 'subscription_lines',
    'subscription_line_items', 'billing_cycles', 'invoices',
    'invoice_items', 'payments', 'refunds', 'credits',
    'debits', 'adjustments', 'write_offs', 'payment_plans',
    'payment_plan_schedules', 'payment_plan_payments',
    'collections', 'collection_agencies', 'collection_attempts',
    'dispute_logs', 'chargeback_logs', 'fraud_checks',
    'fraud_scores', 'fraud_rules', 'fraud_exceptions',
]


def _get_app_connection():
    """Get a raw psycopg2 connection from the Flask-SQLAlchemy engine."""
    return db.engine.raw_connection()


def check_role_bypass_rls(conn) -> Tuple[bool, str]:
    """Check that application role does NOT have BYPASSRLS."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT rolname, rolbypassrls
            FROM pg_roles
            WHERE rolname = current_user
        """)
        row = cur.fetchone()
        if not row:
            return False, "Could not determine current database role"
        role_name, bypass_rls = row
        if bypass_rls:
            return False, f"CRITICAL: Role '{role_name}' has BYPASSRLS privilege"
        return True, f"Role '{role_name}' does NOT have BYPASSRLS (good)"


def check_row_security_active(conn) -> Tuple[bool, str]:
    """Check row_security setting for current connection."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('row_security', true)")
        setting = cur.fetchone()[0]
        if setting and setting.lower() == 'on':
            return True, "row_security is ON for current connection (good)"
        return False, "row_security is OFF or not set for current connection"


def check_tables_rls_enabled(conn) -> List[Tuple[bool, str]]:
    """Check that all tenant-scoped tables have RLS enabled and enforced."""
    results = []
    with conn.cursor() as cur:
        # Get all tables in the current schema with RLS flags
        cur.execute("""
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND c.relname = ANY(%s)
            ORDER BY c.relname
        """, (_TENANT_SCOPED_TABLES,))
        rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    for table in _TENANT_SCOPED_TABLES:
        if table not in rows:
            results.append((False, f"Table '{table}' not found in database"))
            continue
        row_sec, force_sec = rows[table]
        if not row_sec:
            results.append((False, f"Table '{table}' has RLS DISABLED (relrowsecurity=false)"))
        elif not force_sec:
            results.append((False, f"Table '{table}' has RLS enabled but NOT ENFORCED (relforcerowsecurity=false)"))
        else:
            results.append((True, f"Table '{table}' has RLS enabled and enforced (good)"))
    return results


def check_rls_policies_exist(conn) -> List[Tuple[bool, str]]:
    """Check that all tenant-scoped tables have at least one RLS policy."""
    results = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pg_tables.tablename, COUNT(pg_policies.policyname) as policy_count
            FROM pg_tables
            LEFT JOIN pg_policies ON pg_tables.tablename = pg_policies.tablename
                AND pg_tables.schemaname = pg_policies.schemaname
            WHERE pg_tables.schemaname = 'public'
              AND pg_tables.tablename = ANY(%s)
            GROUP BY pg_tables.tablename
            ORDER BY pg_tables.tablename
        """, (_TENANT_SCOPED_TABLES,))
        rows = {r[0]: r[1] for r in cur.fetchall()}

    for table in _TENANT_SCOPED_TABLES:
        count = rows.get(table, 0)
        if count == 0:
            results.append((False, f"Table '{table}' has NO RLS policies"))
        else:
            results.append((True, f"Table '{table}' has {count} RLS policy/policies (good)"))
    return results


def main() -> int:
    app = create_app()
    with app.app_context():
        conn = _get_app_connection()
        try:
            all_passed = True

            # Check 1: Role BYPASSRLS
            ok, msg = check_role_bypass_rls(conn)
            all_passed &= ok
            print(f"{'✅' if ok else '❌'} {msg}")

            # Check 2: row_security_active()
            ok, msg = check_row_security_active(conn)
            all_passed &= ok
            print(f"{'✅' if ok else '❌'} {msg}")

            # Check 3: Tables RLS enabled
            print("\n--- Table RLS Status ---")
            for ok, msg in check_tables_rls_enabled(conn):
                all_passed &= ok
                print(f"{'✅' if ok else '❌'} {msg}")

            # Check 4: RLS policies exist
            print("\n--- Table Policy Count ---")
            for ok, msg in check_rls_policies_exist(conn):
                all_passed &= ok
                print(f"{'✅' if ok else '❌'} {msg}")

            print()
            if all_passed:
                print("✅ All RLS checks passed. Safe to deploy.")
                return 0
            else:
                print("❌ One or more RLS checks failed. DO NOT DEPLOY.")
                return 1
        finally:
            conn.close()


if __name__ == '__main__':
    sys.exit(main())
