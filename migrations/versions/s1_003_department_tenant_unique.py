"""S1-003: per-tenant department name uniqueness.

Revision: s1_003_department_tenant_unique
Revises: s1_002_tenant_rls_policies
"""
from alembic import op

revision = 's1_003_department_tenant_unique'
down_revision = 's1_002_tenant_rls_policies'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('departments', schema=None) as batch_op:
        batch_op.drop_constraint('departments_name_key', type_='unique')
        batch_op.create_unique_constraint('uq_department_tenant_name', ['tenant_id', 'name'])


def downgrade() -> None:
    with op.batch_alter_table('departments', schema=None) as batch_op:
        batch_op.drop_constraint('uq_department_tenant_name', type_='unique')
        batch_op.create_unique_constraint('departments_name_key', ['name'])
