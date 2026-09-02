"""clean old rules and init new postgres

Revision ID: f224b8d0c4d2
Revises: s3_007_add_missing_system_configs
Create Date: 2026-09-02 10:49:08.663833

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f224b8d0c4d2'
down_revision = 's3_007_add_missing_system_configs'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
