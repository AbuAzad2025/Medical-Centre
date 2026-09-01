"""Add financial_periods table for period closing guard.

Revision ID: s3_002_financial_periods
Revises: s3_001_gl_accounting

Creates the financial_periods table used by the GL period-closing guard
in GLService.post_journal().
"""

import sqlalchemy as sa
from alembic import op

revision = 's3_002_financial_periods'
down_revision = 's3_001_gl_accounting'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        'financial_periods',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=True,
            index=True,
        ),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_closed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column(
            'closed_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('end_date >= start_date', name='chk_period_end_ge_start'),
        sa.UniqueConstraint('tenant_id', 'start_date', 'end_date', name='uq_periods_tenant_dates'),
    )
    op.create_index('idx_periods_tenant_closed', 'financial_periods', ['tenant_id', 'is_closed'])
    op.create_index(
        'idx_periods_tenant_dates', 'financial_periods', ['tenant_id', 'start_date', 'end_date']
    )

    if bind.dialect.name == 'postgresql':
        op.execute('ALTER TABLE financial_periods ENABLE ROW LEVEL SECURITY')
        op.execute(
            'CREATE POLICY financial_periods_tenant_policy ON financial_periods '
            "USING (tenant_id = current_setting('app.tenant_id', true)::bigint OR tenant_id IS NULL)"
        )


def downgrade() -> None:
    op.drop_index('idx_periods_tenant_closed', table_name='financial_periods')
    op.drop_index('idx_periods_tenant_dates', table_name='financial_periods')
    op.drop_table('financial_periods')
