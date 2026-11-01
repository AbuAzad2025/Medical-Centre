"""Add SNOMED CT tables

Revision ID: s3_022_snomed_ct
Revises: s3_021_loinc_codes
Create Date: 2026-10-30 20:25:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "s3_022_snomed_ct"
down_revision = "s3_021_loinc_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snomed_concepts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.String(length=20), nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("term_ar", sa.Text(), nullable=True),
        sa.Column("semantic_tag", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id"),
    )
    op.create_index("ix_snomed_concepts_concept_id", "snomed_concepts", ["concept_id"], unique=True)

    op.create_table(
        "snomed_relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=20), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_snomed_relationships_source", "snomed_relationships", ["source_id"])
    op.create_index("ix_snomed_relationships_target", "snomed_relationships", ["target_id"])


def downgrade() -> None:
    op.drop_index("ix_snomed_relationships_target", table_name="snomed_relationships")
    op.drop_index("ix_snomed_relationships_source", table_name="snomed_relationships")
    op.drop_table("snomed_relationships")
    op.drop_index("ix_snomed_concepts_concept_id", table_name="snomed_concepts")
    op.drop_table("snomed_concepts")