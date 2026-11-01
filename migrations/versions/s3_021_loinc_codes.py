"""Add LOINC codes table

Revision ID: s3_021_loinc_codes
Revises: s3_020_append_only_audit_trails
Create Date: 2026-10-28 22:10:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "s3_021_loinc_codes"
down_revision = "s3_020_append_only_audit_trails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loinc_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_loinc_codes_code", "loinc_codes", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_loinc_codes_code", table_name="loinc_codes")
    op.drop_table("loinc_codes")