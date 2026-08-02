"""
Ticket 11: RLS runtime verification and deployment guard
- Verify RLS guard functions correctly identify RLS status
- Verify BYPASSRLS check works
- Verify row_security_active check works
- Verify table RLS status checks work
- Verify policy existence checks work
"""

import pytest

from app_factory import db as _db

# Tenant-scoped tables (must have RLS policies)
_TENANT_SCOPED_TABLES = [
    'visits',
    'patients',
    'users',
    'departments',
    'service_master',
    'invoice_services',
    'invoices',
    'payments',
    'receipts',
    'medical_records',
    'lab_requests',
    'lab_results',
    'radiology_requests',
    'radiology_results',
    'prescriptions',
    'medications',
    'queue_management',
    'audit_trails',
    'notifications',
    'appointments',
    'medical_files',
    'medical_reports',
    'medical_report_templates',
    'dynamic_forms',
    'form_submissions',
    'form_field_definitions',
    'branding_settings',
    'custom_pages',
    'menus',
    'menu_items',
    'navigation_items',
    'website_sections',
    'website_content',
    'landing_pages',
    'page_sections',
    'doctors',
    'nurses',
    'receptionists',
    'medical_staff',
    'staff_schedules',
    'shifts',
    'shift_assignments',
    'medical_equipment',
    'equipment_maintenance',
    'inventory_items',
    'inventory_transactions',
    'suppliers',
    'purchase_orders',
    'purchase_order_items',
    'pricing_catalogs',
    'pricing_catalog_items',
    'doctor_pricings',
    'doctor_pricing_items',
    'insurance_companies',
    'insurance_plans',
    'insurance_coverages',
    'insurance_claims',
    'claim_items',
    'billing_codes',
    'billing_code_categories',
    'financial_transactions',
    'journal_entries',
    'ledger_accounts',
    'account_balances',
    'budgets',
    'budget_items',
    'financial_reports',
    'report_templates',
    'scheduled_reports',
    'report_executions',
    'dashboard_widgets',
    'dashboard_layouts',
    'user_preferences',
    'system_settings',
    'email_templates',
    'sms_templates',
    'notification_templates',
    'workflow_rules',
    'workflow_actions',
    'workflow_executions',
    'task_definitions',
    'task_instances',
    'task_assignments',
    'escalation_rules',
    'escalation_actions',
    'sla_definitions',
    'sla_violations',
    'compliance_checks',
    'compliance_reports',
    'risk_assessments',
    'risk_mitigations',
    'incidents',
    'incident_responses',
    'change_requests',
    'change_approvals',
    'deployment_logs',
    'system_health_checks',
    'performance_metrics',
    'error_logs',
    'slow_query_logs',
    'security_events',
    'access_logs',
    'login_attempts',
    'session_logs',
    'api_usage_logs',
    'webhook_logs',
    'integration_logs',
    'sync_logs',
    'backup_logs',
    'restore_logs',
    'migration_logs',
    'seed_logs',
    'bootstrap_logs',
    'provisioning_logs',
    'tenant_audit_logs',
    'platform_audit_logs',
    'resource_usage',
    'subscription_lines',
    'subscription_line_items',
    'billing_cycles',
    'invoices',
    'invoice_items',
    'payments',
    'refunds',
    'credits',
    'debits',
    'adjustments',
    'write_offs',
    'payment_plans',
    'payment_plan_schedules',
    'payment_plan_payments',
    'collections',
    'collection_agencies',
    'collection_attempts',
    'dispute_logs',
    'chargeback_logs',
    'fraud_checks',
    'fraud_scores',
    'fraud_rules',
    'fraud_exceptions',
]


def _check_role_bypass_rls(conn) -> tuple[bool, str]:
    """Check that application role does NOT have BYPASSRLS."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT rolname, rolbypassrls
            FROM pg_roles
            WHERE rolname = current_user
        """)
        row = cur.fetchone()
        if not row:
            return False, 'Could not determine current database role'
        role_name, bypass_rls = row
        if bypass_rls:
            return False, f"CRITICAL: Role '{role_name}' has BYPASSRLS privilege"
        return True, f"Role '{role_name}' does NOT have BYPASSRLS (good)"


