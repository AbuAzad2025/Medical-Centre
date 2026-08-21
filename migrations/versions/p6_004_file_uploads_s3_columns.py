"""p6-004: add S3/MinIO storage columns to file_uploads.

P0 hardening: file uploads move from web-accessible local disk to private
object storage (S3/MinIO) with pre-signed URLs.  The FileUpload model gained
storage_backend/s3_* columns and a nullable file_path (S3 rows carry the key
instead of a disk path).  These columns previously existed only in databases
provisioned via db.create_all - production/migrated DBs lacked them entirely.

Revision: p6_004_file_uploads_s3_columns
Revises: p6_003_api_keys_rls
"""

import sqlalchemy as sa
from alembic import op

revision = 'p6_004_file_uploads_s3_columns'
down_revision = 'p6_003_api_keys_rls'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'file_uploads',
        sa.Column('storage_backend', sa.String(length=20), server_default='local',
                  nullable=False),
    )
    op.add_column('file_uploads', sa.Column('s3_key', sa.String(length=500), nullable=True))
    op.add_column('file_uploads', sa.Column('s3_bucket', sa.String(length=100), nullable=True))
    op.add_column('file_uploads', sa.Column('s3_region', sa.String(length=50), nullable=True))
    op.add_column('file_uploads', sa.Column('s3_etag', sa.String(length=64), nullable=True))
    # S3-backed rows store the object key in s3_key; legacy local rows keep path.
    op.alter_column('file_uploads', 'file_path', existing_type=sa.String(length=500),
                    nullable=True)
    op.create_index('idx_file_storage', 'file_uploads', ['storage_backend'])


def downgrade():
    op.drop_index('idx_file_storage', table_name='file_uploads')
    op.alter_column('file_uploads', 'file_path', existing_type=sa.String(length=500),
                    nullable=False)
    for col in ('s3_etag', 's3_region', 's3_bucket', 's3_key'):
        op.drop_column('file_uploads', col)
    op.drop_column('file_uploads', 'storage_backend')
