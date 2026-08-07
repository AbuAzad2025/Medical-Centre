"""G-106: branding print header fields

Revision ID: p5_001_branding_print_headers
Revises: s2_009_schema_drift_sync
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists


revision = 'p5_001_branding_print_headers'
down_revision = 's2_009_schema_drift_sync'
branch_labels = None
depends_on = None

_PRINT_COLUMNS = (
    ('invoice_header_html', sa.Text()),
    ('invoice_footer_html', sa.Text()),
    ('receipt_header_html', sa.Text()),
    ('prescription_header_html', sa.Text()),
    ('prescription_footer_html', sa.Text()),
    ('tax_number', sa.String(50)),
    ('license_number', sa.String(50)),
)


def upgrade():
    for name, col_type in _PRINT_COLUMNS:
        if not column_exists('branding_settings', name):
            op.add_column('branding_settings', sa.Column(name, col_type, nullable=True))


def downgrade():
    for name, _ in reversed(_PRINT_COLUMNS):
        if column_exists('branding_settings', name):
            op.drop_column('branding_settings', name)
