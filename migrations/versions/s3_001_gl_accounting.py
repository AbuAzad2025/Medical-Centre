"""Add General Ledger tables (accounts, gl_journals, gl_journal_lines)

Revision ID: s3_001_gl_accounting
Revises: s2_011_clean_schema

Creates the Chart of Accounts and double-entry journal tables that back the
new GL engine (services.gl_service.GLService).
"""

import sqlalchemy as sa
from alembic import op

revision = 's3_001_gl_accounting'
down_revision = 's2_011_clean_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=True,
            index=True,
        ),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('name_ar', sa.String(length=120), nullable=True),
        sa.Column('account_type', sa.String(length=20), nullable=False),
        sa.Column('normal_balance', sa.String(length=20), nullable=False),
        sa.Column(
            'parent_id',
            sa.Integer(),
            sa.ForeignKey('accounts.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint(
            "account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')",
            name='chk_account_type',
        ),
        sa.CheckConstraint(
            "normal_balance IN ('DEBIT', 'CREDIT')", name='chk_account_normal_balance'
        ),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_accounts_tenant_code'),
    )
    op.create_index('idx_accounts_code', 'accounts', ['code'])
    op.create_index('idx_accounts_type', 'accounts', ['account_type'])
    op.create_index('idx_accounts_normal', 'accounts', ['normal_balance'])
    op.create_index('idx_accounts_tenant_type', 'accounts', ['tenant_id', 'account_type'])
    op.create_index('idx_accounts_tenant_normal', 'accounts', ['tenant_id', 'normal_balance'])
    op.create_index('idx_accounts_parent', 'accounts', ['parent_id'])
    op.create_index('ix_accounts_tenant_id', 'accounts', ['tenant_id'])

    if bind.dialect.name == 'postgresql':
        # RLS on tenant-scoped accounts table.
        op.execute('ALTER TABLE accounts ENABLE ROW LEVEL SECURITY')
        op.execute(
            'CREATE POLICY accounts_tenant_policy ON accounts '
            "USING (tenant_id = current_setting('app.tenant_id', true)::bigint OR tenant_id IS NULL)"
        )

    op.create_table(
        'gl_journals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=True,
            index=True,
        ),
        sa.Column('journal_number', sa.String(length=40), nullable=True),
        sa.Column('journal_date', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='POSTED'),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column(
            'posted_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('POSTED', 'VOID')", name='chk_gl_journal_status'),
    )
    op.create_index('idx_gl_journals_source', 'gl_journals', ['source_type', 'source_id'])
    op.create_index(
        'idx_gl_journals_tenant_source', 'gl_journals', ['tenant_id', 'source_type', 'source_id']
    )
    op.create_index('idx_gl_journals_status', 'gl_journals', ['status'])
    op.create_index('idx_gl_journals_journal_number', 'gl_journals', ['journal_number'])
    op.create_index('ix_gl_journals_tenant_id', 'gl_journals', ['tenant_id'])

    if bind.dialect.name == 'postgresql':
        op.execute('ALTER TABLE gl_journals ENABLE ROW LEVEL SECURITY')
        op.execute(
            'CREATE POLICY gl_journals_tenant_policy ON gl_journals '
            "USING (tenant_id = current_setting('app.tenant_id', true)::bigint OR tenant_id IS NULL)"
        )

    op.create_table(
        'gl_journal_lines',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'journal_id',
            sa.Integer(),
            sa.ForeignKey('gl_journals.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'account_id',
            sa.Integer(),
            sa.ForeignKey('accounts.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('debit_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('credit_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('line_description', sa.Text(), nullable=True),
        sa.CheckConstraint('debit_amount >= 0', name='chk_gl_line_debit_non_negative'),
        sa.CheckConstraint('credit_amount >= 0', name='chk_gl_line_credit_non_negative'),
    )
    op.create_index('idx_gl_lines_journal', 'gl_journal_lines', ['journal_id'])
    op.create_index('idx_gl_lines_account', 'gl_journal_lines', ['account_id'])
    op.create_index('ix_gl_journal_lines_tenant_id', 'gl_journal_lines', ['tenant_id'])

    if bind.dialect.name == 'postgresql':
        op.execute('ALTER TABLE gl_journal_lines ENABLE ROW LEVEL SECURITY')
        op.execute(
            'CREATE POLICY gl_journal_lines_tenant_policy ON gl_journal_lines '
            "USING (tenant_id = current_setting('app.tenant_id', true)::bigint OR tenant_id IS NULL)"
        )


def downgrade() -> None:
    op.drop_table('gl_journal_lines')
    op.drop_table('gl_journals')
    op.drop_table('accounts')
