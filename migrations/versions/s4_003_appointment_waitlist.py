"""Add appointment_waitlist table with tenant RLS.

Revision ID: s4_003_appointment_waitlist
Revises: s4_002_device_integration
Create Date: 2026-11-08
"""

import sqlalchemy as sa
from alembic import op

from migrations.migration_utils import enable_tenant_rls

revision = "s4_003_appointment_waitlist"
down_revision = "s4_002_device_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointment_waitlist",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("doctor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("department_id", sa.Integer, sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("status", sa.String(20), default="WAITING", nullable=False, index=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("preferred_time", sa.String(50), nullable=True),
        sa.Column("notified_at", sa.DateTime, nullable=True),
        sa.Column("converted_appointment_id", sa.Integer, sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_waitlist_tenant_status", "appointment_waitlist", ["tenant_id", "status"]
    )
    op.create_index(
        "idx_waitlist_patient_status", "appointment_waitlist", ["patient_id", "status"]
    )
    enable_tenant_rls(["appointment_waitlist"])


def downgrade() -> None:
    from migrations.migration_utils import disable_tenant_rls

    disable_tenant_rls(["appointment_waitlist"])
    op.drop_index("idx_waitlist_patient_status", table_name="appointment_waitlist")
    op.drop_index("idx_waitlist_tenant_status", table_name="appointment_waitlist")
    op.drop_table("appointment_waitlist")
