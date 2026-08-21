"""create api_keys table

Revision ID: p6_002_api_keys
Revises: p6_001_missing_fk_indexes
Create Date: 2026-08-21

Machine-to-machine API keys for /api/* endpoints (hashed at rest).
"""

from alembic import op
import sqlalchemy as sa


revision = 'p6_002_api_keys'
down_revision = 'p6_001_missing_fk_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('key_prefix', sa.String(length=12), nullable=False, index=True),
        sa.Column('key_hash', sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column('scopes', sa.String(length=500), server_default='read', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False, index=True),
        sa.Column('created_by', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('rate_limit_max', sa.Integer(), server_default='100', nullable=False),
        sa.Column('rate_limit_window', sa.Integer(), server_default='60', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_index('idx_api_key_tenant_active', 'api_keys', ['tenant_id', 'is_active'])
    op.create_index('idx_api_key_expires', 'api_keys', ['expires_at'])


def downgrade():
    op.drop_index('idx_api_key_expires', table_name='api_keys')
    op.drop_index('idx_api_key_tenant_active', table_name='api_keys')
    op.drop_table('api_keys')
