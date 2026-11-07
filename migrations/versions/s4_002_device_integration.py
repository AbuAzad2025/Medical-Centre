"""Add IoT and Medical Device Integration tables with RLS.

Revision ID: s4_002_device_integration
Revises: s4_001_rls_order_sets
Create Date: 2026-11-07
"""

from alembic import op
import sqlalchemy as sa

from migrations.migration_utils import enable_tenant_rls

revision = "s4_002_device_integration"
down_revision = "s4_001_rls_order_sets"
branch_labels = None
depends_on = None

IOT_TABLES = ["iot_devices", "iot_readings"]
MDI_TABLES = ["medical_devices", "device_parameters", "device_alarms"]
ALL_TABLES = IOT_TABLES + MDI_TABLES


def upgrade() -> None:
    # Create IoT device tables
    op.create_table(
        "iot_devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("device_id", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("device_name", sa.String(200), nullable=True),
        sa.Column("manufacturer", sa.String(200), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("firmware_version", sa.String(50), nullable=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visit_id", sa.Integer, sa.ForeignKey("visits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), default="offline"),
        sa.Column("last_seen", sa.DateTime, nullable=True),
        sa.Column("battery_level", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("registered_at", sa.DateTime, default=sa.func.now()),
        sa.Column("registered_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_table(
        "iot_readings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("iot_devices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visit_id", sa.Integer, sa.ForeignKey("visits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reading_type", sa.String(50), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("recorded_at", sa.DateTime, default=sa.func.now(), index=True),
        sa.Column("is_critical", sa.Boolean, default=False),
        sa.Column("alert_sent", sa.Boolean, default=False),
    )
    # Create MDI tables
    op.create_table(
        "medical_devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("device_id", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("device_name", sa.String(200), nullable=True),
        sa.Column("manufacturer", sa.String(200), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("firmware_version", sa.String(50), nullable=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visit_id", sa.Integer, sa.ForeignKey("visits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), default="offline"),
        sa.Column("last_seen", sa.DateTime, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("registered_at", sa.DateTime, default=sa.func.now()),
        sa.Column("registered_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_table(
        "device_parameters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("medical_devices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parameter_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("recorded_at", sa.DateTime, default=sa.func.now(), index=True),
        sa.Column("is_critical", sa.Boolean, default=False),
    )
    op.create_table(
        "device_alarms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("medical_devices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("alarm_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), default="warning"),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("triggered_at", sa.DateTime, default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime, nullable=True),
        sa.Column("acknowledged_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
    )
    enable_tenant_rls(ALL_TABLES)


def downgrade() -> None:
    from migrations.migration_utils import disable_tenant_rls

    disable_tenant_rls(ALL_TABLES)
    for table in reversed(ALL_TABLES):
        op.drop_table(table)