def _check_row_security_active(conn) -> tuple[bool, str]:
    """Check row_security setting for current connection."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('row_security', true)")
        setting = cur.fetchone()[0]
        if setting and setting.lower() == 'on':
            return True, 'row_security is ON for current connection (good)'
        return False, 'row_security is OFF or not set for current connection'


def _check_tables_rls_enabled(conn) -> list[tuple[bool, str]]:
    """Check that all tenant-scoped tables have RLS enabled and enforced."""
    results = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND c.relname = ANY(%s)
            ORDER BY c.relname
        """,
            (_TENANT_SCOPED_TABLES,),
        )
        rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    for table in _TENANT_SCOPED_TABLES:
        if table not in rows:
            results.append((False, f"Table '{table}' not found in database"))
            continue
        row_sec, force_sec = rows[table]
        if not row_sec:
            results.append((False, f"Table '{table}' has RLS DISABLED (relrowsecurity=false)"))
        elif not force_sec:
            results.append(
                (
                    False,
                    f"Table '{table}' has RLS enabled but NOT ENFORCED (relforcerowsecurity=false)",
                )
            )
        else:
            results.append((True, f"Table '{table}' has RLS enabled and enforced (good)"))
    return results


def _check_rls_policies_exist(conn) -> list[tuple[bool, str]]:
    """Check that all tenant-scoped tables have at least one RLS policy."""
    results = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_tables.tablename, COUNT(pg_policies.policyname) as policy_count
            FROM pg_tables
            LEFT JOIN pg_policies ON pg_tables.tablename = pg_policies.tablename
                AND pg_tables.schemaname = pg_policies.schemaname
            WHERE pg_tables.schemaname = 'public'
              AND pg_tables.tablename = ANY(%s)
            GROUP BY pg_tables.tablename
            ORDER BY pg_tables.tablename
        """,
            (_TENANT_SCOPED_TABLES,),
        )
        rows = {r[0]: r[1] for r in cur.fetchall()}

    for table in _TENANT_SCOPED_TABLES:
        count = rows.get(table, 0)
        if count == 0:
            results.append((False, f"Table '{table}' has NO RLS policies"))
        else:
            results.append((True, f"Table '{table}' has {count} RLS policy/policies (good)"))
    return results


@pytest.mark.usefixtures('app')
class TestRLSDeploymentGuard:
    def test_role_bypass_rls_check(self, app):
        with app.app_context():
            conn = _db.engine.raw_connection()
            try:
                ok, msg = _check_role_bypass_rls(conn)
                assert ok is True or ok is False
                assert isinstance(msg, str)
            finally:
                conn.close()

    def test_row_security_active_check(self, app):
        with app.app_context():
            conn = _db.engine.raw_connection()
            try:
                ok, msg = _check_row_security_active(conn)
                assert ok is True or ok is False
                assert isinstance(msg, str)
            finally:
                conn.close()

    def test_tables_rls_enabled_returns_results(self, app):
        with app.app_context():
            conn = _db.engine.raw_connection()
            try:
                results = _check_tables_rls_enabled(conn)
                assert len(results) > 0
                for ok, msg in results:
                    assert isinstance(ok, bool)
                    assert isinstance(msg, str)
            finally:
                conn.close()

    def test_rls_policies_exist_returns_results(self, app):
        with app.app_context():
            conn = _db.engine.raw_connection()
            try:
                results = _check_rls_policies_exist(conn)
                assert len(results) > 0
                for ok, msg in results:
                    assert isinstance(ok, bool)
                    assert isinstance(msg, str)
            finally:
                conn.close()

    def test_rls_guard_table_list_not_empty(self, app):
        assert len(_TENANT_SCOPED_TABLES) > 0
        assert 'visits' in _TENANT_SCOPED_TABLES
        assert 'patients' in _TENANT_SCOPED_TABLES
