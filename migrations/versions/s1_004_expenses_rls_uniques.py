"""S1-004: expenses table, RLS expansion, per-tenant unique constraints.

Revision: s1_004_expenses_rls_uniques
Revises: s1_003_department_tenant_unique
"""
from alembic import op
import sqlalchemy as sa

revision = 's1_004_expenses_rls_uniques'
down_revision = 's1_003_department_tenant_unique'
branch_labels = None
depends_on = None

RLS_TABLES = [
    'departments',
    'insurance_companies',
    'insurance_claims',
    'barcode_registry',
    'barcode_scan_logs',
    'expenses',
    'biometric_credentials',
    'biometric_auth_challenges',
    'wards',
    'medications',
    'audit_trails',
    'treatments',
    'emergency_cases',
    'budgets',
    'notifications',
    'medical_reports',
    'receipts',
    'refund_requests',
    'cash_registers',
]


def upgrade() -> None:
    op.create_table(
        'expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('recorded_by_id', sa.Integer(), nullable=True),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='RECORDED'),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recorded_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_expenses_tenant_id', 'expenses', ['tenant_id'])
    op.create_index('ix_expenses_category', 'expenses', ['category'])
    op.create_index('ix_expenses_recorded_by_id', 'expenses', ['recorded_by_id'])
    op.create_index('ix_expenses_expense_date', 'expenses', ['expense_date'])
    op.create_index('ix_expenses_status', 'expenses', ['status'])
    op.create_index('ix_expenses_created_at', 'expenses', ['created_at'])
    op.create_index('idx_expense_tenant_date', 'expenses', ['tenant_id', 'expense_date'])
    op.create_index('idx_expense_tenant_category', 'expenses', ['tenant_id', 'category'])

    with op.batch_alter_table('insurance_companies', schema=None) as batch_op:
        batch_op.drop_constraint('insurance_companies_name_key', type_='unique')
        batch_op.create_unique_constraint('uq_insurance_company_tenant_name', ['tenant_id', 'name'])

    with op.batch_alter_table('barcode_registry', schema=None) as batch_op:
        batch_op.drop_constraint('barcode_registry_barcode_value_key', type_='unique')
        batch_op.create_unique_constraint('uq_barcode_tenant_value', ['tenant_id', 'barcode_value'])

    with op.batch_alter_table('wards', schema=None) as batch_op:
        batch_op.drop_constraint('wards_code_key', type_='unique')
        batch_op.create_unique_constraint('uq_ward_tenant_code', ['tenant_id', 'code'])

    for table in RLS_TABLES:
        policy_name = f'tenant_isolation_{table}'
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(
            f"CREATE POLICY {policy_name} ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true)::int)"
        )


def downgrade() -> None:
    for table in reversed(RLS_TABLES):
        policy_name = f'tenant_isolation_{table}'
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')

    with op.batch_alter_table('wards', schema=None) as batch_op:
        batch_op.drop_constraint('uq_ward_tenant_code', type_='unique')
        batch_op.create_unique_constraint('wards_code_key', ['code'])

    with op.batch_alter_table('barcode_registry', schema=None) as batch_op:
        batch_op.drop_constraint('uq_barcode_tenant_value', type_='unique')
        batch_op.create_unique_constraint('barcode_registry_barcode_value_key', ['barcode_value'])

    with op.batch_alter_table('insurance_companies', schema=None) as batch_op:
        batch_op.drop_constraint('uq_insurance_company_tenant_name', type_='unique')
        batch_op.create_unique_constraint('insurance_companies_name_key', ['name'])

    op.drop_table('expenses')
