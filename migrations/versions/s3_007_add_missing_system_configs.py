"""Ensure system_configs and system_themes exist (missing from s2_011 chain).

Revision ID: s3_007_add_missing_system_configs
Revises: s3_006_add_vital_signs_blood_sugar

The prod_baseline creates these tables, but the s2_011 clean-schema branch
does not. Fresh DBs built from s2_011 -> s3_* therefore lack them, which
breaks verify-boot and branding_context at startup.
"""

import sqlalchemy as sa
from alembic import op

revision = 's3_007_add_missing_system_configs'
down_revision = 's3_006_add_vital_signs_blood_sugar'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table('system_configs'):
        op.create_table(
            'system_configs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('config_key', sa.String(length=100), nullable=False),
            sa.Column('config_value', sa.Text(), nullable=True),
            sa.Column('config_type', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category', sa.String(length=50), nullable=True),
            sa.Column('is_system', sa.Boolean(), nullable=True),
            sa.Column('is_encrypted', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.Column('tenant_id', sa.Integer(), nullable=True),
            sa.CheckConstraint(
                "category IN ('general', 'security', 'notification', 'backup', 'system', 'database', 'email', 'sms')",
                name='chk_category',
            ),
            sa.CheckConstraint(
                "config_type IN ('string', 'integer', 'boolean', 'json', 'file', 'password')",
                name='chk_config_type',
            ),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('config_key'),
        )
        with op.batch_alter_table('system_configs', schema=None) as batch_op:
            batch_op.create_index('idx_config_category', ['category'], unique=False)
            batch_op.create_index('idx_config_key', ['config_key'], unique=False)
            batch_op.create_index('idx_config_system', ['is_system'], unique=False)
            batch_op.create_index(
                batch_op.f('ix_system_configs_created_by'), ['created_by'], unique=False
            )
            batch_op.create_index(
                batch_op.f('ix_system_configs_tenant_id'), ['tenant_id'], unique=False
            )
            batch_op.create_index(
                batch_op.f('ix_system_configs_updated_by'), ['updated_by'], unique=False
            )

    if not insp.has_table('system_themes'):
        op.create_table(
            'system_themes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('name_ar', sa.String(length=100), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('is_default', sa.Boolean(), nullable=True),
            sa.Column('primary_color', sa.String(length=20), nullable=True),
            sa.Column('secondary_color', sa.String(length=20), nullable=True),
            sa.Column('background_color', sa.String(length=20), nullable=True),
            sa.Column('text_color', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('tenant_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('system_themes', schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f('ix_system_themes_tenant_id'), ['tenant_id'], unique=False
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table('system_themes'):
        op.drop_table('system_themes')
    if insp.has_table('system_configs'):
        op.drop_table('system_configs')
